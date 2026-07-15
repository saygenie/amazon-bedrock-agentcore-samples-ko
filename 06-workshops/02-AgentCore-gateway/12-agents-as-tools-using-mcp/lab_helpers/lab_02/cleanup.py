"""
Lab 02: 리소스 정리

Lab 02에서 생성한 모든 리소스를 제거합니다.

AWS 리소스:
- AgentCore Gateway 및 모든 대상
- Lambda 함수(aiml301-diagnostic-agent)
- ECR 리포지토리(aiml301-diagnostic-agent)
- S3 버킷 및 모든 배포 패키지
- IAM 역할(Lambda 실행, Gateway 서비스)
- Parameter Store 항목
- CloudWatch 로그

로컬 아티팩트(Docker 방식):
- lambda_diagnostic_agent/ (Docker 빌드 디렉터리)

로컬 아티팩트(ZIP 방식):
- lambda_diagnostic_agent_zip/ (lib/ 종속성이 포함된 ZIP 빌드 디렉터리)
- lambda_diagnostic_agent_zip.zip (ZIP 패키지 파일)
- 그 밖의 모든 *_zip 디렉터리(포괄 패턴)
- 그 밖의 모든 *.zip 파일(포괄 패턴)

임시 파일:
- __pycache__/ 디렉터리
- 컴파일된 *.pyc Python 파일

보존하는 리소스:
- Lab-02-diagnostics-agent.ipynb (Notebook 파일 보존)
- lab_helpers/ 모듈(재사용을 위해 보존)
"""

import boto3
import time
import shutil
import os
from lab_helpers.constants import PARAMETER_PATHS


def cleanup_lab_02(region_name="us-west-2", cleanup_s3=True):
    """
    Lab 02의 모든 리소스(Docker 및 ZIP 배포)를 정리합니다.

    이 함수는 Lab 02에서 생성한 모든 AWS 리소스와 로컬 아티팩트를 제거합니다.

    AWS 정리:
    1. AgentCore Gateway(및 모든 대상)
    2. Lambda 함수(aiml301-diagnostic-agent)
    3. ECR 리포지토리(Docker 방식인 경우)
    4. S3 버킷 및 모든 배포 패키지(cleanup_s3=True인 경우)
    5. IAM 역할(Lambda 실행 역할, Gateway 서비스 역할)
    6. Parameter Store 항목
    7. CloudWatch 로그

    로컬 정리:
    - lambda_diagnostic_agent/ (Docker 빌드 아티팩트)
    - lambda_diagnostic_agent_zip/ (종속성이 포함된 ZIP 빌드 디렉터리)
    - lambda_diagnostic_agent_zip.zip (ZIP 패키지)
    - 그 밖의 모든 *_zip 디렉터리와 *.zip 파일(패턴 기반)
    - Python 캐시(__pycache__/, *.pyc)

    인자:
        region_name: AWS 리전(기본값: us-west-2)
        cleanup_s3: S3 버킷과 객체도 정리할지 여부(기본값: True)
                   S3 배포 패키지를 보존하려면 False로 설정합니다.

    반환:
        None(stdout에 상태 출력)

    예:
        from lab_helpers.lab_02.cleanup import cleanup_lab_02
        cleanup_lab_02(region_name="us-west-2", cleanup_s3=True)
    """
    print("🧹 Cleaning up Lab 02 resources...\n")
    print("=" * 70)

    # 클라이언트 초기화
    agentcore_client = boto3.client("bedrock-agentcore-control", region_name=region_name)
    lambda_client = boto3.client("lambda", region_name=region_name)
    ecr_client = boto3.client("ecr", region_name=region_name)
    s3_client = boto3.client("s3", region_name=region_name)
    iam_client = boto3.client("iam")
    ssm_client = boto3.client("ssm", region_name=region_name)
    logs_client = boto3.client("logs", region_name=region_name)

    # 1. Gateway 삭제(대상을 먼저 삭제한 다음 Gateway 삭제)
    print("[1/7] Deleting Gateway and targets...")
    try:
        # 이름으로 Gateway 찾기
        gateways = agentcore_client.list_gateways()
        for gw in gateways.get("items", []):
            if gw["name"] == "aiml301-diagnostics-gateway":
                gateway_id = gw["gatewayId"]
                targets_deleted = True  # 달리 확인되기 전까지 성공으로 간주

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
                                        f"  ⏳ Retry {retry_count}/{max_retries - 1}: {remaining_count} target(s) still present..."
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

    # 2. Lambda 함수 삭제
    print("[2/7] Deleting Lambda function...")
    try:
        lambda_client.delete_function(FunctionName="aiml301-diagnostic-agent")
        print("  ✓ Lambda deleted")
    except lambda_client.exceptions.ResourceNotFoundException:
        print("  ✓ Lambda not found (ok)")
    except Exception as e:
        print(f"  ⚠ Lambda deletion: {e}")

    # 3. ECR 리포지토리 삭제
    print("[3/7] Deleting ECR repository...")
    try:
        ecr_client.delete_repository(repositoryName="aiml301-diagnostic-agent", force=True)
        print("  ✓ ECR repository deleted")
    except ecr_client.exceptions.RepositoryNotFoundException:
        print("  ✓ ECR repository not found (ok)")
    except Exception as e:
        print(f"  ⚠ ECR deletion: {e}")

    # 3.5. S3 배포 패키지 삭제(ZIP 기반 배포)
    if cleanup_s3:
        print("[3.5/7] Deleting S3 deployment packages...")
        try:
            bucket_name = "aiml301-lambda-packages"
            # 버킷의 모든 객체 나열
            try:
                response = s3_client.list_objects_v2(Bucket=bucket_name)
                if "Contents" in response:
                    for obj in response["Contents"]:
                        s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])
                        print(f"    • Deleted: {obj['Key']}")

                # 버킷 자체 삭제
                s3_client.delete_bucket(Bucket=bucket_name)
                print(f"  ✓ S3 bucket deleted: {bucket_name}")
            except s3_client.exceptions.NoSuchBucket:
                print(f"  ✓ S3 bucket not found (ok): {bucket_name}")
        except Exception as e:
            print(f"  ⚠ S3 cleanup: {e}")

    # 4. IAM 역할 삭제
    print("[4/7] Deleting IAM roles...")

    # Lambda 실행 역할 삭제
    try:
        _delete_role(iam_client, "aiml301-diagnostic-lambda-role")
        print("  ✓ Lambda execution role deleted")
    except iam_client.exceptions.NoSuchEntityException:
        print("  ✓ Lambda execution role not found (ok)")
    except Exception as e:
        print(f"  ⚠ Lambda role: {e}")

    # Gateway 서비스 역할 삭제
    try:
        _delete_role(iam_client, "aiml301-gateway-service-role")
        print("  ✓ Gateway service role deleted")
    except iam_client.exceptions.NoSuchEntityException:
        print("  ✓ Gateway service role not found (ok)")
    except Exception as e:
        print(f"  ⚠ Gateway role: {e}")

    # 5. Parameter Store 항목 삭제(일관성을 위해 상수 사용)
    print("[5/7] Deleting Parameter Store entries...")
    try:
        params_to_delete = [
            PARAMETER_PATHS["lab_02"]["ecr_repository_uri"],
            PARAMETER_PATHS["lab_02"]["ecr_repository_name"],
            PARAMETER_PATHS["lab_02"]["lambda_role_arn"],
            PARAMETER_PATHS["lab_02"]["lambda_function_arn"],
            PARAMETER_PATHS["lab_02"]["gateway_role_arn"],
            PARAMETER_PATHS["lab_02"]["lambda_function_name"],
            PARAMETER_PATHS["lab_02"]["gateway_id"],
            PARAMETER_PATHS["lab_02"]["gateway_url"],
        ]
        # None 값 제거
        params_to_delete = [p for p in params_to_delete if p]
        if params_to_delete:
            ssm_client.delete_parameters(Names=params_to_delete)
            print(f"  ✓ Parameter Store entries deleted ({len(params_to_delete)} parameters)")
        else:
            print("  ✓ No parameters to delete")
    except Exception as e:
        print(f"  ⚠ Parameters: {e}")

    # 6. CloudWatch 로그 삭제
    print("[6/7] Deleting CloudWatch log groups...")
    try:
        logs_client.delete_log_group(logGroupName="/aws/lambda/aiml301-diagnostic-agent")
        print("  ✓ Lambda log group deleted")
    except logs_client.exceptions.ResourceNotFoundException:
        print("  ✓ Lambda log group not found (ok)")
    except Exception as e:
        print(f"  ⚠ Log group: {e}")

    # 7. 빌드 아티팩트 삭제(Docker 및 ZIP 방식 모두)
    print("[7/7] Deleting build artifacts and temporary files...")
    try:
        import glob

        artifacts_deleted = 0

        # Docker 빌드 디렉터리
        docker_dir = "lambda_diagnostic_agent"
        if os.path.exists(docker_dir):
            shutil.rmtree(docker_dir)
            print(f"  ✓ Docker build directory removed: {docker_dir}")
            artifacts_deleted += 1
        else:
            print("  ✓ Docker build directory not found (ok)")

        # 지정된 ZIP 빌드 디렉터리
        zip_build_dir = "lambda_diagnostic_agent_zip"
        if os.path.exists(zip_build_dir):
            shutil.rmtree(zip_build_dir)
            print(f"  ✓ ZIP build directory removed: {zip_build_dir}")
            artifacts_deleted += 1
        else:
            print("  ✓ ZIP build directory not found (ok)")

        # 지정된 ZIP 파일
        zip_file = "lambda_diagnostic_agent_zip.zip"
        if os.path.exists(zip_file):
            os.remove(zip_file)
            print(f"  ✓ ZIP file removed: {zip_file}")
            artifacts_deleted += 1
        else:
            print("  ✓ ZIP file not found (ok)")

        # 그 밖의 모든 *_zip 디렉터리 정리(다른 패턴까지 포괄)
        zip_dirs = glob.glob("*_zip")
        for zip_dir in zip_dirs:
            if os.path.isdir(zip_dir) and zip_dir != zip_build_dir:
                try:
                    shutil.rmtree(zip_dir)
                    print(f"  ✓ Additional ZIP directory removed: {zip_dir}")
                    artifacts_deleted += 1
                except Exception as e:
                    print(f"  ⚠ Could not remove {zip_dir}: {e}")

        # 그 밖의 모든 *.zip 파일 정리(다른 패턴까지 포괄)
        zip_files = glob.glob("*.zip")
        for zf in zip_files:
            if zf != zip_file:
                try:
                    os.remove(zf)
                    print(f"  ✓ Additional ZIP file removed: {zf}")
                    artifacts_deleted += 1
                except Exception as e:
                    print(f"  ⚠ Could not remove {zf}: {e}")

        # 생성되었을 수 있는 __pycache__ 디렉터리 정리
        pycache_dirs = glob.glob("**/__pycache__", recursive=True)
        for cache_dir in pycache_dirs:
            try:
                shutil.rmtree(cache_dir)
                print(f"  ✓ Python cache removed: {cache_dir}")
                artifacts_deleted += 1
            except Exception:
                pass  # 캐시 정리 실패는 별도로 알리지 않음

        # *.pyc 파일 정리
        pyc_files = glob.glob("**/*.pyc", recursive=True)
        for pyc in pyc_files:
            try:
                os.remove(pyc)
                artifacts_deleted += 1
            except Exception:
                pass  # pyc 정리 실패는 별도로 알리지 않음

        if artifacts_deleted > 0:
            print(f"\n  Total artifacts cleaned: {artifacts_deleted}")

    except Exception as e:
        print(f"  ⚠ Build artifacts cleanup: {e}")

    print("\n" + "=" * 70)
    print("✅ Lab 02 cleanup complete")
    print("\nYou can now re-run the entire Lab 02 from Section 1")


def _delete_role(iam_client, role_name):
    """헬퍼: 모든 정책을 분리하고 역할을 삭제합니다."""
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

    cleanup_lab_02(region_name=AWS_REGION)
