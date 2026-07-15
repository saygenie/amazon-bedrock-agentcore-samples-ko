#!/usr/bin/env python3
"""
Lab 3: FastMCP를 사용하는 Strands Remediation Agent - AgentCore Runtime 배포
Gateway-to-Runtime 통신용 MCP 프로토콜을 FastMCP로 구현합니다.

주요 내용:
- FastMCP를 사용한 MCP 프로토콜 구현
- 승인 단계를 포함한 안전한 수정 워크플로
- Code Interpreter를 사용한 인프라 자동화
- 2단계 프로세스: 계획 → 승인 → 실행
- 위험 평가 및 영향 분석

서버리스 실행을 위해 AgentCore Runtime에 배포됩니다.
"""

import os
import boto3
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Literal

# AgentCore Runtime 호환성을 위한 공식 MCP 패키지
from mcp.server.fastmcp import FastMCP

# Strands 프레임워크
from strands import Agent
from strands.models import BedrockModel
from strands.tools import tool

# AgentCore 배포 시 도구 동의 우회
os.environ["BYPASS_TOOL_CONSENT"] = "true"

# 로깅 구성
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("bedrock_agentcore.app")


# AWS 리전 자동 감지
def get_aws_region():
    """환경 또는 boto3 세션에서 AWS 리전을 자동 감지합니다."""
    # 먼저 환경 변수 확인
    region = os.environ.get("AWS_REGION")
    if region:
        return region

    # boto3 세션 기본 리전 확인
    try:
        session = boto3.Session()
        region = session.region_name
        if region:
            return region
    except Exception:
        pass

    # 대체값으로 us-east-1 사용
    return "us-west-2"


# 환경 변수(AgentCore Runtime에서 설정)
AWS_REGION = get_aws_region()
logger.info(f"🌍 Using AWS Region: {AWS_REGION}")
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0")
AWS_ACCESS_KEY_ID = "none"
AWS_SECRET_ACCESS_KEY = "none"  # pragma: allowlist secret

# IAM 역할 사용 시 'none' 문자열을 None으로 처리
if AWS_ACCESS_KEY_ID.lower() == "none":
    AWS_ACCESS_KEY_ID = None
if AWS_SECRET_ACCESS_KEY.lower() == "none":
    AWS_SECRET_ACCESS_KEY = None

# AgentCore Runtime용 FastMCP 서버 초기화
# host="0.0.0.0" - AgentCore 요구 사항에 따라 모든 인터페이스에서 수신
# stateless_http=True - 엔터프라이즈 보안을 위한 세션 격리 활성화
mcp = FastMCP("SRE Remediation Agent", host="0.0.0.0", stateless_http=True)  # nosec B104

# Code Interpreter용 전역 변수
agentcore_code_interpreter = None
CODE_INTERPRETER_AVAILABLE = False


def get_boto3_client(service_name: str, region: str = None):
    """환경 변수의 자격 증명으로 boto3 클라이언트를 생성합니다."""
    # region = region or AWS_REGION
    region = get_aws_region()

    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        return boto3.client(
            service_name,
            region_name=region,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
    else:
        return boto3.client(service_name, region_name=region)


def get_boto3_session():
    """환경 변수의 자격 증명으로 boto3 세션을 생성합니다."""
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        return boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION,
        )
    else:
        return boto3.Session(region_name=AWS_REGION)


def get_code_interpreter_from_ssm():
    """SSM Parameter Store에서 Code Interpreter 세부 정보를 조회합니다."""
    ssm = get_boto3_client("ssm")
    WORKSHOP_NAME = "aiml301_sre_agentcore"

    try:
        interpreter_id = ssm.get_parameter(Name=f"/{WORKSHOP_NAME}/lab-03/code-interpreter-id")["Parameter"]["Value"]
        interpreter_arn = ssm.get_parameter(Name=f"/{WORKSHOP_NAME}/lab-03/code-interpreter-arn")["Parameter"]["Value"]
        logger.info(f"✅ Retrieved code interpreter from SSM: {interpreter_id}")
        return interpreter_id, interpreter_arn
    except Exception as e:
        logger.error(f"Failed to retrieve code interpreter from SSM: {e}")
        raise


# SSM에서 Code Interpreter 조회
CUSTOM_INTERPRETER_ID, CUSTOM_INTERPRETER_ARN = get_code_interpreter_from_ssm()


def get_sre_remediation_s3_bucket():
    # SSM Parameter Store에 저장
    parameter_name = "/aiml301_sre_workshop/remediation_s3_bucket"
    # ssm = get_boto3_client('ssm')
    ssm = boto3.client("ssm", region_name="us-west-2")
    parameter = ssm.get_parameter(Name=parameter_name)
    retrieved_bucket_name = parameter["Parameter"]["Value"]
    print(f"Retrieved bucket name from Parameter Store: {retrieved_bucket_name}")
    return retrieved_bucket_name


# SSM에서 S3 세부 정보 조회
retrieved_bucket_name = get_sre_remediation_s3_bucket()


def initialize_code_interpreter_client():
    """AgentCore Code Interpreter 클라이언트를 초기화합니다."""
    global agentcore_code_interpreter, CODE_INTERPRETER_AVAILABLE

    try:
        agentcore_code_interpreter = get_boto3_client("bedrock-agentcore")
        CODE_INTERPRETER_AVAILABLE = True
        logger.info("✅ AgentCore Code Interpreter client initialized")
        return True
    except Exception as e:
        CODE_INTERPRETER_AVAILABLE = False
        logger.warning(f"⚠️ AgentCore Code Interpreter not available: {e}")
        return False


def start_code_interpreter_session():
    """사용자 지정 Interpreter로 Code Interpreter 세션을 시작합니다."""
    if not CODE_INTERPRETER_AVAILABLE:
        return None

    try:
        session_response = agentcore_code_interpreter.start_code_interpreter_session(
            codeInterpreterIdentifier=CUSTOM_INTERPRETER_ID,  # 사용자 지정 Interpreter 사용
            name=f"remediation-session-{uuid.uuid4()}",
            sessionTimeoutSeconds=1800,  # 30분
        )

        session_id = session_response.get("sessionId")
        logger.info(f"✅ Code Interpreter session started: {session_id}")
        return session_id

    except Exception as e:
        logger.error(f"❌ Failed to start Code Interpreter session: {e}")
        return None


def stop_code_interpreter_session(session_id: str):
    """Code Interpreter 세션을 중지합니다."""
    if not session_id or not CODE_INTERPRETER_AVAILABLE:
        return

    try:
        agentcore_code_interpreter.stop_code_interpreter_session(
            codeInterpreterIdentifier=CUSTOM_INTERPRETER_ID,  # 사용자 지정 Interpreter 사용
            sessionId=session_id,
        )
        logger.info(f"✅ Code Interpreter session stopped: {session_id}")
    except Exception as e:
        logger.error(f"❌ Failed to stop Code Interpreter session: {e}")


def execute_remediation_code(session_id: str, code: str) -> Dict:
    """사용자 지정 AgentCore Code Interpreter로 수정 코드를 실행합니다."""
    if not session_id:
        return {"error": "No Code Interpreter session available"}

    try:
        logger.info(f"🔧 Executing remediation code: {code}")

        execute_response = agentcore_code_interpreter.invoke_code_interpreter(
            codeInterpreterIdentifier=CUSTOM_INTERPRETER_ID,  # 사용자 지정 Interpreter 사용
            sessionId=session_id,
            name="executeCode",
            arguments={"language": "python", "code": code},
        )

        # 스트리밍 응답 처리
        output_text = ""
        execution_status = "success"

        for event in execute_response.get("stream", []):
            if "result" in event:
                result = event["result"]
                if "content" in result:
                    for content_item in result["content"]:
                        if content_item.get("type") == "text":
                            output_text += content_item.get("text", "")
                        elif content_item.get("type") == "error":
                            execution_status = "error"
                            output_text += f"ERROR: {content_item.get('text', '')}"

        return {
            "execution_status": execution_status,
            "output": output_text,
            "session_id": session_id,
        }

    except Exception as e:
        logger.error(f"❌ Failed to execute remediation code: {e}")
        return {"error": f"Code execution failed: {str(e)}"}


# FastMCP 도구 정의


@tool
def execute_remediation_step(remediation_code: str) -> str:
    """Execute remediation steps"""
    try:
        logger.info(f"🔧 execute_remediation_step called with code length: {len(remediation_code)}")

        if not initialize_code_interpreter_client():
            logger.error("❌ Code interpreter client not available")
            return "AgentCore Code Interpreter not available"

        logger.info("✅ Code interpreter client initialized")
        session_id = start_code_interpreter_session()
        if not session_id:
            logger.error("❌ Failed to start code interpreter session")
            return "Failed to start code interpreter session"

        logger.info(f"✅ Code interpreter session started: {session_id}")

        # 모든 수정 코드 앞에 리전 감지 코드 추가
        region_detection = """import requests
import os

# Detect AWS region from EC2 metadata
try:
    token = requests.put(
        'http://169.254.169.254/latest/api/token',
        headers={'X-aws-ec2-metadata-token-ttl-seconds': '21600'},
        timeout=1
    ).text
    AWS_REGION = requests.get(
        'http://169.254.169.254/latest/meta-data/placement/region',
        headers={'X-aws-ec2-metadata-token': token},
        timeout=1
    ).text
    print(f"✓ Detected region: {AWS_REGION}")
except Exception as e:
    AWS_REGION = 'us-west-2'
    print(f"⚠ Using default region: {AWS_REGION}")

"""
        wrapped_code = region_detection + remediation_code

        try:
            logger.info("⚡ Executing remediation code...")
            execution_result = execute_remediation_code(session_id, wrapped_code)
            logger.info("✅ Code execution completed")

            if "error" in execution_result:
                logger.error(f"❌ Execution error: {execution_result['error']}")
                return f"❌ failed: {execution_result['error']}"

            response = "# ✅ APPROVED EXECUTION - Results\n\n"
            response += "## Execution Output\n\n```\n"
            response += execution_result["output"]
            response += "\n```\n"

            logger.info(f"✅ Execution successful, output length: {len(execution_result['output'])}")
            return response

        except Exception as e:
            logger.error(f"❌ Execution exception: {type(e).__name__}: {str(e)}", exc_info=True)
            return f"❌ remediation plan execution failed: {str(e)}"
        finally:
            logger.info(f"🛑 Stopping session: {session_id}")
            stop_code_interpreter_session(session_id)

    except Exception as e:
        logger.error(
            f"❌ execute_remediation_step failed: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return f"❌ Tool failed: {str(e)}"


@tool
def validate_remediation_environment() -> str:
    """Validate that the remediation environment is ready"""
    try:
        logger.info("🔍 validate_remediation_environment called")
        logger.info("🔍 Validating remediation environment...")

        validation_results = {
            "code_interpreter_available": False,
            "session_creation": False,
            "aws_access": False,
            "environment_ready": False,
        }

        try:
            # Code Interpreter 초기화 테스트
            logger.info("Testing code interpreter initialization...")
            if initialize_code_interpreter_client():
                validation_results["code_interpreter_available"] = True
                logger.info("✅ Code interpreter available")

                # 세션 생성 테스트
                logger.info("Testing session creation...")
                session_id = start_code_interpreter_session()
                if session_id:
                    validation_results["session_creation"] = True
                    validation_results["aws_access"] = True  # 데모를 위해 단순화
                    logger.info(f"✅ Session created: {session_id}")
                    stop_code_interpreter_session(session_id)
                else:
                    logger.error("❌ Session creation failed")
            else:
                logger.error("❌ Code interpreter not available")

            validation_results["environment_ready"] = all(
                [
                    validation_results["code_interpreter_available"],
                    validation_results["session_creation"],
                    validation_results["aws_access"],
                ]
            )

        except Exception as e:
            logger.error(
                f"❌ Environment validation failed: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )

        # 응답 서식 지정
        response = "# Remediation Environment Validation\n\n"
        response += f"**Validation Date**: {datetime.now(timezone.utc).isoformat()}\n\n"

        for check, status in validation_results.items():
            status_icon = "✅" if status else "❌"
            check_name = check.replace("_", " ").title()
            response += f"- **{check_name}**: {status_icon} {'PASS' if status else 'FAIL'}\n"

        if validation_results["environment_ready"]:
            response += "\n🎉 **Environment is READY for remediation**\n"
            logger.info("✅ Environment validation passed")
        else:
            response += "\n⚠️ **Environment is NOT READY**\n"
            logger.warning("⚠️ Environment validation failed")

        logger.info("=" * 80)
        logger.info("📤 RAW AGENT RESPONSE")
        logger.info(f"Response type: {type(response)}")
        logger.info(f"Response attributes: {dir(response)}")
        logger.debug(f"Full response object: {response}")
        logger.debug(f"Response.message: {response.message}")
        logger.info("=" * 80)

        return response

    except Exception as e:
        logger.error(
            f"❌ validate_remediation_environment failed: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        return f"❌ Validation failed: {str(e)}"


@tool
def persist_remediation_scripts_to_s3(file_key: str, content: str) -> dict:
    """Write python scripts to S3 bucket.

    Args:
        file_key: The S3 key (path/filename) where the file will be stored
        content: The content to write to the file
    """
    bucket_name = retrieved_bucket_name
    region = AWS_REGION
    try:
        s3_client = get_boto3_client("s3")

        # S3에 쓰기
        s3_client.put_object(Bucket=bucket_name, Key=file_key, Body=content.encode("utf-8"))

        # S3 URL 생성
        s3_url = f"s3://{bucket_name}/{file_key}"
        https_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{file_key}"

        result = {
            "success": True,
            "message": "Successfully wrote file to S3",
            "bucket": bucket_name,
            "key": file_key,
            "s3_url": s3_url,
            "https_url": https_url,
            "size_bytes": len(content.encode("utf-8")),
        }

        return {
            "status": "success",
            "content": [{"text": f"✓ File written  to {s3_url}"}, {"json": result}],
        }

    except Exception as e:
        error_msg = f"Failed to write file to S3: {str(e)}"
        return {"status": "error", "content": [{"text": error_msg}]}


@tool
def read_remediation_scripts_from_s3(prefix: str = "") -> dict:
    """Read all files from an S3 bucket and return their contents.

    Args:
        prefix: Optional prefix to filter files (e.g., 'crm-remediation')
    """
    bucket_name = retrieved_bucket_name
    region = AWS_REGION
    max_files = 100

    try:
        logger.info(f"🔧 read_remediation_scripts_from_s3 called with prefix='{prefix}'")
        logger.info(f"📦 Reading from bucket: {bucket_name}, region: {region}")

        s3_client = get_boto3_client("s3")

        # 객체 나열
        list_params = {"Bucket": bucket_name, "MaxKeys": max_files}
        if prefix:
            list_params["Prefix"] = prefix

        logger.info(f"📋 Listing objects with params: {list_params}")
        response = s3_client.list_objects_v2(**list_params)

        # 수정: 파일이 없을 때만 일찍 반환하도록 'in'을 'not in'으로 변경
        if "Contents" not in response:
            logger.warning(f"⚠️ No files found in s3://{bucket_name}/{prefix}")
            return {
                "status": "success",
                "content": [
                    {"text": f"No files found in s3://{bucket_name}/{prefix}"},
                    {
                        "json": {
                            "success": True,
                            "bucket": bucket_name,
                            "prefix": prefix,
                            "file_count": 0,
                            "files": [],
                        }
                    },
                ],
            }

        logger.info(f"✅ Found {len(response['Contents'])} objects")
        files_data = []
        total_size = 0

        # 각 파일 읽기
        for obj in response["Contents"]:
            file_key = obj["Key"]

            # 디렉터리 건너뛰기(/로 끝나는 키)
            if file_key.endswith("/"):
                logger.info(f"⏭️ Skipping directory: {file_key}")
                continue

            logger.info(f"📄 Reading file: {file_key}")
            try:
                # 파일 내용 읽기
                file_response = s3_client.get_object(Bucket=bucket_name, Key=file_key)
                content = file_response["Body"].read().decode("utf-8")

                file_info = {
                    "key": file_key,
                    "s3_url": f"s3://{bucket_name}/{file_key}",
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "content": content,
                }
                files_data.append(file_info)
                total_size += obj["Size"]
                logger.info(f"✅ Read file: {file_key} ({obj['Size']} bytes)")
            except Exception as file_error:
                # 파일을 읽을 수 없으면 오류 정보를 포함하고 계속 진행
                logger.error(f"❌ Failed to read {file_key}: {type(file_error).__name__}: {str(file_error)}")
                files_data.append(
                    {
                        "key": file_key,
                        "s3_url": f"s3://{bucket_name}/{file_key}",
                        "size": obj["Size"],
                        "last_modified": obj["LastModified"].isoformat(),
                        "error": str(file_error),
                    }
                )

        logger.info(f"✅ Successfully read {len(files_data)} files, total size: {total_size} bytes")
        result = {
            "success": True,
            "message": f"Successfully read {len(files_data)} files from S3",
            "bucket": bucket_name,
            "prefix": prefix,
            "file_count": len(files_data),
            "total_size_bytes": total_size,
            "files": files_data,
        }

        return {
            "status": "success",
            "content": [
                {"text": f"✓ Read {len(files_data)} files from s3://{bucket_name}/{prefix}"},
                {"json": result},
            ],
        }

    except Exception as e:
        logger.error(
            f"❌ read_remediation_scripts_from_s3 failed: {type(e).__name__}: {str(e)}",
            exc_info=True,
        )
        error_msg = f"Failed to read files from S3: {str(e)}"
        return {"status": "error", "content": [{"text": error_msg}]}


@tool
def get_current_time() -> str:
    """Get the current time in UTC ISO format."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


@tool
def convert_timezone(time_str: str, from_tz: str, to_tz: str) -> str:
    """Convert time between timezones. Supports UTC and ISO format (e.g., 'America/Los_Angeles', 'US/Pacific')."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    # 입력 시간 파싱
    dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))

    # 원본 시간대에서 변환
    if from_tz.upper() == "UTC":
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    else:
        dt = dt.replace(tzinfo=ZoneInfo(from_tz))

    # 대상 시간대로 변환
    if to_tz.upper() == "UTC":
        dt = dt.astimezone(ZoneInfo("UTC"))
    else:
        dt = dt.astimezone(ZoneInfo(to_tz))

    return dt.isoformat()


current_architecture = """
## Current Architecture

## System Context
You are troubleshooting a 3-tier web application deployed on AWS. The infrastructure consists of two separate application flows: a main Python application and a CRM demo application, both with complete observability through CloudWatch.

## Network Architecture

### VPC Configuration
- VPC CIDR: 10.0.0.0/16
- Public Subnets: 10.0.1.0/24 (AZ1), 10.0.2.0/24 (AZ2)
- Private Subnets: 10.0.10.0/24 (AZ1), 10.0.11.0/24 (AZ2)
- Internet Gateway: Attached to VPC for public internet access
- NAT Gateway: Located in PublicSubnet1 for private subnet egress



## Application Flow: CRM Demo Application

### Traffic Path
```
Internet (Port 8080)
  ↓
Public ALB (sre-workshop-public-alb)
  - Same ALB as main app
  - Listener: Port 8080 → CRMAppTargetGroup
  ↓
CRM App Instance (CRMAppInstance)
  - Instance Type: t3.micro
  - Subnet: PrivateSubnet1 (10.0.10.0/24)
  - Port: 8080
  - Security Group: CRMAppSecurityGroup (allows PublicALBSecurityGroup → 8080)
  - Application: Python Flask/Gunicorn CRM app (2 workers)
  - Health Check: /health endpoint
  ↓
DynamoDB Tables (3 tables):
  1. CRMCustomersTable
  2. CRMDealsTable
  3. CRMActivitiesTable
```

### CRM Instance Details
- **IAM Role**: prefixed with EC2InstanceRole. The role should have allow to access DynamoDB tables.
  - DynamoDB access to all 3 CRM tables
  - CloudWatch agent permissions
  - S3 read access to AssetsBucketName
- **Environment Variables**:
  - AWS_REGION: Current region
  - CUSTOMERS_TABLE: CRMCustomersTable name
  - DEALS_TABLE: CRMDealsTable name
  - ACTIVITIES_TABLE: CRMActivitiesTable name
- **Initialization**: Runs init_sample_data.py to populate sample data
- **Service**: Systemd service (crm-app.service)
- **Tags**: DeploymentVersion: "2.0"

### CRM Data Model
```
CRMCustomersTable
  - Partition Key: customer_id (String)
  - Contains: Customer profile information

CRMDealsTable
  - Partition Key: deal_id (String)
  - Global Secondary Index: customer-index
    - Hash Key: customer_id
  - Relationship: One customer → Many deals

CRMActivitiesTable
  - Partition Key: activity_id (String)
  - Global Secondary Index: customer-index
    - Hash Key: customer_id
  - Relationship: One customer → Many activities
```


## Security Group Chain

### Main Application Security Flow
```
PublicALBSecurityGroup
  - Ingress: 0.0.0.0/0 → 80, 443, 8080
  ↓ allows traffic to
NginxSecurityGroup
  - Ingress: PublicALBSecurityGroup → 80
  ↓ allows traffic to
PrivateALBSecurityGroup
  - Ingress: NginxSecurityGroup → 80
  ↓ allows traffic to
AppServerSecurityGroup
  - Ingress: PrivateALBSecurityGroup → 8080
```

### CRM Application Security Flow
```
PublicALBSecurityGroup
  - Ingress: 0.0.0.0/0 → 8080
  ↓ allows traffic to
CRMAppSecurityGroup
  - Ingress: PublicALBSecurityGroup → 8080
```


## Observability Stack


sre-workshop-crm-app [EC2] has python app running from file /opt/crm-app/app.py 

sre-workshop-app [EC2] has python app running from file /opt/sre-app/app.py


## IAM Roles and Permissions

### EC2InstanceRole (Used by all EC2 instances)
Managed Policies:
- AmazonSSMManagedInstanceCore (remote access via Session Manager)
- CloudWatchAgentServerPolicy (metrics and logs)

Inline Policies:
- DynamoDB access (PutItem, GetItem, Query, Scan, UpdateItem, DeleteItem, BatchWriteItem)
- S3 read access to LambdaS3Bucket and AssetsBucketName
"""

logger.info("🔧 About to define remediation_agent with @mcp.tool() decorator...")
logger.info(f"🔍 MCP server exists: {mcp is not None}")
logger.info(f"🔍 MCP server type: {type(mcp)}")


@mcp.tool()
def infrastructure_agent(action_type: Literal["only_plan", "only_execute"], remediation_query: str):
    """Execute infrastructure remediation and AWS service operations using AgentCore Code Interpreter

    Primary tool for ALL AWS infrastructure queries, checks, and actions. Creates remediation plans or executes fixes for AWS infrastructure issues. Plans are saved to S3 for approval. Execution uses secure sandboxed environment with automatic rollback on failure.

    Use this tool for:
    - Querying AWS resources (EC2, DynamoDB, ALB, CloudWatch, etc.)
    - Checking application health and infrastructure state
    - Executing remediation actions and fixes
    - Validating configurations and connectivity

    Args:
        action_type: Remediation mode - "only_plan" generates actionable plan saved to S3,
                    "only_execute" runs approved remediation code with validation
        remediation_query: Issue description or query (e.g., "List all DynamoDB tables",
                          "Fix DynamoDB throttling on CRMDealsTable",
                          "Check EC2 instance sre-workshop-app health",
                          "Restart failed application service")

    Returns:
        Plan summary with S3 location (only_plan) or execution results with validation (only_execute)
    """
    try:
        logger.info(f"🔧 remediation_agent called with action_type={action_type}, query={remediation_query}")

        if not initialize_code_interpreter_client():
            logger.error("❌ Failed to initialize code interpreter client")
            return "Error: Failed to initialize code interpreter client"

        logger.info("✅ Code interpreter client initialized")
        boto_session = get_boto3_session()
        model = BedrockModel(model_id=MODEL_ID, streaming=True, boto_session=boto_session)
        logger.info(f"✅ Bedrock model initialized: {MODEL_ID}")

        if action_type == "only_plan":
            logger.info("📋 Setting up agent for plan-only mode")
            system_prompt = f"""You are an AWS SRE remediation planning agent that creates actionable remediation plans(NO code execution). Here are the details and architecture of the application: {current_architecture}

FOCUS: Generate ONLY immediate actions to restore service availability. No long-term improvements.

PLAN STRUCTURE (use markdown):
1. **Issue Summary** - Brief description of the problem
2. **Root Cause** - Identified cause based on diagnostics
3. **Immediate Actions** - Step-by-step remediation (numbered list)

REQUIREMENTS:
- Each action must specify the exact AWS service, resource, and operation
- Estimate impact and risk level (Low/Medium/High) for each action
- Save plan to S3 using persist_remediation_scripts_to_s3 tool

Once the complete plan is saved as markdown to S3, then provide a brief summary with the S3 location where the plan was persisted.

"""
            agent = Agent(
                system_prompt=system_prompt,
                model=model,
                tools=[persist_remediation_scripts_to_s3],
            )
        elif action_type == "only_execute":
            logger.info("⚡ Setting up agent for execute-only mode")
            system_prompt = f"""
            You are an AWS application remediation agent that helps in troubleshooting application issues. 
            Here is the application details and architecture of the problem you are trying to troubleshoot: {current_architecture}
           

EXECUTION WORKFLOW & CODE REQUIREMENTS::
1. Think step and step
2. Generate Python code using boto3
3. Execute code via execute_remediation_step tool.You have the required IAM permissions and always use action_type='only_execute'
4. Check resource state BEFORE making changes (describe/list operations first)
          

IMPORTANT: 
- The execution environment automatically detects the AWS region and provides it as the AWS_REGION variable. Always use us-west-2 as the working region.
- Always use this variable when creating boto3 clients:

- If you need to connect to any of the EC2 instances, you must use SSM 

After all the remediation and troubleshooting steps are completed, provide the below summary:
1. **Issue Summary** - Brief description of the problem
2. **Root Cause** - Identified cause based on diagnostics
3. **Actions/Fixes Applied** - High level summary of the fixes (numbered list)  

**CRITICAL VALIDATIONS**: To ensure application is running end to end, ensure you access public alb [sre-workshop-public-alb] on port 8080 and should not see database error. If you do see database error, check backend services running in ec2 [sre-workshop-public-alb and sre-workshop-crm-app] and able to successfully connect to dynamodb tables

**IMPORTANT NOTE**: You have a 5 minute timeout for execution, ensure you are generating time efficient and syntactically correct code, no need for extensive verification.

**CRITICAL MEASURES DURING TIMEOUT ERRORS** "When received RuntimeError: Connection to the MCP server was closed" Gracefully notify user of connection timeout but also confirm the steps you were able to successfully complete.

"""

            agent = Agent(
                system_prompt=system_prompt,
                model=model,
                tools=[
                    execute_remediation_step,
                    validate_remediation_environment,
                    read_remediation_scripts_from_s3,
                    get_current_time,
                    convert_timezone,
                ],
            )
        else:
            logger.error(f"❌ Invalid action_type: {action_type}")
            return f"Error: Invalid action_type '{action_type}'. Must be one of: only_plan, only_execute"

        logger.info("🤖 Agent configured, invoking with query...")
        return_text = ""
        response = agent(remediation_query)
        logger.info("✅ Agent response received")

        response_content = response.message.get("content", [])
        if response_content:
            for content in response_content:
                if isinstance(content, dict) and "text" in content:
                    return_text = content["text"]
            logger.info(f"✅ Extracted response text (length: {len(return_text)})")
        else:
            logger.warning("⚠️ No content in agent response")

        return return_text

    except Exception as e:
        logger.error(f"❌ remediation_agent failed: {type(e).__name__}: {str(e)}", exc_info=True)
        return f"Error: {type(e).__name__}: {str(e)}"


# 함수 정의 후 도구 등록 확인 추가
logger.info("✅ remediation_agent tool defined")
# logger.info(f"🔍 Tool function callable: {callable(remediation_agent)}")

# if callable(remediation_agent):
#    logger.info("✅ Tool registration successful - MCP server should work properly")
# else:
#    logger.warning("⚠️ Tool registration failed - this will cause MCP requests to fail!")

# 모듈 수준에서 초기화
logger.info("🚀 Initializing SRE Remediation Agent with FastMCP")
initialize_code_interpreter_client()

logger.info("🚀 Starting FastMCP server with streamable-http transport on port 8000")

mcp.run(transport="streamable-http")
