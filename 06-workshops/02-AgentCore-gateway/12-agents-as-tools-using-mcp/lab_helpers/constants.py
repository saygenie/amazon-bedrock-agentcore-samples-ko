"""
모든 AWS Systems Manager Parameter Store 경로의 중앙 레지스트리
전체 Lab의 배포 및 조회 헬퍼에서 사용합니다.

파라미터 이름을 일관되고 검색 및 버전 관리가 가능하게 유지합니다.
Notebook이나 헬퍼 함수에 값을 하드코딩하지 않습니다.
"""

# Workshop 전체 이름 지정 규칙
WORKSHOP_NAME = "aiml301-sre-agentcore"
WORKSHOP_PREFIX = "/aiml301"

# Parameter Store 경로 구조
PARAMETER_PATHS = {
    "workshop": {
        "account_id": "/aiml301/workshop/account-id",
        "region": "/aiml301/workshop/region",
    },
    # Lab 1: 사전 요구 사항 - Cognito 설정(Lab 3~5 인증용)
    "cognito": {
        "user_pool_id": "/aiml301/cognito/user-pool-id",
        "user_pool_name": "/aiml301/cognito/user-pool-name",
        "user_pool_arn": "/aiml301/cognito/user-pool-arn",
        "domain": "/aiml301/cognito/domain",
        "token_endpoint": "/aiml301/cognito/token-endpoint",
        "user_auth_client_id": "/aiml301/cognito/user-auth-client-id",
        "user_auth_client_name": "/aiml301/cognito/user-auth-client-name",
        "m2m_client_id": "/aiml301/cognito/m2m-client-id",
        "m2m_client_secret": "/aiml301/cognito/m2m-client-secret",
        "m2m_client_name": "/aiml301/cognito/m2m-client-name",
        "resource_server_id": "/aiml301/cognito/resource-server-id",
        "resource_server_identifier": "/aiml301/cognito/resource-server-identifier",
        "test_user_email": "/aiml301/cognito/test-user-email",
        "test_user_password": "/aiml301/cognito/test-user-password",
        "approver_user_email": "/aiml301/cognito/approver-user-email",
        "approver_user_password": "/aiml301/cognito/approver-user-password",
    },
    # Lab 1.5: Memory 설정(Cognito 이후 생성, Lab 2~5에서 사용)
    "memory": {
        "memory_id": "/aiml301/memory/id",
        "memory_name_prefix": "SREAgent_STM",
        "default_session_id": "/aiml301/memory/default-session-id",
    },
    # Lab 2: 진단 에이전트
    "lab_02": {
        "ecr_repository_uri": "/aiml301/lab-02/ecr-repository-uri",
        "ecr_repository_name": "/aiml301/lab-02/ecr-repository-name",
        "lambda_role_arn": "/aiml301/lab-02/lambda-role-arn",
        "lambda_function_arn": "/aiml301/lab-02/lambda-function-arn",
        "lambda_function_name": "/aiml301/lab-02/lambda-function-name",
        "gateway_id": "/aiml301/lab-02/gateway-id",
        "gateway_url": "/aiml301/lab-02/gateway-url",
        "gateway_role_arn": "/aiml301/lab-02/gateway-role-arn",
    },
    # Lab 3: 교정 에이전트(M2M 인증을 사용하는 AgentCore Runtime + Gateway)
    "lab_03": {
        # Code Interpreter 구성
        "code_interpreter_id": "/aiml301_sre_agentcore/lab-03/code-interpreter-id",
        "code_interpreter_arn": "/aiml301_sre_agentcore/lab-03/code-interpreter-arn",
        "code_interpreter_role_arn": "/aiml301_sre_agentcore/lab-03/code-interpreter-role-arn",
        # Runtime 구성
        "runtime_role_arn": "/aiml301_sre_agentcore/lab-03/runtime-role-arn",
        "runtime_id": "/aiml301_sre_agentcore/lab-03/runtime-id",
        "runtime_arn": "/aiml301_sre_agentcore/lab-03/runtime-arn",
        "runtime_config": "/aiml301_sre_agentcore/lab-03/runtime-config",
        # Gateway 구성
        "gateway_role_arn": "/aiml301_sre_agentcore/lab-03/gateway-role-arn",
        "gateway_id": "/aiml301_sre_agentcore/lab-03/gateway-id",
        "gateway_config": "/aiml301_sre_agentcore/lab-03/gateway-config",
        # OAuth2 M2M 인증
        "oauth2_provider_arn": "/aiml301/lab-03/oauth2-provider-arn",
        "oauth2_secret_arn": "/aiml301/lab-03/oauth2-secret-arn",
        "oauth2_config": "/aiml301/lab-03/oauth2-config",
        # Gateway 대상(Runtime)
        "gateway_runtime_target": "/aiml301_sre_agentcore/lab-03/gateway-runtime-target",
        "gateway_m2m_target": "/aiml301/lab-03/gateway-m2m-target",
        "m2m_auth_config": "/aiml301/lab-03/m2m-auth-complete-config",
    },
    # Lab 3B: 세분화된 접근 제어를 사용하는 교정 에이전트
    "lab_03b": {
        "interceptor_function_arn": "/aiml301/lab-03b/interceptor-function-arn",
        "gateway_id": "/aiml301/lab-03b/gateway-id",
        "gateway_url": "/aiml301/lab-03b/gateway-url",
    },
    # Lab 4: 예방 에이전트(M2M 인증을 사용하는 AgentCore Runtime + Gateway)
    "lab_04": {
        # Runtime 구성
        "runtime_role_arn": "/aiml301_sre_agentcore/lab-04/runtime-role-arn",
        "runtime_id": "/aiml301_sre_agentcore/lab-04/runtime-id",
        "runtime_arn": "/aiml301_sre_agentcore/lab-04/runtime-arn",
        "runtime_config": "/aiml301_sre_agentcore/lab-04/runtime-config",
        # Gateway 구성
        "gateway_role_arn": "/aiml301_sre_agentcore/lab-04/gateway-role-arn",
        "gateway_id": "/aiml301_sre_agentcore/lab-04/gateway-id",
        "gateway_config": "/aiml301_sre_agentcore/lab-04/gateway-config",
        # OAuth2 M2M 인증
        "oauth2_provider_arn": "/aiml301/lab-04/oauth2-provider-arn",
        "oauth2_secret_arn": "/aiml301/lab-04/oauth2-secret-arn",
        "oauth2_config": "/aiml301/lab-04/oauth2-config",
        # Gateway 대상(Runtime)
        "gateway_runtime_target": "/aiml301_sre_agentcore/lab-04/gateway-runtime-target",
        "gateway_m2m_target": "/aiml301/lab-04/gateway-m2m-target",
        "m2m_auth_config": "/aiml301/lab-04/m2m-auth-complete-config",
    },
    # Lab 5: 멀티 에이전트 오케스트레이션(Supervisor 에이전트)
    "lab_05": {
        # Runtime 구성
        "runtime_role_arn": "/aiml301_sre_agentcore/lab-05/runtime-role-arn",
        "runtime_id": "/aiml301_sre_agentcore/lab-05/runtime-id",
        "runtime_arn": "/aiml301_sre_agentcore/lab-05/runtime-arn",
        "runtime_config": "/aiml301_sre_agentcore/lab-05/runtime-config",
        # Gateway 구성
        "gateway_role_arn": "/aiml301_sre_agentcore/lab-05/gateway-role-arn",
        "gateway_id": "/aiml301_sre_agentcore/lab-05/gateway-id",
        "gateway_url": "/aiml301_sre_agentcore/lab-05/gateway-url",
        "gateway_config": "/aiml301_sre_agentcore/lab-05/gateway-config",
        # Gateway 대상(Supervisor Runtime)
        "gateway_runtime_target": "/aiml301_sre_agentcore/lab-05/gateway-runtime-target",
    },
    # Lab 6: 사용자 지정 인터셉터(선택 사항)
    "lab_06": {
        "interceptor_role_arn": "/aiml301/lab-06/interceptor-role-arn",
    },
    # Lab 7: Memory 통합(선택 사항)
    "lab_07": {
        "memory_store_arn": "/aiml301/lab-07/memory-store-arn",
    },
}

# Lambda 함수 구성(고정 사양)
LAMBDA_CONFIG = {
    "memory_size": 2048,  # MB(Strands 에이전트 + 모델 추론용 2GB)
    "timeout": 300,  # 초(Strands 에이전트 추론용 5분)
    "ephemeral_storage": 512,  # MB (/tmp)
}

# ECR 이미지 구성
ECR_CONFIG = {
    "base_image": "public.ecr.aws/lambda/python:3.12",
    "image_tag": "latest",
}

# IAM policy 상수
IAM_POLICIES = {
    "cloudwatch_logs_policy": "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
}

# Bedrock 관련 상수
BEDROCK_CONFIG = {
    "invoke_policy_action": "bedrock:InvokeModel",
    # MODEL_ID는 config.py에서 관리하며 필요할 때 deployer에서 가져옴
}

# ZIP 기반 Lambda 배포용 S3 구성
S3_CONFIG = {
    "bucket_name": "aiml301-lambda-packages",
    "lambda_packages_prefix": "lambda-packages/",
    "default_object_prefix": "lambda-packages/diagnostic-agent.zip",
}

# 배포 방식 옵션
DEPLOYMENT_METHODS = {
    "docker": {
        "description": "Docker image → ECR → Lambda (original approach)",
        "requires": ["docker", "ecr"],
        "vpc_compatible": False,
        "size_limit": "10GB (container limit)",
    },
    "zip_direct": {
        "description": "ZIP file → Direct Lambda upload (<50MB)",
        "requires": ["python", "pip", "aws_cli"],
        "vpc_compatible": True,
        "size_limit": "50 MB (direct upload limit)",
    },
    "zip_s3": {
        "description": "ZIP file → S3 → Lambda (recommended)",
        "requires": ["python", "pip", "aws_cli", "s3"],
        "vpc_compatible": True,
        "size_limit": "250 MB (S3 limit)",
    },
}
