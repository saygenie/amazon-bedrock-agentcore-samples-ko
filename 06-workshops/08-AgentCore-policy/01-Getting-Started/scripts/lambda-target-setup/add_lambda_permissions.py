"""
Gateway에서 호출할 수 있도록 Lambda 함수에 리소스 기반 권한을 추가합니다.
Gateway 호출 문제를 해결하는 가장 일반적인 방법입니다.
"""

import boto3
import json


def add_lambda_permissions():
    """Gateway에서 Lambda 함수를 호출할 수 있도록 권한을 추가합니다."""

    print("🔧 Adding Lambda Permissions for Gateway\n")
    print("=" * 70)

    # Gateway 구성 로드
    with open("gateway_config.json", "r") as f:
        gateway_config = json.load(f)

    region = gateway_config["region"]
    gateway_arn = gateway_config["gateway_arn"]
    gateway_account = gateway_arn.split(":")[4]

    print(f"Gateway ARN: {gateway_arn}\n")

    # Lambda 클라이언트 초기화
    lambda_client = boto3.client("lambda", region_name=region)

    # 업데이트할 Lambda 함수
    functions = ["ApplicationTool", "RiskModelTool", "ApprovalTool"]

    for function_name in functions:
        print(f"🔧 {function_name}:")

        try:
            # 함수가 있는지 확인
            lambda_client.get_function(FunctionName=function_name)

            # 권한 추가 시도
            try:
                lambda_client.add_permission(
                    FunctionName=function_name,
                    StatementId="AllowAgentCoreGateway",
                    Action="lambda:InvokeFunction",
                    Principal="bedrock-agentcore.amazonaws.com",
                    SourceArn=gateway_arn,
                )
                print("   ✅ Permission added successfully")

            except lambda_client.exceptions.ResourceConflictException:
                print("   ℹ️  Permission already exists")

                # 기존 권한을 제거한 후 다시 추가하여 업데이트 시도
                try:
                    lambda_client.remove_permission(FunctionName=function_name, StatementId="AllowAgentCoreGateway")

                    lambda_client.add_permission(
                        FunctionName=function_name,
                        StatementId="AllowAgentCoreGateway",
                        Action="lambda:InvokeFunction",
                        Principal="bedrock-agentcore.amazonaws.com",
                        SourceArn=gateway_arn,
                    )
                    print("   ✅ Permission updated successfully")

                except Exception as update_error:
                    print(f"   ⚠️  Could not update permission: {update_error}")

        except lambda_client.exceptions.ResourceNotFoundException:
            print(f"   ❌ Function not found in account {gateway_account}")
            print("   → Deploy Lambda first")

        except Exception as e:
            print(f"   ❌ Error: {e}")

        print()

    print("=" * 70)
    print("\n✅ Permission update complete!")
    print("\nNext steps:")
    print("1. Test gateway invocation")
    print("2. If still failing, check CloudWatch logs for the Lambda functions")
    print("3. Verify gateway IAM role has lambda:InvokeFunction permission")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    add_lambda_permissions()
