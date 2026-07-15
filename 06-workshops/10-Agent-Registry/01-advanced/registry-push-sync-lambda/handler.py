"""
EventBridge UpdateAgentRuntime CloudTrail 이벤트로 트리거되는 Lambda입니다.

흐름:
  1. EventBridge를 통해 CloudTrail 이벤트 수신(동일 계정 또는 교차 계정)
  2. Runtime ARN 추출 → MCP URL 생성 → 소스 계정 식별
  3. AgentCore Identity 자격 증명 공급자를 통해 OAuth 토큰 가져오기
  4. MCP 서버 호출: initialize → tools/list
  5. 서버 스키마의 Runtime ARN으로 일치하는 AWS Agent Registry 레코드 찾기
  6. MCP 도구와 레지스트리 도구 비교 - 변경된 경우에만 업데이트

다중 계정을 지원하며, 계정 ID로 자격 증명 공급자를 조회합니다.

계정별 환경 변수({ACCT}를 12자리 계정 ID로 대체):
  CREDENTIAL_PROVIDER_{ACCT} - AgentCore Identity OAuth2 자격 증명 공급자 이름
  CREDENTIAL_SCOPE_{ACCT}    - MCP 서버의 OAuth 범위(선택 사항)

전역 환경 변수:
  REGISTRY_ID             - 레코드를 검색하고 업데이트할 Registry ID
  WORKLOAD_IDENTITY_NAME  - 이 Lambda의 AgentCore 워크로드 자격 증명 이름
"""

import json
import os
import urllib.parse
import requests
import boto3


def get_bearer_token(account_id=None):
    """AgentCore Identity 자격 증명 공급자를 통해 OAuth Bearer 토큰을 가져옵니다.

    2단계 프로세스:
      1. AgentCore Identity에서 워크로드 액세스 토큰 가져오기(이 Lambda 식별)
      2. 이 토큰을 사용하여 자격 증명 공급자에서 OAuth 토큰 가져오기(M2M 흐름)

    자격 증명 공급자는 Cognito/OAuth 설정을 AgentCore Identity에 안전하게
    저장하므로 Lambda 환경 변수에 클라이언트 보안 암호가 필요하지 않습니다.
    """
    acct = account_id or ""
    provider_name = os.environ.get(f"CREDENTIAL_PROVIDER_{acct}") or os.environ.get("CREDENTIAL_PROVIDER", "")
    scope_str = os.environ.get(f"CREDENTIAL_SCOPE_{acct}") or os.environ.get("CREDENTIAL_SCOPE", "")
    scopes = [s.strip() for s in scope_str.split(",") if s.strip()] if scope_str else []
    workload_name = os.environ.get("WORKLOAD_IDENTITY_NAME", "")

    if not provider_name:
        raise ValueError(f"No CREDENTIAL_PROVIDER configured for account {acct}")
    if not workload_name:
        raise ValueError("WORKLOAD_IDENTITY_NAME env var not set")

    region = os.environ.get("AWS_REGION", "us-west-2")
    client = boto3.client("bedrock-agentcore", region_name=region)

    # 1단계: 워크로드 액세스 토큰 가져오기(이 Lambda를 신뢰할 수 있는 워크로드로 식별)
    wat_response = client.get_workload_access_token(
        workloadName=workload_name,
    )
    print(f"Workload access token response keys: {list(wat_response.keys())}")
    workload_token = wat_response.get("workloadAccessToken") or wat_response.get("accessToken", "")
    if not workload_token:
        raise ValueError(f"No access token in workload response: {list(wat_response.keys())}")

    # 2단계: 워크로드 토큰을 사용하여 자격 증명 공급자에서 OAuth 토큰 가져오기
    response = client.get_resource_oauth2_token(
        workloadIdentityToken=workload_token,
        resourceCredentialProviderName=provider_name,
        oauth2Flow="M2M",
        scopes=scopes,
    )
    return response["accessToken"]


def _parse_sse_json(body):
    """SSE 또는 일반 JSON 응답 본문에서 JSON을 추출합니다."""
    text = body if isinstance(body, str) else body.decode("utf-8")
    text = text.strip()
    # 일반 JSON이면 직접 파싱
    if text.startswith("{") or text.startswith("["):
        return json.loads(text)
    # SSE 형식: "event: message\ndata: {...}\n\n" 형태의 줄
    for line in text.splitlines():
        if line.startswith("data:"):
            return json.loads(line[len("data:") :].strip())
    raise ValueError(f"Could not parse response: {text[:200]}")


def _mcp_headers(token, session_id=None):
    """MCP JSON-RPC 요청용 HTTP 헤더를 생성합니다(streamable-http 전송)."""
    h = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}",
    }
    if session_id:
        h["Mcp-Session-Id"] = session_id
    return h


def call_tools_list(mcp_url, token):
    """MCP 서버의 initialize 및 tools/list 메서드를 호출하고 결과를 반환합니다.

    MCP streamable-http에서는 tools/list보다 먼저 initialize를 호출해야 합니다.
    서버에서 세션을 사용하는 경우 initialize의 session_id를 tools/list에 전달합니다.
    """
    # file:// 또는 사용자 지정 스킴 접근을 방지하도록 URL 스킴 검증
    if not mcp_url.startswith("https://"):
        raise ValueError(f"Only HTTPS URLs are allowed, got: {mcp_url[:50]}")

    # 1단계: MCP 세션 초기화
    init_payload = {
        "jsonrpc": "2.0",
        "id": "init-1",
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "tool-sync-lambda", "version": "1.0.0"},
        },
    }

    init_resp = requests.post(
        mcp_url,
        json=init_payload,
        headers=_mcp_headers(token),
        timeout=30,
    )
    init_resp.raise_for_status()
    session_id = init_resp.headers.get("Mcp-Session-Id")
    init_result = _parse_sse_json(init_resp.text)  # noqa: F841 - 응답 검증을 위해 파싱
    print(f"MCP session initialized, session_id={session_id}")

    # 2단계: tools/list 호출
    list_payload = {
        "jsonrpc": "2.0",
        "id": "list-1",
        "method": "tools/list",
        "params": {},
    }

    list_resp = requests.post(
        mcp_url,
        json=list_payload,
        headers=_mcp_headers(token, session_id),
        timeout=30,
    )
    list_resp.raise_for_status()
    return _parse_sse_json(list_resp.text)


def _extract_mcp_url(event):
    """CloudTrail UpdateAgentRuntime 이벤트에서 MCP URL과 계정 ID를 추출합니다.

    반환값:
        (mcp_url, account_id) 튜플. 추출에 실패하면 둘 다 None입니다.
    """
    detail = event.get("detail", {})
    runtime_arn = detail.get("responseElements", {}).get("agentRuntimeArn", "")
    if not runtime_arn:
        return None, None

    # ARN에서 계정 ID 추출: arn:aws:bedrock-agentcore:region:ACCOUNT:runtime/id
    arn_parts = runtime_arn.split(":")
    account_id = arn_parts[4] if len(arn_parts) > 4 else None

    region = detail.get("awsRegion", "us-west-2")
    encoded_arn = runtime_arn.replace(":", "%3A").replace("/", "%2F")
    mcp_url = f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    return mcp_url, account_id


def _find_record_by_mcp_url(client, registry_id, mcp_url):
    """서버 스키마에 Runtime ARN이 포함된 레지스트리 레코드를 검색합니다.

    다음 세 가지 일치 전략을 시도합니다.
      1. 디코딩된 ARN(예: arn:aws:bedrock-agentcore:...:runtime/TrimMCP-xxx)
      2. URL 인코딩된 ARN(예: arn%3Aaws%3Abedrock-agentcore%3A...%2FTrimMCP-xxx)
      3. 전체 MCP URL 일치

    반환값:
        (record_id, full_record) 튜플. 일치 항목이 없으면 둘 다 None입니다.
    """
    # 일치 여부를 확인할 수 있도록 MCP URL에서 Runtime ARN 추출
    # URL 형식: .../runtimes/arn%3A...%2Fruntime%2F<id>/invocations...
    # 디코딩 결과: arn:aws:bedrock-agentcore:region:account:runtime/id
    try:
        decoded_url = urllib.parse.unquote(mcp_url)
        # Runtime 경로만 추출: arn:aws:bedrock-agentcore:...:runtime/xxx
        runtime_marker = "/runtimes/"
        idx = decoded_url.find(runtime_marker)
        if idx >= 0:
            runtime_arn = decoded_url[idx + len(runtime_marker) :].split("/invocations")[0]
        else:
            runtime_arn = None
    except Exception:
        runtime_arn = None

    records = client.list_registry_records(registryId=registry_id)
    record_list = records.get("registryRecords", [])
    print(f"Found {len(record_list)} registry records")
    for rec in record_list:
        record_id = rec.get("registryRecordId") or rec.get("recordId") or rec.get("id", "")
        record_name = rec.get("name", "?")
        record_status = rec.get("status", "?")
        print(f"  Record: {record_id} | {record_name} | status={record_status} | keys={list(rec.keys())}")
        if not record_id:
            print(f"  Warning: could not get record ID from: {list(rec.keys())}")
            continue
        if record_status == "DRAFT":
            print(f"  Skipping DRAFT record {record_id} ({record_name}) — must be APPROVED first")
            continue
        try:
            full = client.get_registry_record(
                registryId=registry_id,
                recordId=record_id,
            )
            descriptors = full.get("descriptors", {})
            mcp_desc = descriptors.get("mcp", {})
            server_schema = mcp_desc.get("server", {})
            inline = server_schema.get("inlineContent", "")

            # 서버 스키마에서 Runtime ARN(디코딩 또는 인코딩) 일치 여부 확인
            if runtime_arn and runtime_arn in inline:
                print(f"Found matching record (by ARN): {record_id} ({rec.get('name', '?')})")
                return record_id, full
            # URL 인코딩된 ARN도 확인
            encoded_arn = runtime_arn.replace(":", "%3A").replace("/", "%2F") if runtime_arn else None
            if encoded_arn and encoded_arn in inline:
                print(f"Found matching record (by encoded ARN): {record_id} ({rec.get('name', '?')})")
                return record_id, full
            if mcp_url in inline or urllib.parse.unquote(mcp_url).rstrip("?qualifier=DEFAULT") in inline:
                print(f"Found matching record (by URL): {record_id} ({rec.get('name', '?')})")
                return record_id, full
        except Exception as e:
            print(f"Error checking record {record_id}: {e}")
            continue

    print(f"No matching record found among {len(record_list)} records.")
    print(f"  Looking for runtime ARN: {runtime_arn}")
    print(f"  Looking for MCP URL: {mcp_url}")
    return None, None


def _get_registry_client():
    """AWS Agent Registry 컨트롤 플레인용 boto3 클라이언트를 생성합니다.

    boto3 >= 1.42.87에 포함된 bedrock-agentcore-control 서비스 모델을 사용합니다.
    """
    region = os.environ.get("AWS_REGION", "us-west-2")
    return boto3.client("bedrock-agentcore-control", region_name=region)


def _normalize_tools(tools):
    """비교할 도구 목록을 정규화하여 name, description, inputSchema를 추출합니다."""
    normalized = []
    for t in sorted(tools, key=lambda x: x.get("name", "")):
        normalized.append(
            {
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "inputSchema": t.get("inputSchema", {}),
            }
        )
    return normalized


def _get_registry_tools_from_record(full_record):
    """AWS Agent Registry 레코드의 도구 정의에서 현재 도구를 가져옵니다."""
    descriptors = full_record.get("descriptors", {})
    mcp_desc = descriptors.get("mcp", {})
    tools_def = mcp_desc.get("tools", {})
    inline = tools_def.get("inlineContent", "")
    if not inline:
        return []
    try:
        return json.loads(inline).get("tools", [])
    except (json.JSONDecodeError, TypeError):
        return []


def sync_registry_if_changed(mcp_tools, mcp_url):
    """MCP 서버 도구와 AWS Agent Registry 레코드 도구를 비교하고 다를 때만 업데이트합니다.

    단계:
      1. 이 MCP 서버의 URL과 일치하는 AWS Agent Registry 레코드 찾기
      2. 레코드의 tools.inlineContent에서 기존 도구 추출
      3. 두 도구 목록 정규화(이름순 정렬 후 name/description/inputSchema 비교)
      4. 동일하면 업데이트 건너뛰기
      5. 다르면 차이를 기록하고 레지스트리 레코드 업데이트

    반환값:
        'action' 키가 포함된 딕셔너리: 'no_change', 'updated' 또는 'skipped'
    """
    registry_id = os.environ["REGISTRY_ID"]
    client = _get_registry_client()

    # 일치하는 레코드 찾기
    record_id, full_record = _find_record_by_mcp_url(client, registry_id, mcp_url)
    if not record_id:
        print(f"No matching registry record found for {mcp_url}")
        return {"action": "skipped", "reason": "no matching record"}

    # 레지스트리에서 현재 도구 가져오기
    registry_tools = _get_registry_tools_from_record(full_record)

    # 정규화된 도구 목록 비교
    mcp_normalized = _normalize_tools(mcp_tools)
    registry_normalized = _normalize_tools(registry_tools)

    if mcp_normalized == registry_normalized:
        print(f"No change detected. Registry record {record_id} is up to date ({len(registry_tools)} tools).")
        return {
            "action": "no_change",
            "record_id": record_id,
            "tool_count": len(registry_tools),
        }

    # 도구가 다르면 레지스트리 업데이트
    print(f"Change detected! Registry has {len(registry_tools)} tools, MCP server has {len(mcp_tools)} tools.")

    # 차이 기록
    mcp_names = {t["name"] for t in mcp_normalized}
    reg_names = {t["name"] for t in registry_normalized}
    added = mcp_names - reg_names
    removed = reg_names - mcp_names
    if added:
        print(f"  Added: {added}")
    if removed:
        print(f"  Removed: {removed}")
    if not added and not removed:
        print("  Tool definitions changed (same names, different schemas/descriptions)")

    tool_schema_content = json.dumps({"tools": mcp_tools})
    client.update_registry_record(
        registryId=registry_id,
        recordId=record_id,
        descriptors={
            "optionalValue": {
                "mcp": {
                    "optionalValue": {
                        "tools": {
                            "optionalValue": {
                                "protocolVersion": "2025-06-18",
                                "inlineContent": tool_schema_content,
                            }
                        }
                    }
                }
            }
        },
    )
    print(f"Updated registry record {record_id} in registry {registry_id}")
    return {
        "action": "updated",
        "record_id": record_id,
        "old_count": len(registry_tools),
        "new_count": len(mcp_tools),
    }


def handler(event, context):
    """Lambda 진입점입니다. EventBridge의 UpdateAgentRuntime 이벤트로 트리거됩니다."""
    mcp_url, account_id = _extract_mcp_url(event)
    if not mcp_url:
        print(f"Could not extract mcp_url from event: {json.dumps(event, default=str)[:500]}")
        return {"statusCode": 400, "body": "Could not extract mcp_url"}

    print(f"Received event for MCP server: {mcp_url} (account: {account_id})")
    token = get_bearer_token(account_id)
    result = call_tools_list(mcp_url, token)

    tools = result.get("result", {}).get("tools", [])
    print(f"Found {len(tools)} tools from MCP server:")
    for t in tools:
        print(f"  - {t['name']}: {t.get('description', '')}")

    # 레지스트리와 비교하여 변경된 경우에만 업데이트
    sync_result = sync_registry_if_changed(tools, mcp_url)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "mcp_url": mcp_url,
                "tool_count": len(tools),
                "tools": [t["name"] for t in tools],
                "sync": sync_result,
            },
            default=str,
        ),
    }
