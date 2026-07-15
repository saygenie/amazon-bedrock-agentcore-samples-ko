import boto3
import json
import time
import botocore.exceptions


def assume_role(role_arn, session_name="my-session"):
    """IAM 역할을 수임하고 임시 자격 증명을 반환합니다."""
    sts = boto3.client("sts")
    response = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName=session_name,
    )
    creds = response["Credentials"]
    print(f"Assumed role: {response['AssumedRoleUser']['Arn']}")

    return creds


def assume_role_only(AWS_REGION, role_arn, session_name="test-session"):
    """IAM 역할을 수임합니다."""
    sts_client = boto3.client("sts", region_name=AWS_REGION)
    response = sts_client.assume_role(
        RoleArn=role_arn,
        RoleSessionName=session_name,
    )
    return response


def pp(response):
    """API 응답에서 ResponseMetadata를 제외하고 보기 좋게 출력합니다."""
    data = {k: v for k, v in response.items() if k != "ResponseMetadata"}
    print(json.dumps(data, indent=2, default=str))


def wait_for_record_ready(publisher_cp_client, registry_id, record_id, interval=5, timeout=120):
    """레코드가 CREATING/UPDATING 상태를 벗어날 때까지 GetRegistryRecord를 폴링합니다."""
    deadline = time.time() + timeout
    while True:
        resp = publisher_cp_client.get_registry_record(registryId=registry_id, recordId=record_id)
        status = resp["status"]
        print(f"  Record {record_id} status: {status}")
        if status not in ("CREATING", "UPDATING"):
            return resp
        if time.time() >= deadline:
            raise TimeoutError(f"Record {record_id} still in {status} after {timeout}s.")
        time.sleep(interval)


print("Helper functions defined: pp, wait_for_record_ready")


def filter_pending_records(records):
    """상태가 PENDING_APPROVAL인 레코드만 반환합니다."""
    return [r for r in records if r.get("status") == "PENDING_APPROVAL"]


def list_records_with_ids(client, registry_id, **kwargs):
    """원시 HTTP 응답에서 recordId를 추출하는 list_registry_records 래퍼입니다.

    프리뷰 SDK 모델은 'registryRecordId'를 사용하지만 서비스는 'recordId'를 반환합니다.
    이 함수는 원시 JSON을 파싱하여 실제 레코드 ID를 가져옵니다.
    """
    import json as _json

    original_make_request = client._endpoint.make_request
    raw_body = {}

    def capture_request(operation_model, request_dict):
        result = original_make_request(operation_model, request_dict)
        http_response = result[0]
        raw_body["data"] = _json.loads(http_response.content.decode("utf-8"))
        return result

    client._endpoint.make_request = capture_request
    try:
        client.list_registry_records(registryId=registry_id, **kwargs)
    finally:
        client._endpoint.make_request = original_make_request

    return raw_body.get("data", {}).get("registryRecords", [])


def get_or_select_registry(cp_client, registry_id=None, AWS_REGION="us-west-2"):
    """레지스트리를 나열하고 READY 레지스트리의 (registry_id, registry_arn)을 반환합니다.

    매개변수:
        cp_client: Bedrock AgentCore 컨트롤 플레인 클라이언트.
        registry_id: 사용할 특정 레지스트리 ID. None이면 첫 번째 READY 레지스트리를 선택합니다.
        aws_region: AWS 리전(오류 메시지에 사용).

    반환값:
        (registry_id, registry_arn) 튜플.

    예외:
        ValueError: 지정한 레지스트리를 찾을 수 없거나 READY 상태가 아닌 경우.
        RuntimeError: READY 레지스트리가 없는 경우.
    """
    try:
        resp = cp_client.list_registries()
        all_registries = resp.get("registries", [])
        print(f"Found {len(all_registries)} registries:\n")
        for reg in all_registries:
            print(f"  [{reg['status']}] {reg['name']} ({reg['registryId']})")

        ready = [r for r in all_registries if r["status"] == "READY"]

        if registry_id:
            match = [r for r in all_registries if r["registryId"] == registry_id]
            if not match:
                raise ValueError(f"Registry {registry_id} not found.")
            if match[0]["status"] != "READY":
                raise ValueError(f"Registry {registry_id} is {match[0]['status']}, not READY.")
            rid, rarn = match[0]["registryId"], match[0]["registryArn"]
            print(f"\n✅ Using specified registry: {rid}")
        elif ready:
            rid, rarn = ready[0]["registryId"], ready[0]["registryArn"]
            print(f"\n✅ Using registry: {ready[0]['name']} (ID: {rid})")
        else:
            raise RuntimeError("No READY registry available. Run notebook 02 first.")

        print(f"\nRegistry ID:  {rid}")
        print(f"Registry ARN: {rarn}")
        return rid, rarn

    except botocore.exceptions.EndpointConnectionError as e:
        print(f"❌ Cannot reach bedrock-agentcore-control in {AWS_REGION}. Error: {e}")
        raise
    except botocore.exceptions.ClientError as e:
        code = e.response["Error"]["Code"]
        print(f"❌ Error listing registries: {code} — {e}")
        if code == "AccessDeniedException":
            print("   Verify admin_persona has bedrock-agentcore:ListRegistries permission.")
        raise


def build_trust_policy(sagemaker_role_arn):
    """SageMaker 역할과 AgentCore 서비스를 모두 허용하는 신뢰 정책을 생성합니다."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                "Action": "sts:AssumeRole",
            },
            {
                "Effect": "Allow",
                "Principal": {"AWS": sagemaker_role_arn},
                "Action": "sts:AssumeRole",
            },
        ],
    }


def build_permissions_policy(actions):
    """주어진 작업에 대한 권한 정책을 생성합니다."""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": actions,
                "Resource": "*",
            }
        ],
    }


def create_or_update_persona_role(iam_client, role_name, policy_name, actions, trust_policy, ACCOUNT_ID):
    """IAM 역할을 생성하고, 이미 존재하면 업데이트합니다."""
    try:
        resp = iam_client.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description=f"AgentCore Registry - {role_name}",
        )
        role_arn = resp["Role"]["Arn"]
        print(f"  Created role: {role_arn}")
    except iam_client.exceptions.EntityAlreadyExistsException:
        role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/{role_name}"
        print(f"  Role already exists: {role_arn} — updating...")
        iam_client.update_assume_role_policy(
            RoleName=role_name,
            PolicyDocument=json.dumps(trust_policy),
        )

    # 인라인 권한 정책 연결 또는 업데이트
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName=policy_name,
        PolicyDocument=json.dumps(build_permissions_policy(actions)),
    )
    print(f"  Attached policy: {policy_name}")
    return role_arn


def extract_role_arn(caller_arn):
    """호출자 자격 증명에서 실제 IAM 역할 ARN을 가져옵니다.

    수임한 역할의 ARN 형식에서는 역할 경로(예: /service-role/)가 사라집니다.
    역할 이름을 추출하고 IAM에서 조회하여 전체 ARN을 가져옵니다.
    """
    if ":assumed-role/" in caller_arn:
        role_name = caller_arn.split(":")[-1].split("/")[1]
        # 실제 역할을 조회하여 경로가 포함된 전체 ARN 가져오기
        iam = boto3.client("iam")
        role_info = iam.get_role(RoleName=role_name)
        return role_info["Role"]["Arn"]
    return caller_arn
