"""
Lab 01용 fault injection 함수
SRE 교육을 위한 일반적인 인프라 장애 세 가지를 구현합니다.
"""

import boto3
import json
import time
from typing import Dict
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor, as_completed
from .ssm_helper import get_stack_resources

# 향후 rollback에 사용할 수 있도록 원래 구성을 저장하는 전역 저장소
original_configs = {}


def initialize_fault_injection(region_name: str, profile_name: str = None) -> Dict[str, str]:
    """
    인프라 리소스 ID를 가져와 fault injection을 초기화합니다.

    인자:
        region_name: AWS 리전
        profile_name: AWS profile 이름(선택 사항)

    반환:
        리소스 식별자 딕셔너리
    """
    print("Retrieving infrastructure resources from SSM Parameter Store...")
    resources = get_stack_resources(region_name, profile_name)

    if len(resources) > 0:
        print(f"✅ Successfully retrieved {len(resources)} resource identifiers")
    else:
        print("❌ No resources retrieved - CloudFormation stack may not be deployed")

    return resources


def _update_single_table(dynamodb, table_name: str) -> tuple:
    """
    단일 DynamoDB 테이블을 용량이 낮은 PROVISIONED 모드로 변경합니다.
    병렬 실행용으로 설계되었습니다.

    반환:
        tuple: (table_name, success, original_billing_mode_or_error)
    """
    try:
        # rollback에 사용할 수 있도록 원래 billing mode 저장
        print(f"Processing table: {table_name}")
        table_info = dynamodb.describe_table(TableName=table_name)
        original_billing_mode = table_info["Table"]["BillingModeSummary"]["BillingMode"]
        print(f"  Original billing mode: {original_billing_mode}")  # codeql[py/clear-text-logging-sensitive-data]

        # 지나치게 낮은 제한의 provisioned capacity로 변환
        print("  Converting to PROVISIONED mode with minimal capacity...")
        dynamodb.update_table(
            TableName=table_name,
            BillingMode="PROVISIONED",
            ProvisionedThroughput={
                "ReadCapacityUnits": 1,  # 매우 낮아 제한 발생이 보장됨
                "WriteCapacityUnits": 1,  # 매우 낮아 제한 발생이 보장됨
            },
        )

        # 테이블 업데이트가 완료될 때까지 대기
        print(f"  Waiting for {table_name} update to complete...")
        waiter = dynamodb.get_waiter("table_exists")
        waiter.wait(
            TableName=table_name,
            WaiterConfig={
                "Delay": 2,  # 2초마다 확인(5초에서 단축)
                "MaxAttempts": 90,  # 최대 3분
            },
        )

        print(f"✅ Successfully updated {table_name}")
        return (table_name, True, original_billing_mode)

    except Exception as table_error:
        print(f"❌ Failed to update {table_name}: {table_error}")
        return (table_name, False, str(table_error))


def inject_dynamodb_throttling(resources: Dict[str, str], region_name: str, profile_name: str = None) -> bool:
    """
    테이블을 낮은 용량의 PROVISIONED 모드로 변경하여 DynamoDB 제한을 주입합니다.
    애플리케이션 워크로드에 비해 테이블 용량이 부족하여
    ProvisionedThroughputExceededException이 발생하는 일반적인 프로덕션 문제를 재현합니다.

    인자:
        resources: get_stack_resources()에서 가져온 리소스 식별자 딕셔너리
        region_name: AWS 리전
        profile_name: AWS profile 이름(선택 사항)

    반환:
        성공/실패 여부
    """
    try:
        # 리소스에서 DynamoDB 테이블 이름 목록 가져오기
        table_keys = [key for key in resources.keys() if key.endswith("_table_name") and "crm" in key]

        if not table_keys:
            print("❌ No DynamoDB table names found in resources")
            return False

        # DynamoDB 클라이언트 생성
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
            dynamodb = session.client("dynamodb")
        else:
            dynamodb = boto3.client("dynamodb", region_name=region_name)

        print(f"\nFound {len(table_keys)} DynamoDB table(s) to modify")
        print("Processing tables in parallel for faster execution...")
        print(f"\n{'=' * 60}")

        success_count = 0
        failed_tables = []

        # 테이블 이름 추출
        table_names = [resources.get(key) for key in table_keys if resources.get(key)]

        if not table_names:
            print("❌ No valid table names found")
            return False

        # 테이블을 동시에 처리
        max_workers = min(len(table_names), 10)  # 동시 작업을 10개로 제한

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 모든 테이블 업데이트 제출
            future_to_table = {
                executor.submit(_update_single_table, dynamodb, table_name): table_name for table_name in table_names
            }

            # 완료되는 대로 결과 수집
            for future in as_completed(future_to_table):
                table_name, success, result = future.result()

                if success:
                    # rollback용 원래 구성 저장
                    original_configs[f"dynamodb_billing_mode_{table_name}"] = result
                    success_count += 1
                else:
                    failed_tables.append(table_name)

        # 요약
        print(f"\n{'=' * 60}")
        print(f"Summary: {success_count}/{len(table_names)} tables updated successfully")
        if failed_tables:
            print(f"Failed tables: {', '.join(failed_tables)}")
        print(f"{'=' * 60}")

        return success_count > 0

    except Exception as e:
        print(f"❌ DynamoDB throttling injection failed: {e}")
        return False


def inject_iam_permissions(resources: Dict[str, str], region_name: str, profile_name: str = None) -> bool:
    """
    DynamoDB Allow policy를 Deny policy로 교체하여 IAM 권한 문제를 주입합니다.

    지나치게 제한적인 보안 policy나 실수로 변경된 policy 때문에 애플리케이션이
    필요한 AWS 리소스에 접근하지 못하는 일반적인 프로덕션 문제를 재현합니다.

    인자:
        resources: get_stack_resources()에서 가져온 리소스 식별자 딕셔너리
        region_name: AWS 리전
        profile_name: AWS profile 이름(선택 사항)

    반환:
        성공/실패 여부
    """
    try:
        ec2_role_name = resources.get("ec2_role_name")

        if not ec2_role_name:
            print("❌ EC2 role name not found in resources")
            return False

        # IAM 클라이언트 생성
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
            iam = session.client("iam")
        else:
            iam = boto3.client("iam", region_name=region_name)

        print(f"\nTarget IAM role: {ec2_role_name}")

        # rollback에 사용할 수 있도록 원래 policy 저장
        print("Backing up original DynamoDB policy...")
        try:
            original_policy = iam.get_role_policy(RoleName=ec2_role_name, PolicyName="DynamoDBAccess")
            original_configs["dynamodb_policy"] = original_policy["PolicyDocument"]
            print("  ✅ Original policy backed up (redacted)")
        except ClientError:
            print("  ⚠️  Could not backup original policy (may not exist)")

        # DynamoDB 접근을 거부하는 제한적 policy 생성
        print("\nApplying restrictive IAM policy...")
        print("  Technical details:")
        print("  - Replacing existing 'Allow' statements with 'Deny' statements")
        print("  - Targeting key DynamoDB operations used by the application")
        print("  - Deny policies override any Allow policies (explicit deny wins)")
        print("  - Will cause immediate AccessDenied errors for database operations")

        restricted_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Deny",
                    "Action": [
                        "dynamodb:PutItem",
                        "dynamodb:GetItem",
                        "dynamodb:Query",
                        "dynamodb:Scan",
                        "dynamodb:UpdateItem",
                        "dynamodb:DeleteItem",
                    ],
                    "Resource": "*",
                }
            ],
        }

        iam.put_role_policy(
            RoleName=ec2_role_name,
            PolicyName="DynamoDBAccess",
            PolicyDocument=json.dumps(restricted_policy),
        )

        return True

    except Exception as e:
        print(f"❌ IAM permission injection failed: {e}")
        return False


def inject_nginx_crash(resources: Dict[str, str], region_name: str, profile_name: str = None) -> bool:
    """
    AWS Systems Manager를 통해 nginx 프로세스를 종료하여 장애를 주입합니다.

    메모리 누수, segmentation fault 또는 리소스 고갈로 서비스가 중단되어
    ALB 상태 점검이 실패하는 일반적인 프로덕션 문제를 재현합니다.

    인자:
        resources: get_stack_resources()에서 가져온 리소스 식별자 딕셔너리
        region_name: AWS 리전
        profile_name: AWS profile 이름(선택 사항)

    반환:
        성공/실패 여부
    """
    try:
        nginx_instance_id = resources.get("nginx_instance_id")

        if not nginx_instance_id:
            print("❌ Nginx instance ID not found in resources")
            return False

        # SSM 클라이언트 생성
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
            ssm = session.client("ssm")
        else:
            ssm = boto3.client("ssm", region_name=region_name)

        print(f"\nTarget EC2 instance: {nginx_instance_id}")
        print("\nSimulating service crash by killing nginx process...")
        print("  Technical details:")
        print("  - Using 'pkill -9 nginx' to forcefully terminate nginx processes")
        print("  - This simulates common production crashes (memory leaks, segfaults, etc.)")
        print("  - ALB health checks will get 'connection refused' when trying to reach /health")
        print("  - After 3 consecutive failures (90 seconds), target marked as unhealthy")

        # 장애를 재현하도록 nginx 프로세스 종료
        crash_script = """
echo "Current nginx process status:"
sudo systemctl status nginx --no-pager -l || echo "Nginx not running"

echo -e "\\nKilling nginx process to simulate service crash..."
sudo pkill -9 nginx

echo -e "\\nWaiting 5 seconds..."
sleep 5

echo -e "\\nService status after crash:"
sudo systemctl status nginx --no-pager -l || echo "Nginx crashed (as expected)"

echo -e "\\nProcess check:"
ps aux | grep nginx | grep -v grep || echo "No nginx processes running"
"""

        print("\nExecuting crash simulation via AWS Systems Manager...")

        response = ssm.send_command(
            InstanceIds=[nginx_instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [crash_script]},
            Comment="SRE Workshop Lab-01: Simulate nginx service crash",
        )

        command_id = response["Command"]["CommandId"]
        print(f"  Command ID: {command_id}")

        # 명령 완료 대기
        print("  Waiting for crash simulation to complete...")
        time.sleep(10)

        result = ssm.get_command_invocation(CommandId=command_id, InstanceId=nginx_instance_id)

        if result["Status"] == "Success":
            return True
        else:
            print(f"  ❌ Command failed: {result['Status']}")
            if result.get("StandardErrorContent"):
                print(f"  Error: {result['StandardErrorContent']}")
            return False

    except Exception as e:
        print(f"❌ Nginx crash injection failed: {e}")
        return False


def inject_nginx_timeout(resources: Dict[str, str], region_name: str, profile_name: str = None) -> bool:
    """
    proxy timeout을 지나치게 짧게 설정하여 nginx timeout 구성 오류를 주입합니다.

    reverse proxy timeout이 백엔드 응답 시간을 고려하지 않아 502 Bad Gateway 오류가
    발생하는 일반적인 프로덕션 문제를 재현합니다.

    인자:
        resources: get_stack_resources()에서 가져온 리소스 식별자 딕셔너리
        region_name: AWS 리전
        profile_name: AWS profile 이름(선택 사항)

    반환:
        성공/실패 여부
    """
    try:
        nginx_instance_id = resources.get("nginx_instance_id")

        if not nginx_instance_id:
            print("❌ Nginx instance ID not found in resources")
            return False

        # SSM 클라이언트 생성
        if profile_name:
            session = boto3.Session(profile_name=profile_name, region_name=region_name)
            ssm = session.client("ssm")
        else:
            ssm = boto3.client("ssm", region_name=region_name)

        print(f"\nTarget EC2 instance: {nginx_instance_id}")
        print("\nInjecting nginx timeout misconfiguration...")
        print("  Technical details:")
        print("  - Setting proxy_read_timeout to 1 second (too short)")
        print("  - Backend queries taking >1s will trigger timeouts")
        print("  - Nginx returns 502 Bad Gateway when timeout occurs")
        print("  - Common issue when timeouts don't match backend SLAs")

        timeout_script = """
#!/bin/bash
set -e

# Backup original nginx.conf
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup

# Update nginx.conf with short timeouts
sudo sed -i 's/proxy_connect_timeout [0-9]*s;/proxy_connect_timeout 1s;/' /etc/nginx/nginx.conf
sudo sed -i 's/proxy_send_timeout [0-9]*s;/proxy_send_timeout 1s;/' /etc/nginx/nginx.conf
sudo sed -i 's/proxy_read_timeout [0-9]*s;/proxy_read_timeout 1s;/' /etc/nginx/nginx.conf

# Test configuration
sudo nginx -t

# Reload nginx to apply changes
sudo systemctl reload nginx

echo "Nginx timeout misconfiguration injected successfully"
"""

        print("\nExecuting timeout injection via AWS Systems Manager...")

        response = ssm.send_command(
            InstanceIds=[nginx_instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [timeout_script]},
            Comment="SRE Workshop Lab-01: Inject nginx timeout misconfiguration",
        )

        command_id = response["Command"]["CommandId"]
        print(f"  Command ID: {command_id}")

        # 명령 완료 대기
        print("  Waiting for injection to complete...")
        time.sleep(10)

        result = ssm.get_command_invocation(CommandId=command_id, InstanceId=nginx_instance_id)

        if result["Status"] == "Success":
            return True
        else:
            print(f"  ❌ Command failed: {result['Status']}")
            if result.get("StandardErrorContent"):
                print(f"  Error: {result['StandardErrorContent']}")
            return False

    except Exception as e:
        print(f"❌ Nginx timeout injection failed: {e}")
        return False
