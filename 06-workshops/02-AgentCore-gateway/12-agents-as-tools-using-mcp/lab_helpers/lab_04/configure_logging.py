#!/usr/bin/env python3
"""
AgentCore Runtime용 CloudWatch Logs Delivery 구성

이 모듈은 AgentCore Runtime의 컨테이너 로그(stdout/stderr)를 CloudWatch로
전송할 수 있도록 CloudWatch Logs Delivery를 구성하는 기능을 제공합니다.

AWS 문서 기반:
- https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html
- https://docs.aws.amazon.com/AmazonCloudWatchLogs/latest/APIReference/API_PutDeliverySource.html
"""

import boto3
import time
from typing import Dict


def configure_runtime_logging(
    runtime_arn: str,
    runtime_id: str,
    region: str = "us-west-2",
    log_type: str = "APPLICATION_LOGS",
) -> Dict[str, str]:
    """
    AgentCore Runtime용 CloudWatch Logs Delivery를 구성합니다.

    이 함수는 전체 로깅 파이프라인을 설정합니다.
    1. CloudWatch Log Group 생성
    2. Delivery Source 생성(Runtime ARN에 연결)
    3. Delivery Destination 생성(Log Group에 연결)
    4. Delivery 생성(Source와 Destination 연결)

    인자:
        runtime_arn: AgentCore Runtime의 전체 ARN
        runtime_id: Runtime ID(ARN의 마지막 세그먼트)
        region: AWS 리전(기본값: us-west-2)
        log_type: 로그 유형(기본값: APPLICATION_LOGS)
                  유효한 값: APPLICATION_LOGS, USAGE_LOGS, TRACES

    반환:
        다음 항목이 포함된 딕셔너리:
        - log_group_name: 생성된 로그 그룹 이름
        - delivery_source_arn: Delivery Source ARN
        - delivery_destination_arn: Delivery Destination ARN
        - delivery_id: Delivery ID
        - delivery_status: Delivery 상태

    예외:
        Exception: 중요한 단계가 실패한 경우

    예:
        >>> result = configure_runtime_logging(
        ...     runtime_arn="arn:aws:bedrock-agentcore:us-west-2:123:runtime/my-runtime-ABC",
        ...     runtime_id="my-runtime-ABC",
        ...     region="us-west-2"
        ... )
        >>> print(f"Logs at: {result['log_group_name']}")
    """

    print("\n" + "=" * 80)
    print("🔧 Configuring CloudWatch Logs Delivery for AgentCore Runtime")
    print("=" * 80)

    # AWS 클라이언트 초기화
    logs_client = boto3.client("logs", region_name=region)

    # Runtime ARN에서 AWS 계정 ID 가져오기
    account_id = runtime_arn.split(":")[4]

    # 파생 구성
    log_group_name = f"/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT"

    # 이름을 60자 제한 이내로 유지하기 위해 runtime_id의 마지막 12자 추출
    # AWS API에서는 Delivery Source/Destination 이름이 60자 이하여야 함
    short_id = runtime_id.split("-")[-1]  # 고유 접미사 가져오기(예: "V5wJhp4zqq")
    delivery_source_name = f"aiml301-lab04-src-{short_id}"
    delivery_destination_name = f"aiml301-lab04-dst-{short_id}"

    print("\n📋 Configuration:")
    print(f"  Runtime ARN: {runtime_arn}")
    print(f"  Runtime ID: {runtime_id}")
    print(f"  Log Group: {log_group_name}")
    print(f"  Region: {region}")
    print(f"  Log Type: {log_type}")

    result = {
        "log_group_name": log_group_name,
        "delivery_source_arn": None,
        "delivery_destination_arn": None,
        "delivery_id": None,
        "delivery_status": None,
    }

    # 1단계: Log Group 생성
    print("\n📋 Step 1: Creating CloudWatch Log Group...")
    try:
        logs_client.create_log_group(logGroupName=log_group_name)
        print(f"  ✅ Created log group: {log_group_name}")
    except logs_client.exceptions.ResourceAlreadyExistsException:
        print(f"  ℹ️  Log group already exists: {log_group_name}")
    except Exception as e:
        print(f"  ⚠️  Warning: {e}")

    # 2단계: Delivery Source 생성
    print("\n📋 Step 2: Creating Delivery Source...")
    try:
        response = logs_client.put_delivery_source(
            name=delivery_source_name,
            resourceArn=runtime_arn,
            logType=log_type,
            tags={"Project": "AIML301", "Lab": "Lab-03", "ManagedBy": "Workshop"},
        )

        result["delivery_source_arn"] = response["deliverySource"]["arn"]
        print("  ✅ Created delivery source")
        print(f"     ARN: {result['delivery_source_arn']}")
        print(f"     Name: {delivery_source_name}")

    except logs_client.exceptions.ResourceAlreadyExistsException:
        print(f"  ℹ️  Delivery source already exists: {delivery_source_name}")
        response = logs_client.get_delivery_source(name=delivery_source_name)
        result["delivery_source_arn"] = response["deliverySource"]["arn"]
        print(f"     ARN: {result['delivery_source_arn']}")
    except Exception as e:
        print(f"  ❌ Failed to create delivery source: {e}")
        raise

    # 3단계: Delivery Destination 생성
    print("\n📋 Step 3: Creating Delivery Destination...")
    try:
        response = logs_client.put_delivery_destination(
            name=delivery_destination_name,
            deliveryDestinationConfiguration={
                "destinationResourceArn": f"arn:aws:logs:{region}:{account_id}:log-group:{log_group_name}"
            },
            tags={"Project": "AIML301", "Lab": "Lab-03", "ManagedBy": "Workshop"},
        )

        result["delivery_destination_arn"] = response["deliveryDestination"]["arn"]
        print("  ✅ Created delivery destination")
        print(f"     ARN: {result['delivery_destination_arn']}")
        print(f"     Target: {log_group_name}")

    except logs_client.exceptions.ResourceAlreadyExistsException:
        print(f"  ℹ️  Delivery destination already exists: {delivery_destination_name}")
        response = logs_client.get_delivery_destination(name=delivery_destination_name)
        result["delivery_destination_arn"] = response["deliveryDestination"]["arn"]
        print(f"     ARN: {result['delivery_destination_arn']}")
    except Exception as e:
        print(f"  ❌ Failed to create delivery destination: {e}")
        raise

    # 4단계: Delivery 생성(Source를 Destination에 연결)
    print("\n📋 Step 4: Creating Delivery (linking source to destination)...")
    try:
        response = logs_client.create_delivery(
            deliverySourceName=delivery_source_name,
            deliveryDestinationArn=result["delivery_destination_arn"],
            tags={"Project": "AIML301", "Lab": "Lab-03", "ManagedBy": "Workshop"},
        )

        result["delivery_id"] = response["delivery"]["id"]
        print("  ✅ Created delivery")
        print(f"     ID: {result['delivery_id']}")
        print(f"     ARN: {response['delivery']['arn']}")

    except logs_client.exceptions.ResourceAlreadyExistsException:
        print("  ℹ️  Delivery already exists for this source")
        # 기존 Delivery 찾기
        response = logs_client.describe_deliveries()
        for delivery in response.get("deliveries", []):
            if delivery.get("deliverySourceName") == delivery_source_name:
                result["delivery_id"] = delivery["id"]
                print(f"     ID: {result['delivery_id']}")
                break
    except Exception as e:
        print(f"  ⚠️  Warning creating delivery: {e}")
        print("  ℹ️  Delivery may already exist - continuing...")

    # 5단계: Delivery 상태 확인
    print("\n📋 Step 5: Verifying delivery status...")
    time.sleep(2)  # AWS 변경 사항 전파 대기

    try:
        response = logs_client.describe_deliveries()

        for delivery in response.get("deliveries", []):
            if delivery.get("deliverySourceName") == delivery_source_name:
                result["delivery_status"] = delivery.get("deliveryStatus", "UNKNOWN")
                print(f"  ✅ Delivery Status: {result['delivery_status']}")
                print(f"     Source: {delivery.get('deliverySourceName')}")
                print(f"     Destination: {delivery.get('deliveryDestinationArn')}")

                if result["delivery_status"] == "ENABLED":
                    print("\n  🎉 Delivery is ENABLED - logs should flow to CloudWatch!")
                break

    except Exception as e:
        print(f"  ⚠️  Could not verify delivery status: {e}")

    print("\n" + "=" * 80)
    print("✅ CloudWatch Logs Delivery Configuration Complete")
    print("=" * 80)
    print(f"\n📊 View logs at: {log_group_name}")
    print("\n💻 Command to tail logs:")
    print(f"   aws logs tail {log_group_name} --follow --region {region}")
    print()

    return result


def cleanup_runtime_logging(runtime_id: str, region: str = "us-west-2") -> bool:
    """
    Runtime의 CloudWatch Logs Delivery 구성을 정리합니다.

    다음 항목을 제거합니다.
    - Delivery(Source와 Destination 간 연결)
    - Delivery Source
    - Delivery Destination
    - Log Group(선택 사항, 기본적으로 주석 처리됨)

    인자:
        runtime_id: Runtime ID(ARN의 마지막 세그먼트)
        region: AWS 리전(기본값: us-west-2)

    반환:
        정리에 성공하면 True, 그렇지 않으면 False
    """

    print("\n" + "=" * 80)
    print("🧹 Cleaning up CloudWatch Logs Delivery Configuration")
    print("=" * 80)

    logs_client = boto3.client("logs", region_name=region)

    # configure_runtime_logging과 동일한 명명 규칙 사용
    short_id = runtime_id.split("-")[-1]
    delivery_source_name = f"aiml301-lab04-src-{short_id}"
    delivery_destination_name = f"aiml301-lab04-dst-{short_id}"
    log_group_name = f"/aws/bedrock-agentcore/runtimes/{runtime_id}-DEFAULT"

    success = True

    # 1단계: Delivery 삭제
    print(f"\n📋 Step 1: Deleting delivery for source: {delivery_source_name}...")
    try:
        response = logs_client.describe_deliveries()
        delivery_id = None

        for delivery in response.get("deliveries", []):
            if delivery.get("deliverySourceName") == delivery_source_name:
                delivery_id = delivery["id"]
                break

        if delivery_id:
            logs_client.delete_delivery(id=delivery_id)
            print(f"  ✅ Deleted delivery: {delivery_id}")
        else:
            print(f"  ℹ️  No delivery found for source: {delivery_source_name}")

    except Exception as e:
        print(f"  ⚠️  Error deleting delivery: {e}")
        success = False

    # 2단계: Delivery Source 삭제
    print(f"\n📋 Step 2: Deleting delivery source: {delivery_source_name}...")
    try:
        logs_client.delete_delivery_source(name=delivery_source_name)
        print(f"  ✅ Deleted delivery source: {delivery_source_name}")
    except logs_client.exceptions.ResourceNotFoundException:
        print(f"  ℹ️  Delivery source not found: {delivery_source_name}")
    except Exception as e:
        print(f"  ⚠️  Error deleting delivery source: {e}")
        success = False

    # 3단계: Delivery Destination 삭제
    print(f"\n📋 Step 3: Deleting delivery destination: {delivery_destination_name}...")
    try:
        logs_client.delete_delivery_destination(name=delivery_destination_name)
        print(f"  ✅ Deleted delivery destination: {delivery_destination_name}")
    except logs_client.exceptions.ResourceNotFoundException:
        print(f"  ℹ️  Delivery destination not found: {delivery_destination_name}")
    except Exception as e:
        print(f"  ⚠️  Error deleting delivery destination: {e}")
        success = False

    # 4단계: Log Group 삭제(선택 사항, 기본적으로 주석 처리됨)
    # 정리 중 로그 그룹도 삭제하려면 주석을 해제
    print(f"\n📋 Step 4: Deleting log group: {log_group_name}...")
    try:
        logs_client.delete_log_group(logGroupName=log_group_name)
        print(f"  ✅ Deleted log group: {log_group_name}")
    except logs_client.exceptions.ResourceNotFoundException:
        print(f"  ℹ️  Log group not found: {log_group_name}")
    except Exception as e:
        print(f"  ⚠️  Error deleting log group: {e}")
        success = False

    print("\n" + "=" * 80)
    if success:
        print("✅ Cleanup Complete")
    else:
        print("⚠️  Cleanup completed with warnings")
    print("=" * 80)
    print()

    return success


if __name__ == "__main__":
    # 사용 예
    import sys

    if len(sys.argv) < 3:
        print("Usage:")
        print("  Configure logging:")
        print("    python configure_logging.py <runtime_arn> <runtime_id>")
        print()
        print("  Cleanup logging:")
        print("    python configure_logging.py cleanup <runtime_id>")
        sys.exit(1)

    if sys.argv[1] == "cleanup":
        runtime_id = sys.argv[2]
        cleanup_runtime_logging(runtime_id)
    else:
        runtime_arn = sys.argv[1]
        runtime_id = sys.argv[2]
        configure_runtime_logging(runtime_arn, runtime_id)
