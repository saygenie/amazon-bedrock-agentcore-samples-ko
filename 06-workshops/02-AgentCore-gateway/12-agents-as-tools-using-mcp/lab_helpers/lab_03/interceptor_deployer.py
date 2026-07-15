"""AgentCore Gateway용 Lambda 인터셉터를 배포합니다."""

import json
import zipfile
import io
import time
import boto3


def deploy_interceptor(region: str, prefix: str, gateway_arn: str = None) -> str:
    """
    Lambda 인터셉터 함수를 배포합니다.

    인자:
        region: AWS 리전
        prefix: 리소스 이름 접두사
        gateway_arn: Lambda 권한에 사용할 Gateway ARN(선택 사항)

    반환:
        function_arn: 배포된 Lambda 함수의 ARN
    """
    lambda_client = boto3.client("lambda", region_name=region)
    iam_client = boto3.client("iam", region_name=region)

    function_name = f"{prefix}-interceptor-request"
    role_name = f"{prefix}-interceptor-role"

    # IAM 역할 생성
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
        role_response = iam_client.create_role(RoleName=role_name, AssumeRolePolicyDocument=json.dumps(trust_policy))
        role_arn = role_response["Role"]["Arn"]

        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )
        print(f"✅ IAM role created: {role_arn}")
        time.sleep(10)  # 역할 전파 대기

    except iam_client.exceptions.EntityAlreadyExistsException:
        role_arn = iam_client.get_role(RoleName=role_name)["Role"]["Arn"]
        print(f"ℹ️  Using existing role: {role_arn}")

    # 배포 패키지 생성
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.write("lab_helpers/lab_03/interceptor-request.py", "lambda_function.py")

    zip_buffer.seek(0)

    # 기존 Lambda가 있으면 삭제
    try:
        lambda_client.get_function(FunctionName=function_name)
        print(f"🗑️  Deleting existing Lambda: {function_name}")
        lambda_client.delete_function(FunctionName=function_name)
        time.sleep(2)
    except lambda_client.exceptions.ResourceNotFoundException:
        pass

    # Lambda 생성
    response = lambda_client.create_function(
        FunctionName=function_name,
        Runtime="python3.11",
        Role=role_arn,
        Handler="lambda_function.lambda_handler",
        Code={"ZipFile": zip_buffer.getvalue()},
        Timeout=30,
        MemorySize=256,
    )
    function_arn = response["FunctionArn"]
    print(f"✅ Lambda created: {function_arn}")

    # Gateway가 Lambda를 호출할 수 있는 권한 추가
    lambda_client.add_permission(
        FunctionName=function_name,
        StatementId="AllowGatewayInvoke",
        Action="lambda:InvokeFunction",
        Principal="bedrock-agentcore.amazonaws.com",
        SourceArn=f"arn:aws:bedrock-agentcore:us-east-1:{boto3.client('sts').get_caller_identity()['Account']}:gateway/*",
    )
    print("✅ Lambda permission added for all gateways in account")

    return function_arn
