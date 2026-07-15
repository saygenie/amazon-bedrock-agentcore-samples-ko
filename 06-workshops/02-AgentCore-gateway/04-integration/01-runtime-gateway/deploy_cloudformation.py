import boto3
import time
from botocore.exceptions import ClientError


def deploy_stack(stack_name, template_file, region, cf_client):
    """
    Customer Support Lambda용 CloudFormation 스택을 배포하거나 업데이트하고 출력을 반환합니다.

    인수:
        stack_name (str): CloudFormation 스택 이름
        template_file (str): CloudFormation 템플릿 YAML 파일 경로
        region (str): AWS 리전
        cf_client: Boto3 CloudFormation 클라이언트

    반환값:
        tuple: (lambda_arn, gateway_role_arn, runtime_execution_role_arn)
    """

    # 템플릿 파일 읽기
    try:
        with open(template_file, "r") as f:
            template_body = f.read()
        print(f"✅ Successfully read template file: {template_file}")
    except FileNotFoundError:
        raise FileNotFoundError(f"❌ Template file not found: {template_file}")
    except Exception as e:
        raise Exception(f"❌ Error reading template file: {str(e)}")

    # 스택이 있는지 확인
    stack_exists = False
    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        stack_status = response["Stacks"][0]["StackStatus"]
        stack_exists = True
        print(f"📋 Stack '{stack_name}' exists with status: {stack_status}")

        # 스택이 실패 상태인지 확인
        if stack_status in ["CREATE_FAILED", "ROLLBACK_COMPLETE", "ROLLBACK_FAILED"]:
            print(f"⚠️  Stack is in {stack_status} state. You may need to delete it first.")

    except ClientError as e:
        if "does not exist" in str(e):
            print(f"🆕 Stack '{stack_name}' does not exist. Will create new stack...")
        else:
            raise

    try:
        if stack_exists:
            # 기존 스택 업데이트
            print(f"🔄 Updating stack '{stack_name}'...")
            response = cf_client.update_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
                Tags=[
                    {"Key": "Application", "Value": "CustomerSupport"},
                    {"Key": "ManagedBy", "Value": "CloudFormation"},
                ],
            )
            print(f"✅ Stack update initiated. Stack ID: {response['StackId']}")
            waiter = cf_client.get_waiter("stack_update_complete")
            wait_message = "Waiting for stack update to complete"

        else:
            # 새 스택 생성
            print(f"🚀 Creating stack '{stack_name}'...")
            response = cf_client.create_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
                Tags=[
                    {"Key": "Application", "Value": "CustomerSupport"},
                    {"Key": "ManagedBy", "Value": "CloudFormation"},
                ],
                OnFailure="ROLLBACK",
            )
            print(f"✅ Stack creation initiated. Stack ID: {response['StackId']}")
            waiter = cf_client.get_waiter("stack_create_complete")
            wait_message = "Waiting for stack creation to complete"

        # 진행 상황을 업데이트하며 스택 작업 완료 대기
        print(f"⏳ {wait_message}...")
        print("   This may take several minutes as it creates:")
        print("   - DynamoDB tables (WarrantyTable, CustomerProfileTable)")
        print("   - IAM Roles (AgentCore, Gateway, Lambda roles)")
        print("   - Lambda functions (CustomerSupportLambda, PopulateDataFunction)")
        print("   - Custom resource to populate synthetic data")

        waiter.wait(
            StackName=stack_name,
            WaiterConfig={
                "Delay": 15,  # 15초마다 확인
                "MaxAttempts": 120,  # 최대 30분 대기
            },
        )
        print("✅ Stack operation completed successfully!")

    except ClientError as e:
        error_message = str(e)

        if "No updates are to be performed" in error_message:
            print("ℹ️  No updates needed - stack is already up to date.")
        elif "ValidationError" in error_message:
            print(f"❌ Validation error: {error_message}")
            raise
        else:
            print(f"❌ Error during stack operation: {error_message}")
            # 디버깅을 위해 스택 이벤트 조회 시도
            try:
                print("\n📋 Recent stack events:")
                events = cf_client.describe_stack_events(StackName=stack_name)
                for event in events["StackEvents"][:5]:
                    if "FAILED" in event.get("ResourceStatus", ""):
                        print(
                            f"   ❌ {event['LogicalResourceId']}: {event.get('ResourceStatusReason', 'No reason provided')}"
                        )
            except Exception:
                pass
            raise
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        raise

    # 스택 출력 가져오기
    print("\n📤 Retrieving stack outputs...")
    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response["Stacks"][0].get("Outputs", [])

        if not outputs:
            raise Exception("❌ No outputs found in stack. Stack may have failed to create properly.")

        # 템플릿에 따라 특정 출력 추출
        lambda_arn = None
        gateway_role_arn = None
        runtime_execution_role_arn = None

        for output in outputs:
            key = output["OutputKey"]
            value = output["OutputValue"]

            if key == "CustomerSupportLambdaArn":
                lambda_arn = value
                print(f"   ✅ Lambda ARN: {value}")
            elif key == "GatewayAgentCoreRoleArn":
                gateway_role_arn = value
                print(f"   ✅ Gateway Role ARN: {value}")
            elif key == "AgentCoreRuntimeExecutionRoleArn":
                runtime_execution_role_arn = value
                print(f"   ✅ Runtime Execution Role ARN: {value}")

        # 필요한 출력이 모두 확인되었는지 검증
        missing_outputs = []
        if not lambda_arn:
            missing_outputs.append("CustomerSupportLambdaArn")
        if not gateway_role_arn:
            missing_outputs.append("GatewayAgentCoreRoleArn")
        if not runtime_execution_role_arn:
            missing_outputs.append("AgentCoreRuntimeExecutionRoleArn")

        if missing_outputs:
            raise Exception(f"❌ Missing required outputs: {', '.join(missing_outputs)}")

        print("\n🎉 Stack deployment completed successfully!")
        print(f"   Stack Name: {stack_name}")
        print(f"   Region: {region}")

        return lambda_arn, gateway_role_arn, runtime_execution_role_arn

    except ClientError as e:
        print(f"❌ Error retrieving stack outputs: {str(e)}")
        raise
    except Exception as e:
        print(f"❌ Error processing stack outputs: {str(e)}")
        raise


def delete_stack(stack_name, region, cf_client, wait=True):
    """
    CloudFormation 스택과 모든 리소스를 삭제합니다.

    인수:
        stack_name (str): 삭제할 CloudFormation 스택 이름
        region (str): AWS 리전
        cf_client: Boto3 CloudFormation 클라이언트
        wait (bool): 삭제 완료를 기다릴지 여부(기본값: True)

    반환값:
        bool: 삭제에 성공하면 True, 그렇지 않으면 False
    """

    print(f"🗑️  Preparing to delete stack: {stack_name}")
    print(f"   Region: {region}")
    print("=" * 80)

    # 스택이 있는지 확인
    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        stack_status = response["Stacks"][0]["StackStatus"]
        print(f"📋 Current stack status: {stack_status}")

        # 스택이 이미 삭제 중인지 확인
        if stack_status == "DELETE_IN_PROGRESS":
            print("⏳ Stack deletion already in progress...")
            if wait:
                return _wait_for_deletion(stack_name, cf_client)
            return True

        # 스택이 실패 상태인지 확인
        if stack_status == "DELETE_FAILED":
            print("⚠️  Stack is in DELETE_FAILED state. Will attempt to retry deletion...")

    except ClientError as e:
        if "does not exist" in str(e):
            print(f"ℹ️  Stack '{stack_name}' does not exist. Nothing to delete.")
            return True
        else:
            print(f"❌ Error checking stack status: {str(e)}")
            raise

    # 보고를 위해 삭제 전에 리소스 조회
    try:
        print("\n📦 Resources to be deleted:")
        resources = cf_client.list_stack_resources(StackName=stack_name)
        resource_summary = {}

        for resource in resources["StackResourceSummaries"]:
            resource_type = resource["ResourceType"]
            logical_id = resource["LogicalResourceId"]
            physical_id = resource.get("PhysicalResourceId", "N/A")

            if resource_type not in resource_summary:
                resource_summary[resource_type] = []
            resource_summary[resource_type].append({"logical": logical_id, "physical": physical_id})

        for resource_type, items in sorted(resource_summary.items()):
            print(f"\n   {resource_type}:")
            for item in items:
                print(f"      - {item['logical']}")
                if resource_type == "AWS::DynamoDB::Table":
                    print(f"        ⚠️  Table: {item['physical']} (all data will be deleted)")
                elif resource_type == "AWS::Lambda::Function":
                    print(f"        🔧 Function: {item['physical']}")
                elif resource_type == "AWS::IAM::Role":
                    print(f"        🔐 Role: {item['physical']}")

        # 데이터가 있는 DynamoDB 테이블 확인
        dynamodb_tables = resource_summary.get("AWS::DynamoDB::Table", [])
        if dynamodb_tables:
            print(f"\n⚠️  WARNING: This will delete {len(dynamodb_tables)} DynamoDB table(s) and ALL their data!")
            dynamodb = boto3.client("dynamodb", region_name=region)
            for table in dynamodb_tables:
                try:
                    table_name = table["physical"]
                    response = dynamodb.scan(TableName=table_name, Select="COUNT", Limit=1)
                    if response["Count"] > 0:
                        print(f"      ⚠️  {table_name} contains data!")
                except Exception:
                    pass

    except ClientError as e:
        print(f"⚠️  Could not list resources: {str(e)}")

    # 삭제 확인
    print("\n" + "=" * 80)
    print("⚠️  THIS ACTION CANNOT BE UNDONE!")
    print("=" * 80)

    # 스택 삭제 시작
    try:
        print("\n🚀 Initiating stack deletion...")
        cf_client.delete_stack(StackName=stack_name)
        print("✅ Delete request submitted successfully")

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        if error_code == "ValidationError" and "does not exist" in error_message:
            print(f"ℹ️  Stack '{stack_name}' does not exist.")
            return True
        else:
            print(f"❌ Error initiating stack deletion: {error_message}")
            return False

    # 요청된 경우 삭제 완료 대기
    if wait:
        return _wait_for_deletion(stack_name, cf_client)
    else:
        print("\nℹ️  Stack deletion initiated but not waiting for completion.")
        return True


def _wait_for_deletion(stack_name, cf_client, max_wait_minutes=30):
    """
    스택 삭제가 완료될 때까지 기다리는 내부 함수입니다.

    인수:
        stack_name (str): 스택 이름
        cf_client: CloudFormation 클라이언트
        max_wait_minutes (int): 최대 대기 시간(분)

    반환값:
        bool: 삭제가 성공적으로 완료되면 True
    """
    print("\n⏳ Waiting for stack deletion to complete...")
    print(f"   This may take up to {max_wait_minutes} minutes")
    print("   Checking status every 15 seconds...")

    start_time = time.time()
    max_wait_seconds = max_wait_minutes * 60
    check_interval = 15
    last_status = None
    dots = 0

    try:
        while True:
            elapsed = time.time() - start_time

            if elapsed > max_wait_seconds:
                print(f"\n⚠️  Timeout: Stack deletion took longer than {max_wait_minutes} minutes")
                print("   Check AWS Console for current status")
                return False

            try:
                response = cf_client.describe_stacks(StackName=stack_name)
                current_status = response["Stacks"][0]["StackStatus"]

                # 상태가 변경되면 출력
                if current_status != last_status:
                    print(f"\n   Status: {current_status}")
                    last_status = current_status
                    dots = 0
                else:
                    # 진행 상황을 나타내는 점 출력
                    print(".", end="", flush=True)
                    dots += 1
                    if dots >= 20:
                        print()
                        dots = 0

                # 삭제 실패 확인
                if current_status == "DELETE_FAILED":
                    print("\n❌ Stack deletion failed!")
                    _print_deletion_errors(stack_name, cf_client)
                    return False

                # 아직 삭제 중
                if current_status == "DELETE_IN_PROGRESS":
                    time.sleep(check_interval)
                    continue

                # 예상하지 못한 상태
                print(f"\n⚠️  Unexpected status: {current_status}")
                return False

            except ClientError as e:
                if "does not exist" in str(e):
                    # 스택 삭제 성공
                    print(f"\n✅ Stack '{stack_name}' deleted successfully!")
                    elapsed_minutes = elapsed / 60
                    print(f"   Total time: {elapsed_minutes:.1f} minutes")
                    return True
                else:
                    # 기타 오류
                    print(f"\n❌ Error checking stack status: {str(e)}")
                    return False

    except KeyboardInterrupt:
        print("\n\n⚠️  Deletion monitoring interrupted by user")
        print("   Stack deletion will continue in the background")
        return False


def _print_deletion_errors(stack_name, cf_client):
    """
    실패한 스택 삭제의 상세 오류 메시지를 출력하는 내부 함수입니다.
    """
    try:
        print("\n📋 Deletion failure details:")
        events = cf_client.describe_stack_events(StackName=stack_name)

        failed_events = [event for event in events["StackEvents"] if "FAILED" in event.get("ResourceStatus", "")]

        if failed_events:
            for event in failed_events[:10]:  # 최근 실패 이벤트 10개 표시
                resource_type = event.get("ResourceType", "Unknown")
                logical_id = event.get("LogicalResourceId", "Unknown")
                reason = event.get("ResourceStatusReason", "No reason provided")

                print(f"\n   ❌ {resource_type} - {logical_id}")
                print(f"      Reason: {reason}")

        print("\n💡 Troubleshooting tips:")
        print("   1. Some resources may have dependencies preventing deletion")
        print("   2. Check if DynamoDB tables have deletion protection enabled")
        print("   3. Verify Lambda functions are not being invoked")
        print("   4. Try deleting the stack again after a few minutes")

    except Exception as e:
        print(f"   Could not retrieve error details: {str(e)}")


# ============================================================================
# 사용 예
# ============================================================================

if __name__ == "__main__":
    import boto3

    # 초기화
    session = boto3.Session()
    region = session.region_name
    stack_name = "customer-support-lambda-stack"
    template_file = "cloudformation/customer_support_lambda.yaml"
    cf_client = boto3.client("cloudformation", region_name=region)

    print("=" * 80)
    print("CLOUDFORMATION STACK MANAGEMENT")
    print("=" * 80)

    # CloudFormation 스택 배포
    print("\n🚀 DEPLOYING STACK...")
    print("=" * 80)

    try:
        lambda_arn, gateway_role_arn, runtime_execution_role_arn = deploy_stack(
            stack_name=stack_name,
            template_file=template_file,
            region=region,
            cf_client=cf_client,
        )

        print("\n" + "=" * 80)
        print("📋 DEPLOYMENT SUMMARY")
        print("=" * 80)
        print("\n🔧 Lambda Function ARN:")
        print(f"   {lambda_arn}")
        print("\n🔐 Gateway Role ARN:")
        print(f"   {gateway_role_arn}")
        print("\n🔐 Runtime Execution Role ARN:")
        print(f"   {runtime_execution_role_arn}")

    except Exception as e:
        print(f"\n❌ Deployment failed: {str(e)}")
        exit(1)

    # 선택 사항: 스택을 삭제하려면 주석 해제
    # print("\n\n🗑️  DELETING STACK...")
    # print("=" * 80)
    #
    # success = delete_stack(
    #     stack_name=stack_name,
    #     region=region,
    #     cf_client=cf_client,
    #     wait=True
    # )
    #
    # if success:
    #     print("\n🎉 Stack deleted successfully!")
    # else:
    #     print("\n❌ Stack deletion failed")
