"""
Lab 02: Lambda 함수 배포 및 구성 헬퍼

처리 항목:
1. ECR 리포지토리 생성
2. IAM 실행 역할 생성
3. 필수 정책 연결
4. 모든 구성을 Parameter Store에 저장

여러 계정과 호환되며, 각 배포는 자체 값을 저장합니다.
"""

import boto3
import json
from lab_helpers.constants import (
    PARAMETER_PATHS,
    LAMBDA_CONFIG,
    ECR_CONFIG,
    IAM_POLICIES,
)
from lab_helpers.parameter_store import put_parameter, store_workshop_metadata
from lab_helpers.config import MODEL_ID, AWS_REGION


def create_ecr_repository(repository_name, region_name=None):
    """
    ECR 리포지토리를 생성하거나 기존 리포지토리를 반환합니다.

    인자:
        repository_name: 리포지토리 이름(예: "aiml301-diagnostic-agent")
        region_name: AWS 리전

    반환:
        ECR 리포지토리 URI
    """
    if region_name is None:
        region_name = AWS_REGION

    ecr = boto3.client("ecr", region_name=region_name)
    boto3.client("sts", region_name=region_name).get_caller_identity()["Account"]  # noqa: F841

    try:
        # 리포지토리가 존재하는지 확인
        response = ecr.describe_repositories(repositoryNames=[repository_name])
        repo_uri = response["repositories"][0]["repositoryUri"]
        print(f"✓ ECR Repository already exists: {repo_uri}")
        return repo_uri
    except ecr.exceptions.RepositoryNotFoundException:
        # 새 리포지토리 생성
        response = ecr.create_repository(repositoryName=repository_name)
        repo_uri = response["repository"]["repositoryUri"]
        print(f"✓ Created ECR Repository: {repo_uri}")
        return repo_uri


def create_lambda_execution_role(role_name, region_name=None):
    """
    필수 정책이 포함된 Lambda 실행 역할을 생성합니다.

    인자:
        role_name: IAM 역할 이름(예: "aiml301-diagnostic-lambda-role")
        region_name: AWS 리전

    반환:
        역할 ARN
    """
    if region_name is None:
        region_name = AWS_REGION

    iam = boto3.client("iam", region_name=region_name)

    # 신뢰 정책: Lambda 서비스가 이 역할을 수임하도록 허용
    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }
        ],
    }

    try:
        # 역할이 존재하는지 확인
        role = iam.get_role(RoleName=role_name)
        role_arn = role["Role"]["Arn"]
        print(f"✓ IAM Role already exists: {role_arn}")
    except iam.exceptions.NoSuchEntityException:
        # 새 역할 생성
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Lambda execution role for AIML301 workshop agent",
        )
        role_arn = role["Role"]["Arn"]
        print(f"✓ Created IAM Role: {role_arn}")

    # CloudWatch Logs 정책 연결(Lambda 기본 실행)
    try:
        iam.attach_role_policy(RoleName=role_name, PolicyArn=IAM_POLICIES["cloudwatch_logs_policy"])
        print("✓ Attached CloudWatch Logs policy")
    except Exception as e:
        print(f"⚠ CloudWatch policy (may already be attached): {e}")

    # Bedrock InvokeModel 정책 연결(Strands agent에 필요한 모든 Bedrock 작업 포함)
    bedrock_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                    "bedrock:Converse",
                    "bedrock:ConverseStream",
                    "aws-marketplace:Subscribe",
                    "aws-marketplace:ViewSubscriptions",
                ],
                "Resource": "*",
            }
        ],
    }

    try:
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName="BedrockInvokePolicy",
            PolicyDocument=json.dumps(bedrock_policy),
        )
        print("✓ Attached Bedrock InvokeModel policy")
    except Exception as e:
        print(f"⚠ Bedrock policy update: {e}")

    return role_arn


def prepare_lambda_build_context(handler_code, build_dir="lambda_diagnostic_agent"):
    """
    Dockerfile 및 requirements.txt가 포함된 Lambda 빌드 컨텍스트를 생성합니다.

    인자:
        handler_code: app.py용 Python 코드(lambda_handler 함수)
        build_dir: 빌드 컨텍스트를 생성할 디렉터리
    """
    import os

    # 빌드 디렉터리 생성
    os.makedirs(build_dir, exist_ok=True)

    # 상수에서 Dockerfile 생성
    dockerfile_content = f"""FROM --platform=linux/amd64 {ECR_CONFIG["base_image"]}

# Copy requirements (to task root)
COPY requirements.txt ${{LAMBDA_TASK_ROOT}}/

# Install dependencies
RUN pip install --no-cache-dir -r ${{LAMBDA_TASK_ROOT}}/requirements.txt

# Copy Lambda handler and helper modules to task root
COPY app.py ${{LAMBDA_TASK_ROOT}}/
COPY lab_helpers ${{LAMBDA_TASK_ROOT}}/lab_helpers

# Set handler
CMD ["app.lambda_handler"]
"""

    # Strands agent 배포에 필요한 패키지
    # 도구 오케스트레이션을 위한 bedrock-agentcore 및 strands-agents 포함
    requirements = """strands-agents==1.12.0
bedrock-agentcore>=0.1.0
bedrock-agentcore-starter-toolkit>=0.1.24
boto3==1.40.65
botocore==1.40.65
pydantic>=2.0
requests>=2.30
"""

    # 파일 쓰기
    with open(f"{build_dir}/Dockerfile", "w") as f:
        f.write(dockerfile_content)

    with open(f"{build_dir}/requirements.txt", "w") as f:
        f.write(requirements)

    with open(f"{build_dir}/app.py", "w") as f:
        f.write(handler_code)

    return {
        "build_dir": build_dir,
        "dockerfile": f"{build_dir}/Dockerfile",
        "requirements": f"{build_dir}/requirements.txt",
        "handler": f"{build_dir}/app.py",
    }


def setup_lab_02_infrastructure(handler_code, region_name=None):
    """
    Lab 02 인프라 설정을 완료합니다.
    1. Lambda 사양 표시
    2. Lambda 빌드 컨텍스트 생성(Dockerfile, requirements.txt, app.py)
    3. ECR 리포지토리 생성
    4. Lambda 실행 역할 생성
    5. 모든 값을 Parameter Store에 저장

    인자:
        handler_code: Lambda 핸들러용 Python 코드(app.py)
        region_name: AWS 리전(None이면 config.AWS_REGION 사용)

    반환:
        생성된 모든 리소스가 포함된 딕셔너리
    """
    if region_name is None:
        region_name = AWS_REGION

    print("=" * 70)
    print("SETTING UP LAB 02 INFRASTRUCTURE")
    print("=" * 70)
    print()

    # Lambda 사양 표시
    print("Lambda Function Specifications:")
    print(f"  Memory: {LAMBDA_CONFIG['memory_size']}MB (2GB for Strands agent)")
    print(f"  Timeout: {LAMBDA_CONFIG['timeout']}s")
    print(f"  Base Image: {ECR_CONFIG['base_image']}")
    print()

    # Lambda 빌드 컨텍스트 준비(Dockerfile, requirements.txt, app.py 생성)
    print("Preparing Lambda build context...")
    build_context = prepare_lambda_build_context(handler_code)
    print(f"✓ Created build directory: {build_context['build_dir']}")
    print("✓ Created Dockerfile")
    print("✓ Created requirements.txt")
    print("✓ Created app.py (Lambda handler)")
    print()

    # 계정 ID 조회
    sts = boto3.client("sts", region_name=region_name)
    account_id = sts.get_caller_identity()["Account"]
    print(f"AWS Account: {account_id}")
    print(f"AWS Region: {region_name}")
    print()

    # 워크숍 메타데이터 저장
    print("Storing workshop metadata...")
    store_workshop_metadata(account_id, region_name, region_name)
    print()

    # ECR 리포지토리 생성
    print("Setting up ECR repository...")
    repository_name = "aiml301-diagnostic-agent"
    ecr_repository_uri = create_ecr_repository(repository_name, region_name)
    print()

    # Lambda 실행 역할 생성
    print("Setting up Lambda execution role...")
    role_name = "aiml301-diagnostic-lambda-role"
    lambda_role_arn = create_lambda_execution_role(role_name, region_name)
    print()

    # Parameter Store에 구성 저장
    print("Storing configuration in Parameter Store...")
    put_parameter(
        PARAMETER_PATHS["lab_02"]["ecr_repository_uri"],
        ecr_repository_uri,
        description="ECR repository URI for Lab 02 diagnostic agent",
        region_name=region_name,
    )
    put_parameter(
        PARAMETER_PATHS["lab_02"]["ecr_repository_name"],
        repository_name,
        description="ECR repository name for Lab 02",
        region_name=region_name,
    )
    put_parameter(
        PARAMETER_PATHS["lab_02"]["lambda_role_arn"],
        lambda_role_arn,
        description="Lambda execution role ARN for Lab 02",
        region_name=region_name,
    )
    print()

    # 구성 반환
    config = {
        "account_id": account_id,
        "region": region_name,
        "ecr_repository_uri": ecr_repository_uri,
        "ecr_repository_name": repository_name,
        "lambda_role_arn": lambda_role_arn,
        "lambda_memory": LAMBDA_CONFIG["memory_size"],
        "lambda_timeout": LAMBDA_CONFIG["timeout"],
    }

    print("=" * 70)
    print("LAB 02 INFRASTRUCTURE SETUP COMPLETE")
    print("=" * 70)
    print()
    print("Configuration Summary:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    print()
    print("✓ All values stored in Parameter Store")
    print("✓ Ready for Lambda container deployment")
    print()

    return config


def get_lab_02_deployment_instructions(config):
    """
    Lambda 배포용 Docker 및 AWS CLI 명령을 생성합니다.

    인자:
        config: setup_lab_02_infrastructure에서 반환된 구성 딕셔너리

    반환:
        배포 지침이 포함된 서식 지정 문자열
    """
    ecr_uri = config["ecr_repository_uri"]
    role_arn = config["lambda_role_arn"]
    region = config["region"]

    instructions = f"""
╔════════════════════════════════════════════════════════════════════╗
║        LAB 02: DOCKER BUILD & LAMBDA DEPLOYMENT STEPS             ║
╚════════════════════════════════════════════════════════════════════╝

📦 DOCKER BUILD (Run locally or in CI/CD):

1. Build Docker image:
   docker build --provenance=false -t aiml301-diagnostic-agent:latest ./lambda_diagnostic_agent/

2. Authenticate Docker to ECR:
   aws ecr get-login-password --region {region} | docker login --username AWS --password-stdin {ecr_uri.rsplit("/", 1)[0]}

3. Tag image:
   docker tag aiml301-diagnostic-agent:latest {ecr_uri}

4. Push to ECR:
   docker push {ecr_uri}

🚀 LAMBDA DEPLOYMENT (Run after Docker image is pushed):

5. Create Lambda function:
   aws lambda create-function \\
     --function-name aiml301-diagnostic-agent \\
     --role {role_arn} \\
     --code ImageUri={ecr_uri} \\
     --package-type Image \\
     --timeout {LAMBDA_CONFIG["timeout"]} \\
     --memory-size {LAMBDA_CONFIG["memory_size"]} \\
     --region {region}

6. Update Lambda environment variables (optional):
   aws lambda update-function-configuration \\
     --function-name aiml301-diagnostic-agent \\
     --environment Variables={{MODEL_ID={MODEL_ID},REGION={region}}} \\
     --region {region}

📝 NOTES:
   - Image URI: {ecr_uri}
   - Role ARN: {role_arn}
   - Memory: {LAMBDA_CONFIG["memory_size"]}MB (2GB for Strands agent)
   - Timeout: {LAMBDA_CONFIG["timeout"]}s
   - All values are stored in Parameter Store at: /aiml301/lab-02/*
"""

    return instructions


def show_lambda_config():
    """Lambda 구성 상수를 표시합니다."""
    print("Lambda Configuration Constants:")
    print(f"  Memory: {LAMBDA_CONFIG['memory_size']}MB")
    print(f"  Timeout: {LAMBDA_CONFIG['timeout']}s")
    print(f"  Ephemeral Storage: {LAMBDA_CONFIG['ephemeral_storage']}MB")
    print()
    print("Base Image:")
    print(f"  {ECR_CONFIG['base_image']}")
    print()
    print("Model ID (from config.py):")
    print(f"  {MODEL_ID}")


# ============================================================================
# ZIP 배포 지원(Docker를 대체하는 VPC 친화적 방식)
# ============================================================================


def get_zip_deployment_instructions(config):
    """
    ZIP 기반 Lambda 배포 지침을 생성합니다.

    인자:
        config: 구성 딕셔너리

    반환:
        ZIP 배포 지침이 포함된 서식 지정 문자열
    """
    region = config["region"]
    role_arn = config["lambda_role_arn"]

    instructions = f"""
╔════════════════════════════════════════════════════════════════════╗
║          LAB 02: ZIP-BASED LAMBDA DEPLOYMENT (VPC-Friendly)       ║
╚════════════════════════════════════════════════════════════════════╝

📦 ZIP PACKAGE CREATION & DEPLOYMENT:

ONE-LINE DEPLOYMENT (recommended):
   bash lab_helpers/lab_02/deploy.sh

This handles everything:
   ✓ Creates IAM role
   ✓ Installs dependencies for Python 3.11
   ✓ Packages lib/ and lab_helpers/
   ✓ Creates ZIP (direct upload if <50MB, S3 if larger)
   ✓ Deploys Lambda function
   ✓ Saves configuration to Parameter Store

ALTERNATIVE: Using Python packager directly:
   from lab_helpers.lab_02.lambda_packager import setup_lambda_zip_deployment

   handler_code = '''... your app.py code ...'''
   requirements_content = '''... pip requirements ...'''

   result = setup_lambda_zip_deployment(handler_code, requirements_content)

🚀 ADVANTAGES OVER DOCKER:

✓ Works in SageMaker VPC mode (no Docker daemon needed)
✓ Faster deployment (8 min vs 12 min with Docker)
✓ No external network access required
✓ Simpler setup (Python + pip only)
✓ Package size: ~30-35 MB (well under 250 MB limit)

📊 DEPLOYMENT OPTIONS:

Size < 50 MB:  Direct ZIP upload to Lambda
Size > 50 MB:  S3 upload → Lambda
Our package:   ~30-35 MB (uses direct upload by default)

📝 CONFIGURATION:

   - Role ARN: {role_arn}
   - Region: {region}
   - Memory: {LAMBDA_CONFIG["memory_size"]}MB
   - Timeout: {LAMBDA_CONFIG["timeout"]}s
   - All values stored in Parameter Store at: /aiml301/lab-02/*
"""

    return instructions


def show_deployment_methods():
    """사용 가능한 배포 방식과 각 특성을 표시합니다."""
    from lab_helpers.constants import DEPLOYMENT_METHODS

    print("\n" + "=" * 70)
    print("LAMBDA DEPLOYMENT METHODS")
    print("=" * 70)

    for method_name, method_info in DEPLOYMENT_METHODS.items():
        print(f"\n{method_name.upper()}:")
        print(f"  Description: {method_info['description']}")
        print(f"  Requires: {', '.join(method_info['requires'])}")
        print(f"  VPC-Compatible: {'✅ Yes' if method_info['vpc_compatible'] else '❌ No'}")
        print(f"  Size Limit: {method_info['size_limit']}")
