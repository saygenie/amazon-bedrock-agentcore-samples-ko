import base64
import boto3
from bedrock_agentcore_starter_toolkit import Runtime
from boto3.session import Session
from langfuse import get_client
from utils.aws import get_ssm_parameter

boto_session = Session()
region = boto_session.region_name

agentcore_runtime = Runtime()


class ExistingAgentLaunchResult:
    """이미 배포된 에이전트의 API 호환성을 유지하는 모의 시작 결과 객체입니다."""

    def __init__(self, agent_arn, agent_id, ecr_uri=None, status="ACTIVE"):
        self.agent_arn = agent_arn
        self.agent_id = agent_id
        self.ecr_uri = ecr_uri
        self.status = status
        self.already_deployed = True


LANGFUSE_PROJECT_NAME = get_ssm_parameter("/langfuse/LANGFUSE_PROJECT_NAME")
LANGFUSE_SECRET_KEY = get_ssm_parameter("/langfuse/LANGFUSE_SECRET_KEY")
LANGFUSE_PUBLIC_KEY = get_ssm_parameter("/langfuse/LANGFUSE_PUBLIC_KEY")
LANGFUSE_HOST = get_ssm_parameter("/langfuse/LANGFUSE_HOST")

# Langfuse 구성
otel_endpoint = f"{LANGFUSE_HOST}/api/public/otel"
langfuse_project_name = LANGFUSE_PROJECT_NAME
langfuse_secret_key = LANGFUSE_SECRET_KEY
langfuse_public_key = LANGFUSE_PUBLIC_KEY
langfuse_auth_token = base64.b64encode(f"{langfuse_public_key}:{langfuse_secret_key}".encode()).decode()
otel_auth_header = f"Authorization=Basic {langfuse_auth_token}"


def deploy_agent(model, system_prompt, force_redeploy=False, environment="DEV"):
    """
    지정된 구성으로 Amazon Bedrock AgentCore Runtime 에이전트를 배포합니다.

    파라미터:
    - model (dict): 모델 이름과 model_id가 포함된 딕셔너리
    - system_prompt (dict): 프롬프트 이름과 프롬프트 텍스트가 포함된 딕셔너리
    - force_redeploy (bool): True이면 에이전트가 이미 있어도 다시 배포(기본값: False)

    반환:
    - dict: AgentCore Runtime의 시작 결과 또는 이미 배포된 경우 기존 에이전트 정보
    """
    agent_name = f"strands_{model['name']}_{system_prompt['name']}_{environment}"

    # 에이전트가 이미 있는지 확인
    try:
        agentcore_control_client = boto3.client("bedrock-agentcore-control", region_name=region)

        # 이 에이전트가 이미 있는지 확인하기 위해 모든 에이전트 런타임 조회
        list_response = agentcore_control_client.list_agent_runtimes()
        existing_agents = list_response.get("agentRuntimes", [])
        # 이 이름의 에이전트가 이미 있는지 확인
        existing_agent = None
        for agent_summary in existing_agents:
            if agent_summary.get("agentRuntimeName") == agent_name:
                existing_agent = agent_summary
                break

        # 에이전트가 있고 force_redeploy가 False이면 기존 에이전트 정보 반환
        if existing_agent and not force_redeploy:
            print(f"Agent '{agent_name}' already exists. Skipping deployment.")
            print(f"Agent Runtime ARN: {existing_agent.get('agentRuntimeArn')}")
            print(f"Status: {existing_agent.get('status')}")

            # ECR URI를 추출하기 위해 에이전트 런타임의 전체 세부 정보 가져오기
            agent_runtime_id = existing_agent.get("agentRuntimeId")
            agent_runtime_arn = existing_agent.get("agentRuntimeArn")

            try:
                get_response = agentcore_control_client.get_agent_runtime(agentRuntimeId=agent_runtime_id)
                ecr_uri = get_response.get("ecrUri", "")
            except Exception as e:
                print(f"Warning: Could not retrieve ECR URI: {str(e)}")
                ecr_uri = ""

            # 호환 가능한 시작 결과 객체 생성
            launch_result = ExistingAgentLaunchResult(
                agent_arn=agent_runtime_arn,
                agent_id=agent_runtime_id,
                ecr_uri=ecr_uri,
                status=existing_agent.get("status", "ACTIVE"),
            )

            return {
                "agent_name": agent_name,
                "launch_result": launch_result,
                "model_id": model["model_id"],
                "system_prompt_id": system_prompt["name"],
            }

        # 에이전트가 있고 force_redeploy가 True이면 사용자에게 알림
        if existing_agent and force_redeploy:
            print(f"Agent '{agent_name}' already exists. Force redeploying...")

    except Exception as e:
        print(f"Error checking existing agents: {str(e)}")
        print("Proceeding with deployment...")

    # 배포 진행
    response = agentcore_runtime.configure(
        entrypoint="./agents/strands_claude.py",
        auto_create_execution_role=True,
        auto_create_ecr=True,
        requirements_file="./agents/requirements.txt",
        region=region,
        agent_name=agent_name,
        disable_otel=True,
        memory_mode="NO_MEMORY",
    )

    print(response)

    # 에이전트 구성
    bedrock_model_id = model["model_id"]
    system_prompt_value = system_prompt["prompt"]

    launch_result = agentcore_runtime.launch(
        env_vars={
            "BEDROCK_MODEL_ID": bedrock_model_id,
            "LANGFUSE_PROJECT_NAME": langfuse_project_name,
            "LANGFUSE_TRACING_ENVIRONMENT": environment,
            "OTEL_EXPORTER_OTLP_ENDPOINT": otel_endpoint,  # Langfuse OTEL 엔드포인트 사용
            "OTEL_EXPORTER_OTLP_HEADERS": otel_auth_header,  # Langfuse OTEL 인증 헤더 추가
            "DISABLE_ADOT_OBSERVABILITY": "true",
            "SYSTEM_PROMPT": system_prompt_value,
        }
    )

    print(launch_result)

    return {
        "agent_name": agent_name,
        "launch_result": launch_result,
        "model_id": model["model_id"],
        "system_prompt_id": system_prompt["name"],
    }


def invoke_agent(agent_arn, prompt, session_id=None, environment=None):
    """
    주어진 프롬프트로 Amazon Bedrock AgentCore Runtime 에이전트를 호출합니다.

    파라미터:
    - agent_arn (str): 배포된 에이전트 런타임의 ARN
    - prompt (str): 에이전트의 입력 프롬프트
    - session_id (str, optional): 세션의 고유 식별자

    반환:
    - dict: 에이전트의 응답
    """
    import json
    import uuid

    try:
        # Bedrock AgentCore 클라이언트 초기화
        agent_core_client = boto3.client("bedrock-agentcore", region_name=region)

        if environment == "DEV":
            trace_id = get_client().get_current_trace_id()
            obs_id = get_client().get_current_observation_id()

            payload = json.dumps({"prompt": prompt, "trace_id": trace_id, "parent_obs_id": obs_id}).encode()
        else:
            payload = json.dumps({"prompt": prompt}).encode()

        # session_id가 제공되지 않으면 생성
        if session_id is None:
            session_id = str(uuid.uuid4())

        # 에이전트 호출
        response = agent_core_client.invoke_agent_runtime(
            agentRuntimeArn=agent_arn, runtimeSessionId=session_id, payload=payload
        )

        # 콘텐츠 유형에 따라 응답 처리
        content_type = response.get("contentType", "")

        if "text/event-stream" in content_type:
            # 스트리밍 응답 처리
            content = []
            for line in response["response"].iter_lines(chunk_size=10):
                if line:
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        line = line[6:]
                        content.append(line)

            return {
                "response": "\n".join(content),
                "session_id": session_id,
                "content_type": content_type,
            }

        elif content_type == "application/json":
            # 표준 JSON 응답 처리
            content = []
            for chunk in response.get("response", []):
                content.append(chunk.decode("utf-8"))

            return {
                "response": json.loads("".join(content)),
                "session_id": session_id,
                "content_type": content_type,
            }

        else:
            # 다른 콘텐츠 유형은 원시 응답 반환
            return {
                "response": response,
                "session_id": session_id,
                "content_type": content_type,
            }

    except Exception as e:
        return {"error": str(e), "agent_arn": agent_arn}


def delete_agent(agent_runtime_id, ecr_uri):
    """
    Amazon Bedrock AgentCore Runtime 에이전트와 해당 ECR 리포지토리를 삭제합니다.

    파라미터:
    - agent_runtime_id (str): 삭제할 에이전트 런타임 ID
    - ecr_uri (str): 에이전트 컨테이너 리포지토리의 ECR URI

    반환:
    - dict: 삭제 작업의 상태
    """
    try:
        # Bedrock AgentCore Control 클라이언트 초기화
        agentcore_control_client = boto3.client("bedrock-agentcore-control", region_name=region)

        # ECR 클라이언트 초기화
        ecr_client = boto3.client("ecr", region_name=region)

        # 에이전트 런타임 삭제
        runtime_delete_response = agentcore_control_client.delete_agent_runtime(
            agentRuntimeId=agent_runtime_id,
        )

        print(f"ECR repository: {ecr_uri}")

        # ECR 리포지토리 삭제
        repository_name_tmp = ecr_uri.split("/")[1] if "/" in ecr_uri else ecr_uri

        print(f"Repository name 1: {repository_name_tmp}")

        repository_name = repository_name_tmp.split(":")[0] if ":" in repository_name_tmp else repository_name_tmp

        print(f"Repository name 1: {repository_name}")

        print(f"Deleting ECR repository: {repository_name}")

        ecr_delete_response = ecr_client.delete_repository(repositoryName=repository_name, force=True)

        return {
            "status": "success",
            "agent_runtime_id": agent_runtime_id,
            "runtime_delete_response": runtime_delete_response,
            "ecr_delete_response": ecr_delete_response,
        }

    except Exception as e:
        return {
            "status": "error",
            "agent_runtime_id": agent_runtime_id,
            "error": str(e),
        }
