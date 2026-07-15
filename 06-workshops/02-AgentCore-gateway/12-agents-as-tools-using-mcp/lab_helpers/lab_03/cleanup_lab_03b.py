"""
Lab 03B: 세분화된 액세스 제어 리소스 정리

Lab 3A 기본 리소스는 보존하면서 Lab 3B 전용 리소스를 제거합니다.

삭제하는 AWS 리소스:
- JWT 인증을 사용하는 AgentCore Gateway(interceptor-gateway-jwt-*)
- Gateway 대상
- Lambda 인터셉터 함수
- Lambda 실행 역할

보존하는 AWS 리소스:
- AgentCore Runtime(Lab 3A에서 재사용)
- Cognito User Pool 및 사용자
- OAuth2 Credential Provider
- Parameter Store 항목
"""

import boto3
import time


def cleanup_lab_03b(region_name: str = "us-east-1", verbose: bool = True) -> None:
    """
    Lab 3B 리소스(JWT Gateway 및 Lambda 인터셉터)를 정리합니다.

    Lab 3A 리소스(Runtime, Cognito, OAuth2 provider)는 보존합니다.

    인자:
        region_name: AWS 리전
        verbose: 상세 상태 출력 여부
    """
    print("🧹 Cleaning up Lab 3B resources...\n")
    print("=" * 70)

    agentcore_client = boto3.client("bedrock-agentcore-control", region_name=region_name)
    lambda_client = boto3.client("lambda", region_name=region_name)
    iam_client = boto3.client("iam")
    ssm_client = boto3.client("ssm", region_name=region_name)  # noqa: F841

    # 1. JWT 인증을 사용하는 Gateway 삭제
    print("[1/3] Deleting Lab 3B Gateway...")
    try:
        gateways = agentcore_client.list_gateways()
        for gw in gateways.get("items", []):
            if "interceptor-gateway-jwt" in gw.get("name", ""):
                gateway_id = gw["gatewayId"]
                gateway_name = gw.get("name", "N/A")

                print(f"  Found gateway: {gateway_name}")

                # 대상을 먼저 삭제
                targets = agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
                for target in targets.get("items", []):
                    target_id = target["targetId"]
                    agentcore_client.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
                    print(f"    ✓ Deleted target: {target_id}")

                # 대상 삭제 대기
                if targets.get("items"):
                    print("  ⏳ Waiting for targets to be deleted...")
                    for _ in range(30):
                        time.sleep(2)
                        check = agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
                        if len(check.get("items", [])) == 0:
                            break

                # Gateway 삭제
                agentcore_client.delete_gateway(gatewayIdentifier=gateway_id)
                print(f"  ✓ Gateway deleted: {gateway_name}")
                break
        else:
            print("  ✓ Gateway not found (ok)")
    except Exception as e:
        print(f"  ⚠ Gateway cleanup error: {e}")

    # 2. Lambda 인터셉터 삭제
    print("[2/3] Deleting Lambda interceptor...")
    try:
        function_name = "aiml301_sre_agentcore-interceptor-request"
        try:
            lambda_client.delete_function(FunctionName=function_name)
            print(f"  ✓ Lambda deleted: {function_name}")
        except lambda_client.exceptions.ResourceNotFoundException:
            print("  ✓ Lambda not found (ok)")
    except Exception as e:
        print(f"  ⚠ Lambda cleanup error: {e}")

    # 3. Lambda 실행 역할 삭제
    print("[3/3] Deleting Lambda execution role...")
    try:
        role_name = "aiml301_sre_agentcore-interceptor-role"
        try:
            # 정책 분리
            policies = iam_client.list_attached_role_policies(RoleName=role_name)
            for policy in policies.get("AttachedPolicies", []):
                iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])

            # 인라인 정책 삭제
            inline = iam_client.list_role_policies(RoleName=role_name)
            for policy_name in inline.get("PolicyNames", []):
                iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

            # 역할 삭제
            iam_client.delete_role(RoleName=role_name)
            print(f"  ✓ IAM role deleted: {role_name}")
        except iam_client.exceptions.NoSuchEntityException:
            print("  ✓ IAM role not found (ok)")
    except Exception as e:
        print(f"  ⚠ IAM role cleanup error: {e}")

    print("\n" + "=" * 70)
    print("✅ Lab 3B cleanup complete")
    print("\nPreserved resources:")
    print("  ✓ AgentCore Runtime (from Lab 3A)")
    print("  ✓ Cognito User Pool and users")
    print("  ✓ OAuth2 Credential Provider")
    print("  ✓ Parameter Store entries")
