"""
Lab 04: Remediation Agent 리소스 정리

Lab 04에서 생성한 모든 리소스를 제거합니다.

삭제하는 AWS 리소스:
- AgentCore Gateway 및 모든 대상
- AgentCore Runtime(prevention-runtime)
- OAuth2 Credential Provider
- Secrets Manager 보안 암호(m2m 자격 증명)
- IAM 역할(Runtime 실행, Gateway 서비스)
- CloudWatch 로그

보존하는 AWS 리소스:
- Parameter Store 항목(put_parameter()가 이제 덮어쓰기를 지능적으로 처리)
  • 재배포 후 Section 7.3c를 다시 실행하여 새 runtime_arn/runtime_id로 업데이트

삭제하는 로컬 아티팩트:
- agent-prevention.py
- Dockerfile
- .bedrock_agentcore.yaml
- .dockerignore
- Python 캐시(__pycache__/, *.pyc)

보존하는 로컬 아티팩트:
- Lab-03-prevention-agent.ipynb (Notebook 파일)
- lab_helpers/ 모듈(재사용을 위해 보존)
"""

import boto3
import json
import time
import shutil
import os
import logging

from lab_helpers.constants import PARAMETER_PATHS
from lab_helpers.lab_04.configure_logging import cleanup_runtime_logging

logger = logging.getLogger(__name__)


def cleanup_lab_04(region_name: str = "us-west-2", verbose: bool = True) -> None:
    """
    Lab 04의 모든 리소스(Runtime 및 Gateway)를 정리합니다.

    이 함수는 Lab 04에서 생성한 AWS 리소스와 로컬 아티팩트를 제거합니다.

    삭제하는 AWS 리소스:
    1. AgentCore Gateway(및 모든 대상)
    2. AgentCore Runtime(prevention-runtime)
    3. OAuth2 Credential Provider
    4. Secrets Manager 보안 암호(m2m 자격 증명)
    5. IAM 역할(Runtime 실행 역할, Gateway 서비스 역할)
    6. CloudWatch 로그

    보존하는 AWS 리소스:
    - Parameter Store 항목(재배포 시 지능적으로 덮어씀)

    삭제하는 로컬 아티팩트:
    7. 생성 파일(agent-prevention.py, Dockerfile, .bedrock_agentcore.yaml, .dockerignore)
    8. Python 캐시(__pycache__/, *.pyc)

    인자:
        region_name: AWS 리전(기본값: us-west-2)
        verbose: 상세 상태 메시지 출력 여부(기본값: True)

    반환:
        None(stdout에 상태 출력)

    예:
        from lab_helpers.lab_04.cleanup import cleanup_lab_04
        cleanup_lab_04(region_name="us-west-2", verbose=True)
    """
    print("🧹 Cleaning up Lab 04 resources...\n")
    print("=" * 70)

    if verbose:
        logging.basicConfig(level=logging.INFO)

    # 클라이언트 초기화
    agentcore_client = boto3.client("bedrock-agentcore-control", region_name=region_name)
    iam_client = boto3.client("iam")
    ssm_client = boto3.client("ssm", region_name=region_name)
    logs_client = boto3.client("logs", region_name=region_name)
    secrets_client = boto3.client("secretsmanager", region_name=region_name)

    # 디버그: Lab 04 관련 파라미터 모두 찾기
    if verbose:
        print("[DEBUG] Searching for Lab 04 parameters in Parameter Store...")
        try:
            response = ssm_client.describe_parameters(
                Filters=[
                    {
                        "Key": "Name",
                        "Values": ["lab-03", "lab04", "prevention", "aiml301"],
                    }
                ]
            )
            if response.get("Parameters"):
                print(f"  Found {len(response['Parameters'])} parameter(s):")
                for param in response["Parameters"]:
                    print(f"    • {param['Name']}")
            else:
                print("  No Lab 04 parameters found")
        except Exception as e:
            print(f"  ℹ Parameter search error: {e}")
        print()

    # 1. OAuth2 Credential Provider 삭제
    print("[1/7] Deleting OAuth2 Credential Provider...")
    provider_deleted = False

    try:
        # Parameter Store에서 provider ARN 조회
        try:
            response = ssm_client.get_parameter(Name=PARAMETER_PATHS["lab_04"]["oauth2_provider_arn"])
            provider_arn = response["Parameter"]["Value"]

            if provider_arn:
                # ARN에서 provider 이름 추출
                # ARN 형식: arn:aws:bedrock-agentcore:region:account:token-vault/default/oauth2credentialprovider/PROVIDER_NAME
                provider_name = provider_arn.split("/")[-1]

                if verbose:
                    print(f"  ℹ Found provider ARN: {provider_arn}")
                    print(f"  ℹ Extracted provider name: {provider_name}")

                try:
                    # 올바른 'name' 파라미터를 사용해 provider 삭제
                    agentcore_client.delete_oauth2_credential_provider(name=provider_name)
                    print(f"  ✓ OAuth2 credential provider deleted: {provider_name}")
                    provider_deleted = True
                except Exception as e:
                    error_str = str(e)
                    # 이미 삭제되었거나 존재하지 않는지 확인
                    if "ResourceNotFoundException" in error_str or "does not exist" in error_str.lower():
                        print("  ✓ Provider already deleted or not found (ok)")
                        provider_deleted = True
                    else:
                        print(f"  ⚠ Failed to delete provider {provider_name}: {error_str}")

        except ssm_client.exceptions.ParameterNotFound:
            if verbose:
                print("  ℹ Provider ARN not found in Parameter Store (ok)")
            provider_deleted = True  # noqa: F841

    except Exception as e:
        print(f"  ⚠ OAuth2 cleanup error: {e}")

    # 1b. OAuth2 credential provider가 생성한 Secrets Manager 보안 암호 삭제
    print("[1b/8] Deleting Secrets Manager secrets...")
    try:
        # 보안 암호를 페이지 단위로 조회하여 OAuth2 credential provider가 생성한 항목 찾기
        # OAuth2 provider는 다음 패턴으로 보안 암호를 생성: bedrock-agentcore-identity!default/oauth2/aiml301-m2m-credentials-*
        paginator = secrets_client.get_paginator("list_secrets")
        pages = paginator.paginate()

        oauth2_secrets = []
        for page in pages:
            for secret in page.get("SecretList", []):
                secret_name = secret["Name"]
                # OAuth2 credential provider 보안 암호와 일치하는지 확인
                if (
                    ("bedrock-agentcore-identity" in secret_name and "m2m-credentials" in secret_name)
                    or ("bedrock-agentcore-identity" in secret_name and "aiml301" in secret_name)
                    or "m2m-credentials" in secret_name
                ):
                    oauth2_secrets.append(secret)

        if oauth2_secrets:
            for secret in oauth2_secrets:
                secret_name = secret["Name"]
                try:
                    secrets_client.delete_secret(SecretId=secret_name, ForceDeleteWithoutRecovery=True)
                    print(f"  ✓ Secret deleted: {secret_name}")
                except Exception as e:
                    error_str = str(e)
                    if "ResourceNotFoundException" not in error_str:
                        # 예상대로 bedrock-agentcore-identity가 소유하는지 확인
                        if "bedrock-agentcore-identity" in error_str:
                            print(
                                f"  ℹ Secret {secret_name} is service-owned - will be auto-deleted when provider is removed"
                            )
                        else:  # codeql[py/clear-text-logging-sensitive-data]
                            print(f"  ⚠ Failed to delete secret {secret_name}: {error_str}")
        else:  # codeql[py/clear-text-logging-sensitive-data]
            print("  ✓ No OAuth2 m2m credentials secrets found")

    except Exception as e:
        print(f"  ⚠ Secrets Manager cleanup error: {e}")

    # 2. Gateway 삭제(대상을 먼저 삭제한 다음 Gateway 삭제)
    print("[2/8] Deleting Gateway and targets...")
    try:
        # 이름으로 Gateway 찾기
        gateways = agentcore_client.list_gateways()
        for gw in gateways.get("items", []):
            if "prevention-gateway" in gw["name"]:
                gateway_id = gw["gatewayId"]

                # 1단계: 대상 삭제
                try:
                    targets = agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
                    target_count = len(targets.get("items", []))

                    if target_count > 0:
                        print(f"  Deleting {target_count} target(s)...")
                        for target in targets.get("items", []):
                            target_id = target["targetId"]
                            agentcore_client.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
                            print(f"    • Deleted target: {target_id}")

                        # 2단계: 재시도 로직으로 대상이 삭제되었는지 확인
                        print("  Verifying target deletion...")
                        max_retries = 5
                        retry_count = 0
                        targets_deleted = False

                        while retry_count < max_retries and not targets_deleted:
                            time.sleep(3)  # AWS 전파 대기
                            remaining_targets = agentcore_client.list_gateway_targets(gatewayIdentifier=gateway_id)
                            remaining_count = len(remaining_targets.get("items", []))

                            if remaining_count == 0:
                                print("  ✓ All targets confirmed deleted")
                                targets_deleted = True
                            else:
                                retry_count += 1
                                if retry_count < max_retries:
                                    print(
                                        f"  ⏳ Retry {retry_count}/{max_retries - 1}: "
                                        f"{remaining_count} target(s) still present..."
                                    )
                                else:
                                    print(
                                        f"  ⚠ {remaining_count} target(s) still associated after {max_retries} retries"
                                    )
                    else:
                        print("  ✓ No targets found")
                        targets_deleted = True

                except Exception as e:
                    print(f"  ⚠ Target deletion: {e}")
                    targets_deleted = False

                # 3단계: Gateway 삭제(대상이 삭제되었다고 확인된 경우에만)
                try:
                    if targets_deleted:
                        agentcore_client.delete_gateway(gatewayIdentifier=gateway_id)
                        print("  ✓ Gateway deleted")
                    else:
                        print("  ⚠ Skipping gateway deletion - targets still present")
                        print("     Please try cleanup again in a few moments")
                except Exception as e:
                    print(f"  ⚠ Gateway deletion: {e}")

                break
        else:
            print("  ✓ Gateway not found (ok)")

    except Exception as e:
        print(f"  ⚠ Gateway lookup error: {e}")

    # 3. Runtime 및 연결된 CloudWatch Logs Delivery 삭제
    print("[3/8] Deleting AgentCore Runtime...")
    try:
        runtime_deleted = False
        runtime_id_for_logging = None
        prefixes = [
            "aiml301_sre_agentcore",
            "aiml301-sre-agentcore",
            "aiml301",
            "lab-03",
        ]

        # 먼저 Parameter Store에서 Runtime 정보 조회 시도
        for prefix in prefixes:
            if runtime_deleted:
                break

            try:
                # 여러 파라미터 이름을 구체적인 순서로 조회
                param_names = [
                    f"/{prefix}/lab-04/runtime-id",  # 직접 ID(가장 가능성 높음)
                    f"/{prefix}/lab-04/runtime-config",  # ID가 포함된 JSON
                    f"/{prefix}/runtime-id",  # 대체 이름
                    f"/{prefix}/runtime-config",
                ]

                for param_name in param_names:
                    try:
                        response = ssm_client.get_parameter(Name=param_name)
                        param_value = response["Parameter"]["Value"]

                        if verbose:
                            print(f"  Found parameter: {param_name}")

                        # 먼저 JSON으로 파싱 시도
                        runtime_id = None
                        try:
                            runtime_config = json.loads(param_value)
                            runtime_id = runtime_config.get("runtime_id")
                        except (json.JSONDecodeError, TypeError):
                            # JSON이 아니면 Runtime ID 자체로 간주
                            if param_value and param_value.strip():
                                runtime_id = param_value.strip()

                        if runtime_id:
                            print("  Found runtime ID: ****")
                            runtime_id_for_logging = runtime_id

                            # Runtime을 삭제하기 전에 CloudWatch Logs Delivery 정리
                            try:
                                print("  Cleaning up CloudWatch Logs Delivery for runtime...")
                                cleanup_runtime_logging(runtime_id, region=region_name)
                            except Exception as e:
                                print(f"  ⚠ CloudWatch Logs Delivery cleanup warning: {e}")

                            try:
                                agentcore_client.delete_agent_runtime(agentRuntimeId=runtime_id)
                                print("  ✓ Runtime deletion initiated: ****")

                                # Runtime이 완전히 삭제될 때까지 대기
                                print("  ⏳ Waiting for Runtime deletion to complete...")
                                max_retries = 60
                                retry_count = 0

                                while retry_count < max_retries:
                                    time.sleep(5)
                                    try:
                                        status_check = agentcore_client.get_agent_runtime(agentRuntimeId=runtime_id)
                                        current_status = status_check.get("status", "UNKNOWN")
                                        retry_count += 1
                                        print(f"     Status: {current_status} (check {retry_count}/{max_retries})")

                                        if current_status == "DELETING":
                                            continue
                                    except agentcore_client.exceptions.ResourceNotFoundException:
                                        print("  ✓ Runtime fully deleted: ****")
                                        runtime_deleted = True
                                        break
                                    except Exception as e:
                                        if "not found" in str(e).lower():
                                            print("  ✓ Runtime fully deleted: ****")
                                            runtime_deleted = True
                                            break
                                        else:
                                            print(f"  ⚠ Error checking status: {e}")
                                            break

                                if not runtime_deleted:
                                    print(f"  ⚠ Runtime may still be deleting after {max_retries} retries")

                                break

                            except Exception as e:
                                error_str = str(e)
                                if (
                                    "ResourceNotFoundException" not in error_str
                                    and "does not exist" not in error_str.lower()
                                ):
                                    print(f"  ⚠ Runtime deletion error: {error_str}")

                    except ssm_client.exceptions.ParameterNotFound:
                        if verbose:
                            print(f"  Parameter not found: {param_name}")

            except Exception as e:
                if verbose:
                    print(f"  ℹ Parameter Store search ({prefix}): {e}")

        # 대체 경로: Runtime 목록에서 찾기
        if not runtime_deleted:
            if verbose:
                print("  Runtime not in Parameter Store, checking API...")

            try:
                runtimes = agentcore_client.list_agent_runtimes()
                all_items = runtimes.get("items", [])

                if verbose and all_items:
                    print(f"  Found {len(all_items)} runtime(s) via API")

                for rt in all_items:
                    runtime_name = rt["agentRuntimeName"].lower()
                    if "prevention" in runtime_name or "aiml301" in runtime_name:
                        runtime_id = rt["agentRuntimeId"]
                        runtime_id_for_logging = runtime_id  # noqa: F841
                        print(f"  Found runtime: {rt['agentRuntimeName']}")

                        # Runtime을 삭제하기 전에 CloudWatch Logs Delivery 정리
                        try:
                            print("  Cleaning up CloudWatch Logs Delivery for runtime...")
                            cleanup_runtime_logging(runtime_id, region=region_name)
                        except Exception as e:
                            print(f"  ⚠ CloudWatch Logs Delivery cleanup warning: {e}")

                        try:
                            agentcore_client.delete_agent_runtime(agentRuntimeId=runtime_id)
                            print("  ✓ Runtime deletion initiated: ****")

                            # Runtime이 완전히 삭제될 때까지 대기
                            print("  ⏳ Waiting for Runtime deletion to complete...")
                            max_retries = 30
                            retry_count = 0

                            while retry_count < max_retries:
                                time.sleep(5)
                                try:
                                    status_check = agentcore_client.get_agent_runtime(agentRuntimeId=runtime_id)
                                    current_status = status_check.get("status", "UNKNOWN")
                                    retry_count += 1
                                    print(f"     Status: {current_status} (check {retry_count}/{max_retries})")

                                    if current_status == "DELETING":
                                        continue
                                except agentcore_client.exceptions.ResourceNotFoundException:
                                    print("  ✓ Runtime fully deleted: ****")
                                    runtime_deleted = True
                                    break
                                except Exception as e:
                                    if "not found" in str(e).lower():
                                        print("  ✓ Runtime fully deleted: ****")
                                        runtime_deleted = True
                                        break
                                    else:
                                        print(f"  ⚠ Error checking status: {e}")
                                        break

                            if not runtime_deleted:
                                print(f"  ⚠ Runtime may still be deleting after {max_retries} retries")

                            break
                        except Exception as e:
                            print(f"  ⚠ Runtime deletion failed: {e}")

            except Exception as e:
                if verbose:
                    print(f"  ℹ API lookup error: {e}")

        if not runtime_deleted:
            print("  ✓ Runtime not found (ok)")

    except Exception as e:
        print(f"  ⚠ Runtime cleanup error: {e}")

    # 4. IAM 역할 삭제
    print("[4/8] Deleting IAM roles...")

    # Runtime 실행 역할 삭제
    try:
        _delete_role(iam_client, "aiml301-agentcore-prevention-role")
        print("  ✓ Runtime execution role deleted")
    except iam_client.exceptions.NoSuchEntityException:
        print("  ✓ Runtime execution role not found (ok)")
    except Exception as e:
        print(f"  ⚠ Runtime role: {e}")

    # Gateway 서비스 역할 삭제
    try:
        _delete_role(iam_client, "aiml301-prevention-gateway-role")
        print("  ✓ Gateway service role deleted")
    except iam_client.exceptions.NoSuchEntityException:
        print("  ✓ Gateway service role not found (ok)")
    except Exception as e:
        print(f"  ⚠ Gateway role: {e}")

    # 5. Parameter Store 항목(재사용을 위해 보존)
    print("[5/8] Parameter Store entries...")
    print("  ✓ Preserved (put_parameter() now handles overwrites intelligently)")
    print("  ℹ Run Section 7.3c again to update values with latest ARN/ID")

    # 6. CloudWatch 로그 삭제
    print("[6/8] Deleting CloudWatch log groups...")
    try:
        # 패턴과 일치하는 로그 그룹을 찾아 삭제
        logs_pattern = "/aws/bedrock-agentcore/runtime"
        log_groups = logs_client.describe_log_groups(logGroupNamePrefix=logs_pattern)

        for lg in log_groups.get("logGroups", []):
            if "prevention" in lg["logGroupName"].lower():
                try:
                    logs_client.delete_log_group(logGroupName=lg["logGroupName"])
                    print(f"  ✓ Log group deleted: {lg['logGroupName']}")
                except Exception as e:
                    print(f"  ⚠ Failed to delete {lg['logGroupName']}: {e}")

    except logs_client.exceptions.ResourceNotFoundException:
        print("  ✓ No log groups found (ok)")
    except Exception as e:
        print(f"  ⚠ Log group cleanup: {e}")

    # 7. 로컬 생성 파일 삭제
    print("[7/8] Deleting local artifacts...")
    try:
        # 현재 작업 디렉터리 가져오기
        cwd = os.getcwd()

        # 삭제할 파일
        files_to_delete = [
            os.path.join(cwd, "agent-prevention.py"),
            os.path.join(cwd, "Dockerfile"),
            os.path.join(cwd, ".bedrock_agentcore.yaml"),
            os.path.join(cwd, ".dockerignore"),
        ]

        deleted_count = 0
        for file_path in files_to_delete:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"  ✓ Deleted: {os.path.basename(file_path)}")
                    deleted_count += 1
                except Exception as e:
                    print(f"  ⚠ Failed to delete {os.path.basename(file_path)}: {e}")

        # Python 캐시 정리
        pycache_paths = [
            os.path.join(cwd, "__pycache__"),
            os.path.join(cwd, "agent_prevention.cpython-*.pyc"),
        ]

        for pycache in pycache_paths:
            if "__pycache__" in pycache and os.path.isdir(pycache):
                try:
                    shutil.rmtree(pycache)
                    print("  ✓ Deleted: __pycache__")
                except Exception as e:
                    print(f"  ⚠ Failed to delete __pycache__: {e}")

        if deleted_count == 0:
            print("  ✓ No local artifacts found (ok)")

    except Exception as e:
        print(f"  ⚠ Local cleanup: {e}")

    print("\n" + "=" * 70)
    print("✅ Lab 04 cleanup complete")
    print("\nYou can now re-run Lab 04 from Section 1")


def _delete_role(iam_client, role_name: str) -> None:
    """
    헬퍼: 모든 정책을 분리하고 역할을 삭제합니다.

    인자:
        iam_client: IAM boto3 클라이언트
        role_name: 삭제할 IAM 역할 이름
    """
    # 관리형 정책 분리
    policies = iam_client.list_attached_role_policies(RoleName=role_name)
    for policy in policies.get("AttachedPolicies", []):
        iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy["PolicyArn"])

    # 인라인 정책 삭제
    inline_policies = iam_client.list_role_policies(RoleName=role_name)
    for policy_name in inline_policies.get("PolicyNames", []):
        iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)

    # 역할 삭제
    iam_client.delete_role(RoleName=role_name)


if __name__ == "__main__":
    from lab_helpers.config import AWS_REGION

    print("Lab 04: Cleanup All Resources")
    print("=" * 70)
    print("\nWARNING: This will delete:")
    print("\nAWS RESOURCES DELETED:")
    print("  • AgentCore Gateway and all targets")
    print("  • AgentCore Runtime")
    print("  • OAuth2 Credential Provider")
    print("  • Secrets Manager secrets (m2m credentials)")
    print("  • IAM roles (Runtime, Gateway)")
    print("  • CloudWatch logs")
    print("\nAWS RESOURCES PRESERVED:")
    print("  ✓ Parameter Store entries (will be updated on re-deploy)")
    print("\nLOCAL FILES DELETED:")
    print("  • agent-prevention.py")
    print("  • Dockerfile")
    print("  • .bedrock_agentcore.yaml")
    print("  • .dockerignore")
    print("  • Python cache (__pycache__/)")
    print("\nThis action cannot be undone.\n")

    confirm = input("Are you sure? Type 'yes' to proceed: ")
    if confirm.lower() == "yes":
        cleanup_lab_04(region_name=AWS_REGION, verbose=True)
    else:
        print("Cleanup cancelled")
