"""
05_agentic_consumer_discovery.ipynb 정리 스크립트입니다.
노트북 데모 중에 생성된 모든 AWS 리소스를 역순으로 삭제합니다.

사용법(노트북에서 실행):
    %run cleanup.py

모든 변수는 노트북 커널에서 가져온다고 가정합니다. 데모 도중 커널이 재시작되더라도
정리 작업을 계속할 수 있도록 각 섹션을 보호합니다.
"""

import os
import time
import shutil
import boto3

# 커널이 재시작되었을 경우 AWS 클라이언트 다시 생성
try:
    cp_client
except NameError:
    session = boto3.Session()
    region = session.region_name or "us-west-2"
    cp_client = session.client("bedrock-agentcore-control")
    iam_client = session.client("iam")
    lambda_client = session.client("lambda")
    cognito_client = session.client("cognito-idp")
    sm_client = session.client("secretsmanager")


# 노트북 변수를 안전하게 확인합니다. 커널이 재시작되었다면 일부 변수가 없을 수 있습니다.
# 참고: %run -i는 노트북 변수를 실행 네임스페이스에 주입하지만, 일부 IPython 버전에서는
# locals().get() / globals().get()으로 변수를 안정적으로 찾지 못할 수 있으므로
# try/except와 직접 변수 참조를 사용합니다.
def _safe_get(name):
    """노트북 네임스페이스에서 변수를 가져오고, 설정되지 않았으면 None을 반환합니다."""
    # 먼저 IPython 사용자 네임스페이스 확인(%run -i에서 가장 안정적)
    try:
        ip = get_ipython()
        if name in ip.user_ns:
            return ip.user_ns[name]
    except NameError:
        pass
    # 프레임의 지역/전역 변수로 대체
    import inspect

    frame = inspect.currentframe().f_back
    try:
        if name in frame.f_locals:
            return frame.f_locals[name]
        if name in frame.f_globals:
            return frame.f_globals[name]
    finally:
        del frame
    return None


_orchestrator_agent_id = _safe_get("orchestrator_agent_id")
_pricing_agent_id = _safe_get("pricing_agent_id")
_support_agent_id = _safe_get("support_agent_id")
_record_ids = _safe_get("record_ids")
_REGISTRY_ID = _safe_get("REGISTRY_ID")
_target_ids = _safe_get("target_ids")
_gateway_id = _safe_get("gateway_id")
_lambda_arns = _safe_get("lambda_arns")
_lambda_role_name = _safe_get("lambda_role_name")
_gateway_role_name = _safe_get("gateway_role_name")
_secret_name = _safe_get("secret_name")
_domain_name = _safe_get("domain_name")
_user_pool_id = _safe_get("user_pool_id")
_orchestrator_launch = _safe_get("orchestrator_launch")
_pricing_launch = _safe_get("pricing_launch")
_support_launch = _safe_get("support_launch")

print("=== Cleanup ===\n")

_agent_ids = [
    ("orchestrator", _orchestrator_agent_id),
    ("pricing", _pricing_agent_id),
    ("support", _support_agent_id),
]

# 1. 레지스트리 레코드 삭제
print("\n1. Deleting registry records...")
if _record_ids and _REGISTRY_ID:
    for rid in _record_ids:
        try:
            cp_client.delete_registry_record(registryId=_REGISTRY_ID, recordId=rid)
            print(f"  Deleted record: {rid}")
        except Exception as e:
            print(f"  Skip {rid}: {e}")
else:
    print("  Skipped (record_ids or REGISTRY_ID not set)")

# 2. 레지스트리 삭제
print("\n2. Deleting registry...")
if _REGISTRY_ID:
    try:
        cp_client.delete_registry(registryId=_REGISTRY_ID)
        print(f"  Deleted registry: {_REGISTRY_ID}")
    except Exception as e:
        print(f"  Skip: {e}")
else:
    print("  Skipped (REGISTRY_ID not set)")

# 3. A2A 에이전트 삭제
print("\n3. Deleting A2A agents...")
for name, aid in _agent_ids:
    if not aid:
        print(f"  {name}: skipped (variable not set)")
        continue
    try:
        cp_client.delete_agent_runtime(agentRuntimeId=aid)
        print(f"  Deleted agent: {aid}")
    except Exception as e:
        print(f"  Skip {name}: {e}")

# 4. Gateway 대상 삭제
print("\n4. Deleting gateway targets...")
if _target_ids and _gateway_id:
    for tname, tid in _target_ids.items():
        try:
            cp_client.delete_gateway_target(gatewayIdentifier=_gateway_id, targetId=tid)
            print(f"  Deleted target: {tid}")
        except Exception as e:
            print(f"  Skip {tname}: {e}")
    time.sleep(30)  # 대상이 삭제될 때까지 대기
else:
    print("  Skipped (target_ids or gateway_id not set)")

# 5. Gateway 삭제
print("\n5. Deleting gateway...")
if _gateway_id:
    try:
        cp_client.delete_gateway(gatewayIdentifier=_gateway_id)
        print(f"  Deleted gateway: {_gateway_id}")
    except Exception as e:
        print(f"  Skip: {e}")
else:
    print("  Skipped (gateway_id not set)")

# 6. Lambda 함수 삭제
print("\n6. Deleting Lambda functions...")
if _lambda_arns:
    for name, arn in _lambda_arns.items():
        try:
            lambda_client.delete_function(FunctionName=arn)
            print(f"  Deleted: {name}")
        except Exception as e:
            print(f"  Skip {name}: {e}")
else:
    print("  Skipped (lambda_arns not set)")

# 7. IAM 역할 삭제
print("\n7. Deleting IAM roles...")
for role_name in [_lambda_role_name, _gateway_role_name]:
    if not role_name:
        continue
    try:
        for p in iam_client.list_attached_role_policies(RoleName=role_name)["AttachedPolicies"]:
            iam_client.detach_role_policy(RoleName=role_name, PolicyArn=p["PolicyArn"])
        for p in iam_client.list_role_policies(RoleName=role_name)["PolicyNames"]:
            iam_client.delete_role_policy(RoleName=role_name, PolicyName=p)
        iam_client.delete_role(RoleName=role_name)
        print(f"  Deleted role: {role_name}")
    except Exception as e:
        print(f"  Skip {role_name}: {e}")

# 8. Secrets Manager 보안 암호 삭제
print("\n8. Deleting Secrets Manager secret...")
if _secret_name:
    try:
        sm_client.delete_secret(SecretId=_secret_name, ForceDeleteWithoutRecovery=True)
        print(f"  Deleted secret: {_secret_name}")
    except Exception as e:
        print(f"  Skip: {e}")
else:
    print("  Skipped (secret_name not set)")

# 9. Cognito 삭제
print("\n9. Deleting Cognito...")
if _domain_name and _user_pool_id:
    try:
        cognito_client.delete_user_pool_domain(Domain=_domain_name, UserPoolId=_user_pool_id)
        cognito_client.delete_user_pool(UserPoolId=_user_pool_id)
        print(f"  Deleted pool: {_user_pool_id}")
    except Exception as e:
        print(f"  Skip: {e}")
else:
    print("  Skipped (domain_name or user_pool_id not set)")

# 10. 로컬 파일 정리
print("\n10. Cleaning up local files...")
for f in [
    "pricing_agent.py",
    "customer_support_agent.py",
    "orchestrator_agent.py",
    "a2a_requirements.txt",
    "orchestrator_requirements.txt",
    ".bedrock_agentcore.yaml",
    "Dockerfile",
    ".dockerignore",
]:
    if os.path.exists(f):
        os.remove(f)
        print(f"  Removed: {f}")
if os.path.exists("models"):
    shutil.rmtree("models")

# 11. 스타터 툴킷에서 생성한 ECR 리포지토리 삭제
print("\n11. Deleting ECR repositories...")
ecr_client = session.client("ecr")
for launch in [_orchestrator_launch, _pricing_launch, _support_launch]:
    if not launch:
        continue
    try:
        repo_name = launch.ecr_uri.split("/")[1].split(":")[0]
        ecr_client.delete_repository(repositoryName=repo_name, force=True)
        print(f"  Deleted ECR repo: {repo_name}")
    except Exception as e:
        print(f"  Skip ECR: {e}")

print("\n=== Cleanup complete! ===")
