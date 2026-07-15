import boto3
import json
import time
from boto3.session import Session
from botocore.exceptions import ClientError
import requests


def get_or_create_user_pool(cognito, USER_POOL_NAME):
    response = cognito.list_user_pools(MaxResults=60)
    for pool in response["UserPools"]:
        if pool["Name"] == USER_POOL_NAME:
            user_pool_id = pool["Id"]
            response = cognito.describe_user_pool(UserPoolId=user_pool_id)

            # User Pool 설명에서 도메인 가져오기
            user_pool = response.get("UserPool", {})
            domain = user_pool.get("Domain")

            if domain:
                region = user_pool_id.split("_")[0] if "_" in user_pool_id else REGION  # noqa: F821
                domain_url = f"https://{domain}.auth.{region}.amazoncognito.com"
                print(f"Found domain for user pool {user_pool_id}: {domain} ({domain_url})")
            else:
                print(f"No domains found for user pool {user_pool_id}")
            return pool["Id"]
    print("Creating new user pool")
    created = cognito.create_user_pool(PoolName=USER_POOL_NAME)
    user_pool_id = created["UserPool"]["Id"]
    user_pool_id_without_underscore_lc = user_pool_id.replace("_", "").lower()
    cognito.create_user_pool_domain(Domain=user_pool_id_without_underscore_lc, UserPoolId=user_pool_id)
    print("Domain created as well")
    return created["UserPool"]["Id"]


def get_or_create_resource_server(cognito, user_pool_id, RESOURCE_SERVER_ID, RESOURCE_SERVER_NAME, SCOPES):
    try:
        existing = cognito.describe_resource_server(  # noqa: F841
            UserPoolId=user_pool_id, Identifier=RESOURCE_SERVER_ID
        )
        return RESOURCE_SERVER_ID
    except cognito.exceptions.ResourceNotFoundException:
        print("creating new resource server")
        cognito.create_resource_server(
            UserPoolId=user_pool_id,
            Identifier=RESOURCE_SERVER_ID,
            Name=RESOURCE_SERVER_NAME,
            Scopes=SCOPES,
        )
        return RESOURCE_SERVER_ID


def get_or_create_m2m_client(cognito, user_pool_id, CLIENT_NAME, RESOURCE_SERVER_ID, SCOPES=None):
    response = cognito.list_user_pool_clients(UserPoolId=user_pool_id, MaxResults=60)
    for client in response["UserPoolClients"]:
        if client["ClientName"] == CLIENT_NAME:
            describe = cognito.describe_user_pool_client(UserPoolId=user_pool_id, ClientId=client["ClientId"])
            return client["ClientId"], describe["UserPoolClient"]["ClientSecret"]
    print("creating new m2m client")

    # 제공되지 않은 경우 이전 버전과의 호환성을 위해 기본 scope 사용
    if SCOPES is None:
        SCOPES = [
            f"{RESOURCE_SERVER_ID}/gateway:read",
            f"{RESOURCE_SERVER_ID}/gateway:write",
        ]

    created = cognito.create_user_pool_client(
        UserPoolId=user_pool_id,
        ClientName=CLIENT_NAME,
        GenerateSecret=True,
        AllowedOAuthFlows=["client_credentials"],
        AllowedOAuthScopes=SCOPES,
        AllowedOAuthFlowsUserPoolClient=True,
        SupportedIdentityProviders=["COGNITO"],
        ExplicitAuthFlows=["ALLOW_REFRESH_TOKEN_AUTH"],
    )
    return created["UserPoolClient"]["ClientId"], created["UserPoolClient"]["ClientSecret"]


def get_token(
    user_pool_id: str,
    client_id: str,
    client_secret: str,
    scope_string: str,
    REGION: str,
) -> dict:
    try:
        user_pool_id_without_underscore = user_pool_id.replace("_", "")
        url = f"https://{user_pool_id_without_underscore}.auth.{REGION}.amazoncognito.com/oauth2/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope_string,
        }
        print(client_id)
        response = requests.post(url, headers=headers, data=data, timeout=30)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as err:
        return {"error": str(err)}


def create_agentcore_gateway_role(gateway_name):
    iam_client = boto3.client("iam")
    agentcore_gateway_role_name = f"agentcore-{gateway_name}-role"
    boto_session = Session()
    region = boto_session.region_name
    account_id = boto3.client("sts").get_caller_identity()["Account"]
    role_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "VisualEditor0",
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:*",
                    "bedrock:*",
                    "agent-credential-provider:*",
                    "iam:PassRole",
                    "secretsmanager:GetSecretValue",
                    "lambda:InvokeFunction",
                    "execute-api:Invoke",
                ],
                "Resource": "*",
            }
        ],
    }

    assume_role_policy_document = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AssumeRolePolicy",
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {"aws:SourceAccount": f"{account_id}"},
                    "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"},
                },
            }
        ],
    }

    assume_role_policy_document_json = json.dumps(assume_role_policy_document)

    role_policy_document = json.dumps(role_policy)
    # Lambda 함수용 IAM 역할 생성
    try:
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_gateway_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json,
        )

        # 역할이 생성되도록 잠시 대기
        time.sleep(10)
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("Role already exists -- deleting and creating it again")
        policies = iam_client.list_role_policies(RoleName=agentcore_gateway_role_name, MaxItems=100)
        print("policies:", policies)
        for policy_name in policies["PolicyNames"]:
            iam_client.delete_role_policy(RoleName=agentcore_gateway_role_name, PolicyName=policy_name)
        print(f"deleting {agentcore_gateway_role_name}")
        iam_client.delete_role(RoleName=agentcore_gateway_role_name)
        print(f"recreating {agentcore_gateway_role_name}")
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_gateway_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json,
        )

    # AWSLambdaBasicExecutionRole policy 연결
    print(f"attaching role policy {agentcore_gateway_role_name}")
    try:
        iam_client.put_role_policy(
            PolicyDocument=role_policy_document,
            PolicyName="AgentCorePolicy",
            RoleName=agentcore_gateway_role_name,
        )
    except Exception as e:
        print(e)

    return agentcore_iam_role


def load_openapi_definition(filename):
    """
    JSON 파일에서 OpenAPI 정의를 불러옵니다.

    :param filename: OpenAPI JSON 파일 경로
    :return: OpenAPI 정의가 포함된 딕셔너리
    """
    with open(filename, "r") as f:
        return json.load(f)


def create_and_deploy_api_from_openapi_with_extensions(
    filename="AgentCore_Sample_API-dev-oas30-apigateway.json",
    stage_name="dev",
    description="Initial Deployment",
):
    """
    API Gateway 확장이 포함된 OpenAPI 정의를 불러와 배포합니다.
    OpenAPI 문서에 통합 및 보안 구성이 이미 설정되어 있어야 합니다.

    :param filename: x-amazon-apigateway 확장이 포함된 OpenAPI JSON 파일 경로
    :param stage_name: 배포 stage 이름(기본값: 'dev')
    :param description: 배포 설명(기본값: 'Initial Deployment')
    :return: api_id, api_name, api_key, invoke_url이 포함된 딕셔너리
    """
    import boto3

    # API Gateway 클라이언트 초기화
    client = boto3.client("apigateway")

    # 파일에서 OpenAPI 정의 불러오기
    openapi_definition = load_openapi_definition(filename)

    try:
        # OpenAPI 정의를 JSON 문자열로 변환
        body = json.dumps(openapi_definition)

        print("Importing REST API with API Gateway extensions...")
        # OpenAPI 정의를 사용해 REST API 가져오기
        response = client.import_rest_api(
            body=body,
            failOnWarnings=False,
            parameters={"endpointConfigurationTypes": "REGIONAL"},
        )

        api_id = response["id"]
        api_name = response["name"]

        print("✓ API Gateway REST API created successfully")
        print(f"  API ID: {api_id}")
        print(f"  API Name: {api_name}")

        # API 배포
        print(f"\nDeploying API to stage '{stage_name}'...")
        deployment_response = client.create_deployment(restApiId=api_id, stageName=stage_name, description=description)

        deployment_id = deployment_response["id"]
        print(f"✓ Deployment created: {deployment_id}")

        # orders 엔드포인트용 API Key 생성
        print("\nCreating API Key...")
        api_key_response = client.create_api_key(
            name=f"{api_name}-api-key",
            description=f"API Key for {api_name} orders endpoint",
            enabled=True,
        )
        api_key_id = api_key_response["id"]
        api_key_value = api_key_response["value"]
        print(f"✓ API Key created: {api_key_id}")

        # Usage Plan 생성  # codeql[py/clear-text-logging-sensitive-data]
        print("\nCreating Usage Plan...")
        usage_plan_response = client.create_usage_plan(
            name=f"{api_name}-usage-plan",
            description=f"Usage plan for {api_name}",
            apiStages=[{"apiId": api_id, "stage": stage_name}],
            throttle={"rateLimit": 100.0, "burstLimit": 200},
            quota={"limit": 10000, "period": "MONTH"},
        )
        usage_plan_id = usage_plan_response["id"]
        print(f"✓ Usage Plan created: {usage_plan_id}")

        # API Key를 Usage Plan과 연결
        print("\nAssociating API Key with Usage Plan...")
        client.create_usage_plan_key(usagePlanId=usage_plan_id, keyId=api_key_id, keyType="API_KEY")
        print("✓ API Key associated with Usage Plan")

        # 호출 URL 구성
        region = client.meta.region_name
        invoke_url = f"https://{api_id}.execute-api.{region}.amazonaws.com/{stage_name}"

        print(f"\n{'=' * 70}")
        print("API Gateway Deployment Complete")
        print(f"{'=' * 70}")
        print(f"Invoke URL: {invoke_url}")
        print("\nEndpoint Authorization:")
        print("  • GET /pets              → AWS IAM (SigV4)")
        print("  • POST /pets             → AWS IAM (SigV4)")
        print("  • GET /pets/{petId}      → AWS IAM (SigV4)")
        print("  • GET /orders/{orderId}  → API Key (x-api-key header)")
        print(f"{'=' * 70}")

        return {
            "api_id": api_id,
            "api_name": api_name,
            "deployment_id": deployment_id,
            "invoke_url": invoke_url,
            "stage_name": stage_name,
            "api_key_id": api_key_id,
            "api_key_value": api_key_value,
            "usage_plan_id": usage_plan_id,
        }

    except client.exceptions.ConflictException:
        print("An API with the specified name already exists. Consider updating or deleting existing API.")
        raise
    except Exception as e:
        print(f"Error creating or deploying API Gateway REST API: {e}")
        raise


def test_api_gateway_endpoints(invoke_url, api_key, region):
    """
    올바른 권한 부여를 사용해 API Gateway 엔드포인트를 테스트합니다.
    IAM 권한을 사용하는 /pets 엔드포인트와 API Key 권한을 사용하는 /orders 엔드포인트를 모두 테스트합니다.

    :param invoke_url: API Gateway 호출 URL
    :param api_key: /orders 엔드포인트용 API Key
    :param region: AWS 리전(기본값: 'us-west-2')
    :return: 테스트 결과가 포함된 딕셔너리
    """
    import boto3
    import requests
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest

    print(f"\n{'=' * 70}")
    print("Testing API Gateway Endpoints")
    print(f"{'=' * 70}\n")

    results = {}
    session = boto3.Session()
    credentials = session.get_credentials()

    # 테스트 1: GET /pets(IAM 권한 부여)
    print("1. Testing GET /pets (IAM Authorization)...")
    try:
        url = f"{invoke_url}/pets"
        request = AWSRequest(method="GET", url=url)
        SigV4Auth(credentials, "execute-api", region).add_auth(request)

        response = requests.get(url, headers=dict(request.headers), timeout=30)

        if response.status_code == 200:
            print(f"   ✓ SUCCESS (Status: {response.status_code})")
            print(f"   Response: {response.json()}")
            results["get_pets"] = {"status": "success", "data": response.json()}
        else:
            print(f"   ✗ FAILED (Status: {response.status_code})")
            print(f"   Response: {response.text}")
            results["get_pets"] = {"status": "failed", "error": response.text}
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
        results["get_pets"] = {"status": "error", "error": str(e)}

    # 테스트 2: GET /pets/1(IAM 권한 부여)
    print("\n2. Testing GET /pets/1 (IAM Authorization)...")
    try:
        url = f"{invoke_url}/pets/1"
        request = AWSRequest(method="GET", url=url)
        SigV4Auth(credentials, "execute-api", region).add_auth(request)

        response = requests.get(url, headers=dict(request.headers), timeout=30)

        if response.status_code == 200:
            print(f"   ✓ SUCCESS (Status: {response.status_code})")
            print(f"   Response: {response.json()}")
            results["get_pet_by_id"] = {"status": "success", "data": response.json()}
        else:
            print(f"   ✗ FAILED (Status: {response.status_code})")
            print(f"   Response: {response.text}")
            results["get_pet_by_id"] = {"status": "failed", "error": response.text}
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
        results["get_pet_by_id"] = {"status": "error", "error": str(e)}

    # 테스트 3: POST /pets(IAM 권한 부여)
    print("\n3. Testing POST /pets (IAM Authorization)...")
    try:
        url = f"{invoke_url}/pets"
        request = AWSRequest(method="POST", url=url, data="{}")
        SigV4Auth(credentials, "execute-api", region).add_auth(request)

        response = requests.post(url, headers=dict(request.headers), json={}, timeout=30)

        if response.status_code == 200:
            print(f"   ✓ SUCCESS (Status: {response.status_code})")
            print(f"   Response: {response.json()}")
            results["post_pets"] = {"status": "success", "data": response.json()}
        else:
            print(f"   ✗ FAILED (Status: {response.status_code})")
            print(f"   Response: {response.text}")
            results["post_pets"] = {"status": "failed", "error": response.text}
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
        results["post_pets"] = {"status": "error", "error": str(e)}

    # 테스트 4: GET /orders/1(API Key 권한 부여)
    print("\n4. Testing GET /orders/1 (API Key Authorization)...")
    try:
        url = f"{invoke_url}/orders/1"
        headers = {"x-api-key": api_key}

        response = requests.get(url, headers=headers, timeout=30)

        if response.status_code == 200:
            print(f"   ✓ SUCCESS (Status: {response.status_code})")
            print(f"   Response: {response.json()}")
            results["get_order_by_id"] = {"status": "success", "data": response.json()}
        else:
            print(f"   ✗ FAILED (Status: {response.status_code})")
            print(f"   Response: {response.text}")
            results["get_order_by_id"] = {"status": "failed", "error": response.text}
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
        results["get_order_by_id"] = {"status": "error", "error": str(e)}

    # 테스트 5: API Key 없이 GET /orders/1 호출(실패해야 함)
    print("\n5. Testing GET /orders/1 WITHOUT API Key (should fail with 403)...")
    try:
        url = f"{invoke_url}/orders/1"
        response = requests.get(url, timeout=30)

        if response.status_code == 403:
            print(f"   ✓ EXPECTED FAILURE (Status: {response.status_code})")
            print(f"   Response: {response.json()}")
            results["get_order_no_key"] = {
                "status": "expected_failure",
                "data": response.json(),
            }
        else:
            print(f"   ✗ UNEXPECTED (Status: {response.status_code})")
            print(f"   Response: {response.text}")
            results["get_order_no_key"] = {
                "status": "unexpected",
                "error": response.text,
            }
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
        results["get_order_no_key"] = {"status": "error", "error": str(e)}

    # 테스트 6: IAM 인증 없이 GET /pets 호출(실패해야 함)
    print("\n6. Testing GET /pets WITHOUT IAM Auth (should fail with 403)...")
    try:
        url = f"{invoke_url}/pets"
        response = requests.get(url, timeout=30)

        if response.status_code == 403:
            print(f"   ✓ EXPECTED FAILURE (Status: {response.status_code})")
            print(f"   Response: {response.json()}")
            results["get_pets_no_auth"] = {
                "status": "expected_failure",
                "data": response.json(),
            }
        else:
            print(f"   ✗ UNEXPECTED (Status: {response.status_code})")
            print(f"   Response: {response.text}")
            results["get_pets_no_auth"] = {
                "status": "unexpected",
                "error": response.text,
            }
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
        results["get_pets_no_auth"] = {"status": "error", "error": str(e)}

    print(f"\n{'=' * 70}")
    print("Test Summary")
    print(f"{'=' * 70}")
    success_count = sum(1 for r in results.values() if r["status"] in ["success", "expected_failure"])
    total_count = len(results)
    print(f"Passed: {success_count}/{total_count}")
    print(f"{'=' * 70}\n")

    return results


def delete_api_gateway_and_resources(api_id, api_key_id=None, usage_plan_id=None):
    """
    API Gateway와 모든 관련 리소스(API Key, Usage Plan)를 삭제합니다.

    :param api_id: API Gateway REST API ID
    :param api_key_id: API Key ID(선택 사항)
    :param usage_plan_id: Usage Plan ID(선택 사항)
    :return: 삭제 결과가 포함된 딕셔너리
    """
    import boto3

    client = boto3.client("apigateway")
    results = {
        "api_deleted": False,
        "api_key_deleted": False,
        "usage_plan_deleted": False,
        "errors": [],
    }

    print(f"\n{'=' * 70}")
    print("Deleting API Gateway Resources")
    print(f"{'=' * 70}\n")

    # Usage Plan과 API Key가 있으면 Usage Plan Key 연결부터 삭제
    if usage_plan_id and api_key_id:
        try:
            print("1. Removing API Key from Usage Plan...")
            client.delete_usage_plan_key(usagePlanId=usage_plan_id, keyId=api_key_id)
            print("   ✓ API Key removed from Usage Plan")
        except ClientError as e:
            error_msg = f"Failed to remove API Key from Usage Plan: {e}"
            print(f"   ✗ {error_msg}")
            results["errors"].append(error_msg)
        except Exception as e:
            error_msg = f"Error removing API Key from Usage Plan: {e}"
            print(f"   ✗ {error_msg}")
            results["errors"].append(error_msg)

    # Usage Plan 삭제
    if usage_plan_id:
        try:
            print(f"\n2. Deleting Usage Plan: {usage_plan_id}...")

            # 연결된 API stage를 찾기 위해 먼저 Usage Plan 가져오기
            try:
                usage_plan = client.get_usage_plan(usagePlanId=usage_plan_id)
                api_stages = usage_plan.get("apiStages", [])

                if api_stages:
                    print(f"   Found {len(api_stages)} associated API stage(s)")
                    for stage in api_stages:
                        api_id_stage = stage.get("apiId")
                        stage_name = stage.get("stage")
                        print(f"   Removing API stage: {api_id_stage}/{stage_name}...")
                        try:
                            client.update_usage_plan(
                                usagePlanId=usage_plan_id,
                                patchOperations=[
                                    {
                                        "op": "remove",
                                        "path": "/apiStages",
                                        "value": f"{api_id_stage}:{stage_name}",
                                    }
                                ],
                            )
                            print("   ✓ API stage removed")
                        except Exception as e:
                            print(f"   ⚠ Could not remove API stage: {e}")
            except Exception as e:
                print(f"   ⚠ Could not get usage plan details: {e}")

            # Usage Plan 삭제
            client.delete_usage_plan(usagePlanId=usage_plan_id)
            print("   ✓ Usage Plan deleted")
            results["usage_plan_deleted"] = True
        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                print("   ⚠ Usage Plan not found (may already be deleted)")
                results["usage_plan_deleted"] = True
            else:
                error_msg = f"Failed to delete Usage Plan: {e}"
                print(f"   ✗ {error_msg}")
                results["errors"].append(error_msg)
        except Exception as e:
            error_msg = f"Error deleting Usage Plan: {e}"
            print(f"   ✗ {error_msg}")
            results["errors"].append(error_msg)

    # API Key 삭제
    if api_key_id:
        try:
            print(f"\n3. Deleting API Key: {api_key_id}...")  # codeql[py/clear-text-logging-sensitive-data]
            client.delete_api_key(apiKey=api_key_id)
            print("   ✓ API Key deleted")
            results["api_key_deleted"] = True
        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                print("   ⚠ API Key not found (may already be deleted)")
                results["api_key_deleted"] = True
            else:
                error_msg = f"Failed to delete API Key: {e}"
                print(f"   ✗ {error_msg}")
                results["errors"].append(error_msg)
        except Exception as e:
            error_msg = f"Error deleting API Key: {e}"
            print(f"   ✗ {error_msg}")
            results["errors"].append(error_msg)

    # REST API 삭제
    try:
        print(f"\n4. Deleting REST API: {api_id}...")
        client.delete_rest_api(restApiId=api_id)
        print("   ✓ REST API deleted")
        results["api_deleted"] = True
    except ClientError as e:
        if e.response["Error"]["Code"] == "NotFoundException":
            print("   ⚠ REST API not found (may already be deleted)")
            results["api_deleted"] = True
        else:
            error_msg = f"Failed to delete REST API: {e}"
            print(f"   ✗ {error_msg}")
            results["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Error deleting REST API: {e}"
        print(f"   ✗ {error_msg}")
        results["errors"].append(error_msg)

    print(f"\n{'=' * 70}")
    print("Cleanup Summary")
    print(f"{'=' * 70}")
    print(f"REST API Deleted: {'✓' if results['api_deleted'] else '✗'}")
    if api_key_id:
        print(f"API Key Deleted: {'✓' if results['api_key_deleted'] else '✗'}")
    if usage_plan_id:
        print(f"Usage Plan Deleted: {'✓' if results['usage_plan_deleted'] else '✗'}")

    if results["errors"]:
        print(f"\nErrors encountered: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"  - {error}")
    else:
        print("\n✓ All resources deleted successfully")

    print(f"{'=' * 70}\n")

    return results


def delete_agentcore_gateway_and_targets(gateway_id, region="us-west-2"):
    """
    AgentCore Gateway와 모든 대상을 삭제합니다.

    :param gateway_id: AgentCore Gateway ID
    :param region: AWS 리전(기본값: 'us-west-2')
    :return: 삭제 결과가 포함된 딕셔너리
    """
    import boto3

    gateway_client = boto3.client("bedrock-agentcore-control", region_name=region)

    results = {"targets_deleted": [], "gateway_deleted": False, "errors": []}

    print(f"\n{'=' * 70}")
    print("Deleting AgentCore Gateway and Targets")
    print(f"{'=' * 70}\n")

    # 모든 대상을 먼저 나열하고 삭제
    try:
        print(f"1. Listing all targets for gateway: {gateway_id}...")
        list_response = gateway_client.list_gateway_targets(gatewayIdentifier=gateway_id, maxResults=100)

        targets = list_response.get("items", [])

        if targets:
            print(f"   Found {len(targets)} target(s)")

            for item in targets:
                target_id = item["targetId"]
                target_name = item.get("name", "Unknown")

                try:
                    print(f"\n   Deleting target: {target_name} ({target_id})...")
                    gateway_client.delete_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
                    print(f"   ✓ Target deletion initiated: {target_id}")
                    results["targets_deleted"].append(target_id)

                    # 대상이 완전히 삭제될 때까지 대기
                    print("   Waiting for target to be fully deleted...")
                    max_wait = 30  # 최대 대기 시간(초)
                    wait_interval = 2
                    elapsed = 0

                    while elapsed < max_wait:
                        try:
                            # 대상을 가져오되 존재하지 않으면 삭제 완료로 판단
                            gateway_client.get_gateway_target(gatewayIdentifier=gateway_id, targetId=target_id)
                            time.sleep(wait_interval)
                            elapsed += wait_interval
                        except ClientError as e:
                            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                                print(f"   ✓ Target fully deleted: {target_id}")
                                break
                            else:
                                raise

                    if elapsed >= max_wait:
                        print("   ⚠ Target deletion timeout, continuing anyway...")

                except ClientError as e:
                    if e.response["Error"]["Code"] == "ResourceNotFoundException":
                        print("   ⚠ Target not found (may already be deleted)")
                        results["targets_deleted"].append(target_id)
                    else:
                        error_msg = f"Failed to delete target {target_id}: {e}"
                        print(f"   ✗ {error_msg}")
                        results["errors"].append(error_msg)
                except Exception as e:
                    error_msg = f"Error deleting target {target_id}: {e}"
                    print(f"   ✗ {error_msg}")
                    results["errors"].append(error_msg)
        else:
            print("   No targets found")

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print("   ⚠ Gateway not found (may already be deleted)")
            results["gateway_deleted"] = True
            return results
        else:
            error_msg = f"Failed to list targets: {e}"
            print(f"   ✗ {error_msg}")
            results["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Error listing targets: {e}"
        print(f"   ✗ {error_msg}")
        results["errors"].append(error_msg)

    # Gateway 삭제
    try:
        print(f"\n2. Deleting gateway: {gateway_id}...")
        gateway_client.delete_gateway(gatewayIdentifier=gateway_id)
        print("   ✓ Gateway deleted")
        results["gateway_deleted"] = True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print("   ⚠ Gateway not found (may already be deleted)")
            results["gateway_deleted"] = True
        else:
            error_msg = f"Failed to delete gateway: {e}"
            print(f"   ✗ {error_msg}")
            results["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Error deleting gateway: {e}"
        print(f"   ✗ {error_msg}")
        results["errors"].append(error_msg)

    print(f"\n{'=' * 70}")
    print("AgentCore Gateway Cleanup Summary")
    print(f"{'=' * 70}")
    print(f"Targets Deleted: {len(results['targets_deleted'])}")
    print(f"Gateway Deleted: {'✓' if results['gateway_deleted'] else '✗'}")

    if results["errors"]:
        print(f"\nErrors encountered: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"  - {error}")
    else:
        print("\n✓ All AgentCore resources deleted successfully")

    print(f"{'=' * 70}\n")

    return results


def delete_agentcore_credential_provider(credential_provider_arn, region="us-west-2"):
    """
    AgentCore Identity API Key Credential Provider를 삭제합니다.
    AWS Secrets Manager의 연결된 secret도 함께 삭제됩니다.

    :param credential_provider_arn: Credential Provider ARN
    :param region: AWS 리전(기본값: 'us-west-2')
    :return: 삭제 결과가 포함된 딕셔너리
    """
    import boto3

    bedrock_agent_client = boto3.client("bedrock-agentcore-control", region_name=region)

    results = {"credential_provider_deleted": False, "errors": []}

    print(f"\n{'=' * 70}")
    print("Deleting AgentCore Identity Credential Provider")
    print(f"{'=' * 70}\n")

    # ARN에서 Credential Provider 이름 추출
    # ARN 형식: arn:aws:bedrock-agentcore:region:account:token-vault/default/apikeycredentialprovider/name
    try:
        provider_name = credential_provider_arn.split("/")[-1]
        print(f"Credential Provider Name: {provider_name}")
        print(f"Credential Provider ARN: {credential_provider_arn}\n")
    except Exception as e:
        error_msg = f"Failed to parse credential provider ARN: {e}"
        print(f"✗ {error_msg}")
        results["errors"].append(error_msg)
        return results

    # Credential Provider 삭제
    try:
        print(f"Deleting API Key Credential Provider: {provider_name}...")
        bedrock_agent_client.delete_api_key_credential_provider(name=provider_name)
        print("✓ Credential Provider deleted")
        print("  Note: Associated secret in Secrets Manager will also be deleted")
        results["credential_provider_deleted"] = True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print("⚠ Credential Provider not found (may already be deleted)")
            results["credential_provider_deleted"] = True
        else:
            error_msg = f"Failed to delete credential provider: {e}"
            print(f"✗ {error_msg}")
            results["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Error deleting credential provider: {e}"
        print(f"✗ {error_msg}")
        results["errors"].append(error_msg)

    print(f"\n{'=' * 70}")
    print("Credential Provider Cleanup Summary")
    print(f"{'=' * 70}")
    print(f"Credential Provider Deleted: {'✓' if results['credential_provider_deleted'] else '✗'}")

    if results["errors"]:
        print(f"\nErrors encountered: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"  - {error}")
    else:
        print("\n✓ Credential provider deleted successfully")

    print(f"{'=' * 70}\n")

    return results


def delete_cognito_user_pool(user_pool_name, region="us-west-2"):
    """
    Cognito User Pool과 모든 관련 리소스(도메인, 클라이언트, Resource Server)를 삭제합니다.

    :param user_pool_name: Cognito User Pool 이름
    :param region: AWS 리전(기본값: 'us-west-2')
    :return: 삭제 결과가 포함된 딕셔너리
    """
    import boto3

    cognito = boto3.client("cognito-idp", region_name=region)

    results = {
        "user_pool_deleted": False,
        "domain_deleted": False,
        "clients_deleted": [],
        "errors": [],
    }

    print(f"\n{'=' * 70}")
    print(f"Deleting Cognito User Pool: {user_pool_name}")
    print(f"{'=' * 70}\n")

    # 이름으로 User Pool 찾기
    try:
        print(f"1. Finding User Pool: {user_pool_name}...")
        response = cognito.list_user_pools(MaxResults=60)
        user_pool_id = None

        for pool in response.get("UserPools", []):
            if pool["Name"] == user_pool_name:
                user_pool_id = pool["Id"]
                print(f"   ✓ Found User Pool ID: {user_pool_id}")
                break

        if not user_pool_id:
            print(f"   ⚠ User Pool '{user_pool_name}' not found (may already be deleted)")
            results["user_pool_deleted"] = True
            return results

    except Exception as e:
        error_msg = f"Error finding user pool: {e}"
        print(f"   ✗ {error_msg}")
        results["errors"].append(error_msg)
        return results

    # 도메인이 있으면 삭제
    try:
        print("\n2. Checking for User Pool Domain...")
        describe_response = cognito.describe_user_pool(UserPoolId=user_pool_id)
        domain = describe_response.get("UserPool", {}).get("Domain")

        if domain:
            print(f"   Found domain: {domain}")
            print("   Deleting domain...")
            cognito.delete_user_pool_domain(Domain=domain, UserPoolId=user_pool_id)
            print("   ✓ Domain deleted")
            results["domain_deleted"] = True
        else:
            print("   No domain found")

    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            error_msg = f"Error deleting domain: {e}"
            print(f"   ✗ {error_msg}")
            results["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Error checking/deleting domain: {e}"
        print(f"   ✗ {error_msg}")
        results["errors"].append(error_msg)

    # 모든 클라이언트 삭제
    try:
        print("\n3. Deleting User Pool Clients...")
        clients_response = cognito.list_user_pool_clients(UserPoolId=user_pool_id, MaxResults=60)

        clients = clients_response.get("UserPoolClients", [])
        if clients:
            for client in clients:
                client_id = client["ClientId"]
                client_name = client["ClientName"]
                try:
                    print(f"   Deleting client: {client_name} ({client_id})...")
                    cognito.delete_user_pool_client(UserPoolId=user_pool_id, ClientId=client_id)
                    print("   ✓ Client deleted")
                    results["clients_deleted"].append(client_id)
                except Exception as e:
                    error_msg = f"Error deleting client {client_id}: {e}"
                    print(f"   ✗ {error_msg}")
                    results["errors"].append(error_msg)
        else:
            print("   No clients found")

    except Exception as e:
        error_msg = f"Error listing/deleting clients: {e}"
        print(f"   ✗ {error_msg}")
        results["errors"].append(error_msg)

    # User Pool 삭제
    try:
        print(f"\n4. Deleting User Pool: {user_pool_id}...")
        cognito.delete_user_pool(UserPoolId=user_pool_id)
        print("   ✓ User Pool deleted")
        results["user_pool_deleted"] = True

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print("   ⚠ User Pool not found (may already be deleted)")
            results["user_pool_deleted"] = True
        else:
            error_msg = f"Failed to delete user pool: {e}"
            print(f"   ✗ {error_msg}")
            results["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Error deleting user pool: {e}"
        print(f"   ✗ {error_msg}")
        results["errors"].append(error_msg)

    print(f"\n{'=' * 70}")
    print("Cognito User Pool Cleanup Summary")
    print(f"{'=' * 70}")
    print(f"User Pool Deleted: {'✓' if results['user_pool_deleted'] else '✗'}")
    print(f"Domain Deleted: {'✓' if results['domain_deleted'] else 'N/A'}")
    print(f"Clients Deleted: {len(results['clients_deleted'])}")

    if results["errors"]:
        print(f"\nErrors encountered: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"  - {error}")
    else:
        print("\n✓ Cognito resources deleted successfully")

    print(f"{'=' * 70}\n")

    return results


def delete_iam_role(role_name):
    """
    IAM 역할과 연결된 모든 인라인 policy를 삭제합니다.

    :param role_name: IAM 역할 이름
    :return: 삭제 결과가 포함된 딕셔너리
    """
    import boto3

    iam_client = boto3.client("iam")

    results = {"role_deleted": False, "policies_deleted": [], "errors": []}

    print(f"\n{'=' * 70}")
    print(f"Deleting IAM Role: {role_name}")
    print(f"{'=' * 70}\n")

    # 인라인 policy부터 삭제
    try:
        print(f"1. Listing inline policies for role: {role_name}...")
        policies_response = iam_client.list_role_policies(RoleName=role_name, MaxItems=100)

        policy_names = policies_response.get("PolicyNames", [])

        if policy_names:
            print(f"   Found {len(policy_names)} inline policy(ies)")
            for policy_name in policy_names:
                try:
                    print(f"   Deleting policy: {policy_name}...")
                    iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
                    print("   ✓ Policy deleted")
                    results["policies_deleted"].append(policy_name)
                except Exception as e:
                    error_msg = f"Error deleting policy {policy_name}: {e}"
                    print(f"   ✗ {error_msg}")
                    results["errors"].append(error_msg)
        else:
            print("   No inline policies found")

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print("   ⚠ Role not found (may already be deleted)")
            results["role_deleted"] = True
            return results
        else:
            error_msg = f"Error listing policies: {e}"
            print(f"   ✗ {error_msg}")
            results["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Error listing policies: {e}"
        print(f"   ✗ {error_msg}")
        results["errors"].append(error_msg)

    # 역할 삭제
    try:
        print(f"\n2. Deleting IAM Role: {role_name}...")
        iam_client.delete_role(RoleName=role_name)
        print("   ✓ IAM Role deleted")
        results["role_deleted"] = True

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchEntity":
            print("   ⚠ Role not found (may already be deleted)")
            results["role_deleted"] = True
        else:
            error_msg = f"Failed to delete role: {e}"
            print(f"   ✗ {error_msg}")
            results["errors"].append(error_msg)
    except Exception as e:
        error_msg = f"Error deleting role: {e}"
        print(f"   ✗ {error_msg}")
        results["errors"].append(error_msg)

    print(f"\n{'=' * 70}")
    print("IAM Role Cleanup Summary")
    print(f"{'=' * 70}")
    print(f"IAM Role Deleted: {'✓' if results['role_deleted'] else '✗'}")
    print(f"Inline Policies Deleted: {len(results['policies_deleted'])}")

    if results["errors"]:
        print(f"\nErrors encountered: {len(results['errors'])}")
        for error in results["errors"]:
            print(f"  - {error}")
    else:
        print("\n✓ IAM role deleted successfully")

    print(f"{'=' * 70}\n")

    return results
