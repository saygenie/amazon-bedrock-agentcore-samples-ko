"""
Lab 05: Supervisor Agent 리소스 정리

Lab 05 배포 중 생성한 모든 리소스를 정리합니다.
- Supervisor Agent Runtime
- IAM 역할
- ECR 리포지토리(선택 사항)
- agent-supervisor.py 파일
- Dockerfile
- .bedrock_agentcore.yaml
"""

import os
import boto3
import logging
from typing import Dict, List
from botocore.exceptions import ClientError

from lab_helpers.config import AWS_REGION
from .iam_setup import delete_supervisor_runtime_iam_role

logger = logging.getLogger(__name__)


def delete_supervisor_runtime(runtime_name: str, region: str = AWS_REGION, verbose: bool = True) -> bool:
    """
    Supervisor Agent Runtime을 삭제합니다.

    인자:
        runtime_name: 삭제할 Supervisor Runtime 이름
        region: AWS 리전
        verbose: 상태 메시지 출력 여부

    반환:
        성공하면 True, 그렇지 않으면 False
    """
    try:
        agentcore = boto3.client("bedrock-agentcore-control", region_name=region)

        if verbose:
            logger.info(f"🗑️  Deleting supervisor runtime: {runtime_name}")

        # Runtime 목록에서 삭제할 항목 찾기
        response = agentcore.list_agent_runtimes()
        runtime_id = None

        for runtime in response.get("agentRuntimes", []):
            if runtime["agentRuntimeName"] == runtime_name:
                runtime_id = runtime["agentRuntimeId"]
                break

        if not runtime_id:
            if verbose:
                logger.warning(f"⚠️  Runtime not found: {runtime_name}")
            return True

        # Runtime 삭제
        agentcore.delete_agent_runtime(agentRuntimeId=runtime_id)

        if verbose:
            logger.info(f"✅ Supervisor runtime deleted: {runtime_id}")

        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            if verbose:
                logger.warning(f"⚠️  Runtime not found: {runtime_name}")
            return True
        logger.error(f"❌ Error deleting runtime: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error deleting runtime: {e}")
        return False


def delete_supervisor_gateway(gateway_name: str, region: str = AWS_REGION, verbose: bool = True) -> bool:
    """
    Supervisor Gateway를 삭제합니다.

    인자:
        gateway_name: 삭제할 Supervisor Gateway 이름
        region: AWS 리전
        verbose: 상태 메시지 출력 여부

    반환:
        성공하면 True, 그렇지 않으면 False
    """
    try:
        agentcore = boto3.client("bedrock-agentcore-control", region_name=region)

        if verbose:
            logger.info(f"🗑️  Deleting supervisor gateway: {gateway_name}")

        # Gateway 목록에서 삭제할 항목 찾기
        response = agentcore.list_gateways()
        gateway_id = None

        for gateway in response.get("gatewaySummaries", []):
            if gateway_name in gateway["gatewayArn"]:
                gateway_id = gateway["gatewayId"]
                break

        if not gateway_id:
            if verbose:
                logger.warning(f"⚠️  Gateway not found: {gateway_name}")
            return True

        # Gateway 삭제
        agentcore.delete_gateway(gatewayIdentifier=gateway_id)

        if verbose:
            logger.info(f"✅ Supervisor gateway deleted: {gateway_id}")

        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            if verbose:
                logger.warning(f"⚠️  Gateway not found: {gateway_name}")
            return True
        logger.error(f"❌ Error deleting gateway: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error deleting gateway: {e}")
        return False


def delete_ecr_repository(
    repository_name: str,
    region: str = AWS_REGION,
    verbose: bool = True,
    force: bool = True,
) -> bool:
    """
    Supervisor Runtime용 ECR 리포지토리를 삭제합니다.

    인자:
        repository_name: ECR 리포지토리 이름
        region: AWS 리전
        verbose: 상태 메시지 출력 여부
        force: 리포지토리에 이미지가 있어도 강제로 삭제할지 여부

    반환:
        성공하면 True, 그렇지 않으면 False
    """
    try:
        ecr = boto3.client("ecr", region_name=region)

        if verbose:
            logger.info(f"🗑️  Deleting ECR repository: {repository_name}")

        ecr.delete_repository(repositoryName=repository_name, force=force)

        if verbose:
            logger.info(f"✅ ECR repository deleted: {repository_name}")

        return True

    except ClientError as e:
        if e.response["Error"]["Code"] == "RepositoryNotFoundException":
            if verbose:
                logger.warning(f"⚠️  Repository not found: {repository_name}")
            return True
        logger.error(f"❌ Error deleting ECR repository: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error deleting ECR repository: {e}")
        return False


def delete_supervisor_files(file_names: List[str] = None, verbose: bool = True) -> Dict[str, bool]:
    """
    프로젝트 루트에서 Supervisor 관련 파일을 삭제합니다.

    인자:
        file_names: 삭제할 파일 이름 목록(제공하지 않으면 표준 파일을 기본값으로 사용)
        verbose: 상태 메시지 출력 여부

    반환:
        각 파일의 삭제 상태가 포함된 딕셔너리
    """
    if file_names is None:
        file_names = ["agent-supervisor.py", "Dockerfile", ".bedrock_agentcore.yaml"]

    # 프로젝트 루트 디렉터리 가져오기(lab_helpers/lab_05/cleanup.py에서 3단계 상위)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    deletion_status = {}

    for file_name in file_names:
        try:
            file_path = os.path.join(project_root, file_name)

            if verbose:
                logger.info(f"🗑️  Deleting {file_name}: {file_path}")

            if os.path.exists(file_path):
                os.remove(file_path)
                if verbose:
                    logger.info(f"✅ {file_name} deleted")
                deletion_status[file_name] = True
            else:
                if verbose:
                    logger.warning(f"⚠️  File not found: {file_path}")
                deletion_status[file_name] = True

        except Exception as e:
            logger.error(f"❌ Error deleting {file_name}: {e}")
            deletion_status[file_name] = False

    return deletion_status


def cleanup_lab_05(region_name: str = AWS_REGION, verbose: bool = True, delete_ecr: bool = True) -> Dict[str, bool]:
    """
    Lab 05의 모든 리소스를 정리합니다.

    인자:
        region_name: AWS 리전
        verbose: 상태 메시지 출력 여부
        delete_ecr: ECR 리포지토리 삭제 여부(기본값: True)

    반환:
        각 리소스의 정리 상태가 포함된 딕셔너리
    """
    logger.info("\n🧹 Starting Lab-05 Cleanup...")
    if verbose:
        logger.info("=" * 70)

    cleanup_status = {}

    # 1. Supervisor Runtime 삭제
    if verbose:
        logger.info("\n1️⃣  Deleting Supervisor Runtime...")
    cleanup_status["runtime"] = delete_supervisor_runtime(
        runtime_name="aiml301_sre_agentcore_supervisor_runtime",
        region=region_name,
        verbose=verbose,
    )

    # 2. IAM 역할 삭제
    if verbose:
        logger.info("\n2️⃣  Deleting IAM Role...")
    cleanup_status["iam_role"] = delete_supervisor_runtime_iam_role(
        role_name="aiml301_sre_agentcore-lab05-supervisor-runtime-role",
        region=region_name,
    )

    # 3. ECR 리포지토리 삭제
    if verbose:
        logger.info("\n3️⃣  Deleting ECR Repository...")
    cleanup_status["ecr"] = delete_ecr_repository(
        repository_name="bedrock-agentcore-aiml301_sre_agentcore_supervisor_runtime",
        region=region_name,
        verbose=verbose,
        force=True,
    )

    # 4. Supervisor 관련 파일 삭제
    if verbose:
        logger.info("\n4️⃣  Deleting Supervisor Files...")
    files_cleanup = delete_supervisor_files(verbose=verbose)
    cleanup_status.update(files_cleanup)

    # 요약
    if verbose:
        logger.info("\n" + "=" * 70)
        logger.info("✅ Lab-05 Cleanup Summary:")
        for resource, status in cleanup_status.items():
            status_icon = "✓" if status else "✗"
            logger.info(f"   {status_icon} {resource.upper()}: {'SUCCESS' if status else 'FAILED'}")

        logger.info("\n💡 All Lab-05 supervisor resources have been cleaned up!")
        logger.info("=" * 70)

    return cleanup_status
