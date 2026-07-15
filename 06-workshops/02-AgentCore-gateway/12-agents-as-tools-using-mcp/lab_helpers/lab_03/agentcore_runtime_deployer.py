"""
Lab 03: AgentCore Runtime 배포 헬퍼

AgentCore Code Interpreter를 사용하는 Strands remediation agent를 Amazon Bedrock AgentCore Runtime에 배포합니다.

기능:
- Runtime 실행용 IAM 역할 생성
- Agent 코드 패키징(Strands + Code Interpreter)
- bedrock-agentcore-starter-toolkit을 통한 Runtime 배포
- Parameter Store에 구성 저장
- 배포 수명 주기 관리(생성, 업데이트, 삭제)
- Lab-02 Gateway 연동(선택 사항)

AWS 패턴 기반:
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-toolkit.html
- https://github.com/awslabs/amazon-bedrock-agentcore-samples
"""

import json
import boto3
import logging
import time
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime
from botocore.exceptions import ClientError

# 중앙 집중식 구성 가져오기
from lab_helpers.config import AWS_REGION
from lab_helpers.constants import PARAMETER_PATHS

logger = logging.getLogger(__name__)

# 기본 구성
REGION = AWS_REGION  # config.py의 중앙 집중식 리전 사용
PREFIX = "aiml301"
RUNTIME_NAME = f"{PREFIX}-remediation-runtime"
RUNTIME_ROLE_NAME = f"{PREFIX}-agentcore-remediation-role"
RUNTIME_POLICY_NAME = f"{PREFIX}-remediation-runtime-policy"


class AgentCoreRuntimeDeployer:
    """Strands remediation agent를 AgentCore Runtime에 배포하는 헬퍼입니다."""

    def __init__(
        self,
        region: str = REGION,
        prefix: str = PREFIX,
        runtime_name: str = RUNTIME_NAME,
        verbose: bool = True,
    ):
        """
        AWS 클라이언트와 구성으로 배포 도구를 초기화합니다.

        인자:
            region: AWS 리전(기본값: us-west-2)
            prefix: 리소스 명명 접두사(기본값: aiml301)
            runtime_name: 배포된 Runtime 이름(기본값: aiml301-remediation-runtime)
            verbose: 상세 로깅 활성화 여부
        """
        self.region = region
        self.prefix = prefix
        self.runtime_name = runtime_name
        self.verbose = verbose

        # AWS 클라이언트
        self.iam = boto3.client("iam", region_name=region)
        self.agentcore = boto3.client("bedrock-agentcore-control", region_name=region)
        self.ssm = boto3.client("ssm", region_name=region)
        self.sts = boto3.client("sts", region_name=region)
        self.logs = boto3.client("logs", region_name=region)

        # 계정 ID 조회
        self.account_id = self.sts.get_caller_identity()["Account"]

        # 로거 초기화
        if verbose:
            logging.basicConfig(level=logging.INFO)
            logger.setLevel(logging.INFO)

    def _log(self, message: str, level: str = "info"):
        """메시지를 서식에 맞춰 기록합니다."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        levels = {"info": "ℹ️", "success": "✅", "error": "❌", "warning": "⚠️"}
        icon = levels.get(level, "•")
        print(f"{icon} [{timestamp}] {message}")
        getattr(logger, level, logger.info)(message)

    def check_prerequisites(self) -> bool:
        """모든 배포 사전 요구 사항이 충족되었는지 확인합니다."""
        self._log("Checking prerequisites...")

        try:
            # Toolkit 설치 확인
            try:
                from bedrock_agentcore_starter_toolkit import Runtime  # noqa: F401

                self._log("bedrock-agentcore-starter-toolkit is installed", "success")
            except ImportError:
                self._log(
                    "bedrock-agentcore-starter-toolkit not found. "
                    "Install with: pip install bedrock-agentcore-starter-toolkit",
                    "error",
                )
                return False

            # AWS 자격 증명 및 권한 확인
            identity = self.sts.get_caller_identity()
            self._log(f"AWS account: {self.account_id}", "success")
            self._log(f"AWS IAM user/role: {identity.get('Arn')}", "success")

            # IAM 권한 확인(역할 나열 시도)
            try:
                self.iam.list_roles(MaxItems=1)
                self._log("IAM permissions verified", "success")
            except ClientError as e:
                self._log(f"IAM permissions insufficient: {e}", "error")
                return False

            # AgentCore 접근 확인
            try:
                self.agentcore.list_agent_runtimes()
                self._log("AgentCore access verified", "success")
            except ClientError as e:
                self._log(f"AgentCore access denied: {e}", "error")
                return False

            self._log("All prerequisites met", "success")
            return True

        except Exception as e:
            self._log(f"Prerequisite check failed: {e}", "error")
            return False

    def create_runtime_iam_role(self) -> Dict:
        """
        AgentCore Runtime 실행용 IAM 역할을 생성합니다.

        이 역할은 다음을 허용합니다.
        - Runtime 서비스의 역할 수임
        - CloudWatch 로깅
        - ECR 이미지 접근
        - Bedrock 모델 호출(Code Interpreter용)
        - Parameter Store 접근

        반환:
            역할 ARN과 메타데이터가 포함된 딕셔너리
        """
        self._log("Creating IAM role for Runtime...")

        # 신뢰 정책: bedrock-agentcore 서비스가 역할을 수임하도록 허용
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": self.account_id},
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:runtime/*"
                        },
                    },
                }
            ],
        }

        # Runtime용 권한 정책
        permissions_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "CloudWatchLogs",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/bedrock-agentcore/runtime/*",
                },
                {
                    "Sid": "ECRAccess",
                    "Effect": "Allow",
                    "Action": [
                        "ecr:GetAuthorizationToken",
                        "ecr:BatchGetImage",
                        "ecr:GetDownloadUrlForLayer",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "BedrockModels",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    "Resource": f"arn:aws:bedrock:{self.region}::foundation-model/*",
                },
                {
                    "Sid": "CodeInterpreter",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:StartCodeInterpreterSession",
                        "bedrock-agentcore:InvokeCodeInterpreter",
                        "bedrock-agentcore:StopCodeInterpreterSession",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "ParameterStore",
                    "Effect": "Allow",
                    "Action": [
                        "ssm:GetParameter",
                        "ssm:GetParameters",
                        "ssm:GetParametersByPath",
                    ],
                    "Resource": f"arn:aws:ssm:{self.region}:{self.account_id}:parameter/{self.prefix}/*",
                },
            ],
        }

        try:
            # 역할이 존재하는지 확인
            try:
                role = self.iam.get_role(RoleName=RUNTIME_ROLE_NAME)
                self._log(f"IAM role already exists: {RUNTIME_ROLE_NAME}", "warning")
                role_arn = role["Role"]["Arn"]

                # 현재 리전에 맞도록 신뢰 정책 업데이트
                self.iam.update_assume_role_policy(RoleName=RUNTIME_ROLE_NAME, PolicyDocument=json.dumps(trust_policy))
                self._log(f"Updated trust policy for region {self.region}", "success")

            except self.iam.exceptions.NoSuchEntityException:
                # 새 역할 생성
                role = self.iam.create_role(
                    RoleName=RUNTIME_ROLE_NAME,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description="Execution role for AgentCore Runtime - Lab 03 Remediation Agent",
                    MaxSessionDuration=3600,
                )
                role_arn = role["Role"]["Arn"]
                self._log(f"Created IAM role: {RUNTIME_ROLE_NAME}", "success")

                # IAM에서 역할 전파 대기
                time.sleep(10)

            # 권한 정책 연결
            self.iam.put_role_policy(
                RoleName=RUNTIME_ROLE_NAME,
                PolicyName=RUNTIME_POLICY_NAME,
                PolicyDocument=json.dumps(permissions_policy),
            )
            self._log(f"Attached permissions policy: {RUNTIME_POLICY_NAME}", "success")

            # 역할 ARN을 Parameter Store에 저장
            param_name = PARAMETER_PATHS["lab_03"]["runtime_role_arn"]
            self.ssm.put_parameter(
                Name=param_name,
                Value=role_arn,
                Type="String",
                Overwrite=True,
                Description="IAM role ARN for Lab-03 AgentCore Runtime",
            )
            self._log("Stored role ARN in Parameter Store", "success")

            return {
                "role_arn": role_arn,
                "role_name": RUNTIME_ROLE_NAME,
                "policy_name": RUNTIME_POLICY_NAME,
                "account_id": self.account_id,
            }

        except Exception as e:
            self._log(f"Failed to create IAM role: {e}", "error")
            raise

    def package_agent_code(
        self,
        agent_script_path: Path,
        requirements_path: Optional[Path] = None,
        include_files: Optional[List[Path]] = None,
    ) -> Dict:
        """
        배포를 위해 Strands remediation agent 코드를 패키징합니다.

        인자:
            agent_script_path: Agent Python 스크립트 경로
            requirements_path: requirements.txt 경로(선택 사항)
            include_files: 포함할 추가 파일(선택 사항)

        반환:
            패키지 메타데이터와 파일 경로가 포함된 딕셔너리
        """
        self._log(f"Packaging agent code from {agent_script_path}...")

        # Agent 스크립트가 존재하는지 확인
        if not Path(agent_script_path).exists():
            self._log(f"Agent script not found: {agent_script_path}", "error")
            raise FileNotFoundError(f"Agent script not found: {agent_script_path}")

        # Agent 코드 읽기
        with open(agent_script_path, "r") as f:
            agent_code = f.read()

        package_info = {
            "agent_script": str(agent_script_path),
            "code_size_bytes": len(agent_code.encode()),
            "code_size_mb": round(len(agent_code.encode()) / (1024 * 1024), 2),
            "timestamp": datetime.utcnow().isoformat(),
            "files": {"agent_script": str(agent_script_path)},
        }

        # 제공된 경우 requirements 추가
        if requirements_path and Path(requirements_path).exists():
            with open(requirements_path, "r") as f:
                requirements = f.read()
            package_info["files"]["requirements"] = str(requirements_path)
            package_info["requirements_lines"] = len(requirements.splitlines())

        # 제공된 경우 기타 파일 추가
        if include_files:
            for file_path in include_files:
                if Path(file_path).exists():
                    package_info["files"][Path(file_path).name] = str(file_path)

        self._log(f"Agent code packaged: {package_info['code_size_mb']} MB", "success")

        return package_info

    def deploy_runtime(
        self,
        agent_code: str,
        agent_name: str = "remediation-agent",
        role_arn: Optional[str] = None,
        description: Optional[str] = None,
        timeout_seconds: int = 300,
    ) -> Dict:
        """
        Strands agent를 AgentCore Runtime에 배포합니다.

        인자:
            agent_code: 문자열 형식의 Agent Python 코드
            agent_name: Agent/Runtime 이름
            role_arn: IAM 역할 ARN(제공하지 않으면 Parameter Store에서 조회)
            description: Runtime 설명
            timeout_seconds: 실행 제한 시간

        반환:
            배포 정보(Runtime ID, ARN, 엔드포인트 등)가 포함된 딕셔너리
        """
        self._log(f"Deploying runtime: {agent_name}...")

        # 제공되지 않은 경우 역할 ARN 조회
        if not role_arn:
            try:
                response = self.ssm.get_parameter(Name=PARAMETER_PATHS["lab_03"]["runtime_role_arn"])
                role_arn = response["Parameter"]["Value"]
                self._log("Retrieved role ARN from Parameter Store", "info")
            except ClientError:
                self._log("Role ARN not found in Parameter Store. Creating role...", "warning")
                role_info = self.create_runtime_iam_role()
                role_arn = role_info["role_arn"]

        try:
            # bedrock-agentcore-starter-toolkit을 사용해 Runtime 생성
            from bedrock_agentcore_starter_toolkit import Runtime

            runtime = Runtime(
                name=self.runtime_name,
                entrypoint=agent_code,
                role_arn=role_arn,
                region_name=self.region,
                timeout_seconds=timeout_seconds,
                description=description or "Strands remediation agent with Code Interpreter - Lab 03",
            )

            # AgentCore에 배포
            runtime_config = runtime.deploy()

            self._log("Runtime deployed successfully", "success")

            deployment_info = {
                "runtime_name": self.runtime_name,
                "runtime_id": runtime_config.get("agent_runtime_id"),
                "runtime_arn": runtime_config.get("agent_runtime_arn"),
                "role_arn": role_arn,
                "region": self.region,
                "deployment_time": datetime.utcnow().isoformat(),
                "status": "DEPLOYED",
                "entrypoint": "agent_invocation",
                "tools": [
                    "validate_remediation_environment",
                    "generate_remediation_plan",
                    "execute_remediation_step",
                ],
            }

            # 배포 정보를 Parameter Store에 저장
            self.ssm.put_parameter(
                Name=f"/{self.prefix}/lab-03/runtime-config",
                Value=json.dumps(deployment_info, indent=2),
                Type="String",
                Overwrite=True,
                Description="Lab-03 AgentCore Runtime deployment configuration",
            )

            return deployment_info

        except Exception as e:
            self._log(f"Runtime deployment failed: {e}", "error")
            raise

    def get_runtime_status(self, runtime_id: Optional[str] = None) -> Dict:
        """
        배포된 Runtime의 상태를 조회합니다.

        인자:
            runtime_id: Runtime ID(제공하지 않으면 Parameter Store에서 조회)

        반환:
            Runtime 상태가 포함된 딕셔너리
        """
        try:
            # 제공되지 않은 경우 Runtime ID 조회
            if not runtime_id:
                response = self.ssm.get_parameter(Name=f"/{self.prefix}/lab-03/runtime-config")
                config = json.loads(response["Parameter"]["Value"])
                runtime_id = config.get("runtime_id")

            if not runtime_id:
                self._log("Runtime ID not found", "error")
                return {"status": "NOT_FOUND"}

            # Runtime 세부 정보 조회
            response = self.agentcore.get_agent_runtime(agentRuntimeIdentifier=runtime_id)

            status_info = {
                "runtime_id": response["agentRuntime"]["agentRuntimeId"],
                "runtime_arn": response["agentRuntime"]["agentRuntimeArn"],
                "status": response["agentRuntime"]["status"],
                "created_at": response["agentRuntime"].get("createdAt"),
                "last_modified": response["agentRuntime"].get("lastModifiedAt"),
            }

            self._log(f"Runtime status: {status_info['status']}", "info")
            return status_info

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                self._log(f"Runtime not found: {runtime_id}", "warning")
                return {"status": "NOT_FOUND"}
            raise

    def save_deployment_config(self, config: Dict, output_path: Optional[Path] = None) -> Path:
        """
        배포 구성을 파일에 저장합니다.

        인자:
            config: 배포 구성 딕셔너리
            output_path: 출력 파일 경로(선택 사항)

        반환:
            저장된 구성 파일의 경로
        """
        if not output_path:
            output_path = Path(__file__).parent.parent.parent / "lab_03_deployment_config.json"

        with open(output_path, "w") as f:
            json.dump(config, f, indent=2)

        self._log(f"Configuration saved to {output_path}", "success")
        return output_path

    def cleanup(self, force: bool = False) -> bool:
        """
        Lab-03 리소스를 정리합니다.

        인자:
            force: 확인 없이 강제 삭제할지 여부

        반환:
            정리에 성공하면 True
        """
        self._log("Starting cleanup...")

        if not force:
            confirm = input(
                f"Delete Lab-03 runtime '{self.runtime_name}' and related resources? This cannot be undone. (yes/no): "
            )
            if confirm.lower() != "yes":
                self._log("Cleanup cancelled", "warning")
                return False

        try:
            # Parameter Store에서 Runtime ID 조회
            try:
                response = self.ssm.get_parameter(Name=f"/{self.prefix}/lab-03/runtime-config")
                config = json.loads(response["Parameter"]["Value"])
                runtime_id = config.get("runtime_id")

                if runtime_id:
                    # Runtime 삭제
                    self.agentcore.delete_agent_runtime(agentRuntimeIdentifier=runtime_id)
                    self._log(f"Deleted runtime: {runtime_id}", "success")
            except ClientError as e:
                if e.response["Error"]["Code"] != "ParameterNotFound":
                    self._log(f"Error deleting runtime: {e}", "warning")

            # IAM 역할 및 정책 삭제
            try:
                self.iam.delete_role_policy(RoleName=RUNTIME_ROLE_NAME, PolicyName=RUNTIME_POLICY_NAME)
                self._log(f"Deleted role policy: {RUNTIME_POLICY_NAME}", "success")
            except ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchEntity":
                    self._log(f"Error deleting policy: {e}", "warning")

            try:
                self.iam.delete_role(RoleName=RUNTIME_ROLE_NAME)
                self._log(f"Deleted IAM role: {RUNTIME_ROLE_NAME}", "success")
            except ClientError as e:
                if e.response["Error"]["Code"] != "NoSuchEntity":
                    self._log(f"Error deleting role: {e}", "warning")

            # Parameter Store 항목 삭제
            try:
                self.ssm.delete_parameter(Name=PARAMETER_PATHS["lab_03"]["runtime_role_arn"])
                self._log("Deleted Parameter Store entry: runtime-role-arn", "success")
            except ClientError:
                pass

            try:
                self.ssm.delete_parameter(Name=PARAMETER_PATHS["lab_03"]["runtime_config"])
                self._log("Deleted Parameter Store entry: runtime-config", "success")
            except ClientError:
                pass

            # CloudWatch 로그 그룹 삭제
            try:
                log_groups = self.logs.describe_log_groups(
                    logGroupNamePrefix=f"/aws/bedrock-agentcore/runtime/{self.runtime_name}"
                )
                for log_group in log_groups.get("logGroups", []):
                    self.logs.delete_log_group(logGroupName=log_group["logGroupName"])
                    self._log(f"Deleted log group: {log_group['logGroupName']}", "success")
            except ClientError:
                pass

            self._log("Cleanup completed successfully", "success")
            return True

        except Exception as e:
            self._log(f"Cleanup failed: {e}", "error")
            raise


def store_runtime_configuration(
    runtime_arn: str,
    runtime_id: str = None,
    region: str = "us-west-2",
    prefix: str = "aiml301_sre_agentcore",
) -> None:
    """세션 간에 유지되도록 Runtime 구성을 Parameter Store에 저장합니다."""
    from lab_helpers.parameter_store import put_parameter

    print("\n" + "=" * 70)
    print("🔍 DEBUG: store_runtime_configuration() called")
    print("=" * 70)
    print(f"  Runtime ARN: {runtime_arn}")
    print(f"  Runtime ID: {runtime_id}")
    print(f"  Region: {region}")
    print(f"  Prefix: {prefix}")
    print()

    # 중앙 집중식 상수를 사용해 Runtime ARN 저장
    runtime_arn_path = PARAMETER_PATHS["lab_03"]["runtime_arn"]
    print("📝 Storing runtime ARN to Parameter Store:")
    print(f"  Path: {runtime_arn_path}")
    print(f"  Value: {runtime_arn}")
    try:
        result = put_parameter(
            key=runtime_arn_path,
            value=runtime_arn,
            description="AgentCore Runtime ARN for Lab-03",
            region_name=region,
            overwrite=True,
        )
        print(f"✅ Successfully stored runtime ARN (version: {result})")
    except Exception as e:
        print(f"❌ Failed to store runtime ARN: {e}")
        import traceback

        traceback.print_exc()
        raise

    # 제공된 경우 Runtime ID 저장
    if runtime_id:
        runtime_id_path = PARAMETER_PATHS["lab_03"]["runtime_id"]
        print("\n📝 Storing runtime ID to Parameter Store:")
        print(f"  Path: {runtime_id_path}")
        print(f"  Value: {runtime_id}")
        try:
            result = put_parameter(
                key=runtime_id_path,
                value=runtime_id,
                description="AgentCore Runtime ID for Lab-03",
                region_name=region,
                overwrite=True,
            )
            print(f"✅ Successfully stored runtime ID (version: {result})")
        except Exception as e:
            print(f"❌ Failed to store runtime ID: {e}")
            import traceback

            traceback.print_exc()
            raise
    else:
        print("\n⏭️  Runtime ID not provided, skipping...")

    print("\n" + "=" * 70)
    print("✅ store_runtime_configuration() complete")
    print("=" * 70 + "\n")
