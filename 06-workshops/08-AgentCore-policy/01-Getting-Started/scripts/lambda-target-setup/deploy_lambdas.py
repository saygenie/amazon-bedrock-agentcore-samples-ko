"""
Lambda 함수를 배포하고 ARN을 config.json에 저장합니다.

사용법:
    python deploy_lambdas.py --region REGION [--role-arn ROLE_ARN]

예시:
    # 기존 역할 사용
    python deploy_lambdas.py --region us-west-2 --role-arn arn:aws:iam::123456789012:role/MyLambdaRole

    # 새 역할 자동 생성
    python deploy_lambdas.py --region us-west-2
"""

import argparse
import boto3
import zipfile
import io
import os
import json
import sys
import time


def get_or_create_lambda_role(iam_client):
    """Lambda 실행용 IAM 역할을 가져오거나 생성합니다."""
    role_name = "AgentCoreLambdaExecutionRole"

    try:
        response = iam_client.get_role(RoleName=role_name)
        print(f"   ✅ Using existing IAM role: {role_name}")
        return response["Role"]["Arn"], False
    except iam_client.exceptions.NoSuchEntityException:
        print(f"   📝 Creating IAM role: {role_name}")

        # Lambda용 신뢰 정책
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

        # 역할 생성
        response = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Execution role for AgentCore Lambda functions",
        )

        # 기본 Lambda 실행 정책 연결
        iam_client.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )

        print(f"   ✅ IAM role created: {role_name}")
        print("   ⏳ Waiting 10 seconds for IAM propagation...")
        return response["Role"]["Arn"], True


def deploy_lambda(lambda_client, function_name, js_file, role_arn):
    """JS 파일에서 Lambda 함수를 배포합니다."""

    print(f"📦 Deploying {function_name}...")

    # JS 파일 읽기
    script_dir = os.path.dirname(os.path.abspath(__file__))
    js_path = os.path.join(script_dir, js_file)

    with open(js_path, "r") as f:
        code_content = f.read()

    # 메모리에서 코드를 index.mjs(ES 모듈)로 포함하는 zip 파일 생성
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("index.mjs", code_content)

    zip_buffer.seek(0)
    zip_content = zip_buffer.read()

    try:
        # 함수 생성 시도
        response = lambda_client.create_function(
            FunctionName=function_name,
            Runtime="nodejs20.x",
            Role=role_arn,
            Handler="index.handler",
            Code={"ZipFile": zip_content},
            Description=f"AgentCore {function_name}",
            Timeout=30,
            MemorySize=256,
        )

        print("   ✅ Lambda created")
        print(f"   ARN: {response['FunctionArn']}")
        return response["FunctionArn"]

    except lambda_client.exceptions.ResourceConflictException:
        # 함수가 이미 있으면 업데이트
        print("   ℹ️  Function exists, updating code...")

        response = lambda_client.update_function_code(FunctionName=function_name, ZipFile=zip_content)

        print("   ✅ Code updated")
        print(f"   ARN: {response['FunctionArn']}")
        return response["FunctionArn"]

    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None


def save_config(lambda_arns, region, output_file="config.json"):
    """Lambda ARN을 Getting-Started 디렉터리의 config.json에 저장합니다."""

    # 스크립트 디렉터리 가져오기(lambda-target-setup)
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Getting-Started 디렉터리로 이동: lambda-target-setup -> scripts -> Getting-Started
    getting_started_dir = os.path.dirname(os.path.dirname(script_dir))
    config_path = os.path.join(getting_started_dir, output_file)

    config = {"lambdas": lambda_arns, "region": region}

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n💾 Configuration saved to: {config_path}")


def main():
    print("🚀 Deploying Lambda Functions\n")
    print("=" * 70)

    # 인수 파싱
    parser = argparse.ArgumentParser(description="Deploy Lambda functions for AgentCore Policy demo")
    parser.add_argument("--region", type=str, default=None, help="AWS region to deploy into")
    parser.add_argument("--role-arn", type=str, default=None, help="IAM role ARN for Lambda execution")
    args = parser.parse_args()

    # 리전 결정
    region = args.region
    if not region:
        session = boto3.Session()
        region = session.region_name
    if not region:
        region = input("Enter AWS region (e.g., us-east-1, us-west-2): ").strip()
        if not region:
            print("❌ Error: AWS region is required")
            sys.exit(1)

    print(f"\nRegion: {region}")

    # AWS 클라이언트 초기화
    lambda_client = boto3.client("lambda", region_name=region)
    iam_client = boto3.client("iam", region_name=region)

    if args.role_arn:
        role_arn = args.role_arn

        # 역할 ARN 형식 검증
        if not role_arn.startswith("arn:aws:iam::"):
            print(f"\n❌ Error: Invalid role ARN format: {role_arn}")
            print("Expected format: arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME")
            print("\n" + "=" * 70)
            sys.exit(1)

        print(f"\n🔐 Using provided IAM role: {role_arn}")
        print()
        newly_created = False
    else:
        # 역할이 제공되지 않았으면 새로 생성
        print("\n🔐 No role provided, setting up IAM role...")
        role_arn, newly_created = get_or_create_lambda_role(iam_client)
        print()

        # 역할을 방금 생성했으면 IAM 전파 대기
        if newly_created:
            time.sleep(10)

    # 각 함수 배포
    functions = [
        ("ApplicationTool", "application_tool.js"),
        ("ApprovalTool", "approval_tool.js"),
        ("RiskModelTool", "risk_model_tool.js"),
    ]

    lambda_arns = {}

    for function_name, js_file in functions:
        arn = deploy_lambda(lambda_client, function_name, js_file, role_arn)
        if arn:
            lambda_arns[function_name] = arn
        print()
        # 배포 사이에 잠시 대기
        time.sleep(1)

    # 구성 저장
    if lambda_arns:
        save_config(lambda_arns, region)

    print("=" * 70)
    print(f"\n✅ Deployment complete! {len(lambda_arns)}/3 functions deployed.")
    print("\nLambda ARNs have been saved to config.json")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
