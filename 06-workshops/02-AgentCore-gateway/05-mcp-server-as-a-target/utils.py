import boto3
import json
import subprocess
import time
import requests


def get_agent_status(agent_name: str, cwd: str = "mcpservers") -> dict:
    """`agentcore status --json`을 실행하고 지정한 agent의 리소스 항목을 반환합니다.

    --json 모드에서도 Ink가 stdout에 남기는 후행 ANSI cursor-show escape를
    무시하기 위해 `JSONDecoder.raw_decode`를 사용합니다.
    """
    result = subprocess.run(
        ["agentcore", "status", "--json"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    status, _ = json.JSONDecoder().raw_decode(result.stdout.lstrip())
    return next(
        r
        for r in status["resources"]
        if r["resourceType"] == "agent" and r["name"] == agent_name
    )


def deploy_cognito_stack(cfn, stack_name: str, template_path: str) -> dict:
    """Cognito CloudFormation 스택을 멱등하게 배포하고 출력을 반환합니다.

    스택이 없으면 생성하고, 이미 `*_COMPLETE` 상태이면 업데이트를 시도하며
    "no updates" 오류는 무시합니다. 스택이 종료 상태가 아니면 오류를 발생시킵니다.
    """
    with open(template_path) as f:
        template_body = f.read()

    def _stack_status(name):
        try:
            return cfn.describe_stacks(StackName=name)["Stacks"][0]["StackStatus"]
        except cfn.exceptions.ClientError as e:
            if "does not exist" in str(e):
                return None
            raise

    status = _stack_status(stack_name)

    if status is None:
        print(f"Creating stack {stack_name}...")
        cfn.create_stack(
            StackName=stack_name,
            TemplateBody=template_body,
            Capabilities=[],  # 스택에 IAM 리소스가 없음
            OnFailure="DELETE",
        )
        cfn.get_waiter("stack_create_complete").wait(StackName=stack_name)
    elif status.endswith("_COMPLETE"):
        try:
            print(f"Stack {stack_name} exists ({status}); attempting update...")
            cfn.update_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Capabilities=[],
            )
            cfn.get_waiter("stack_update_complete").wait(StackName=stack_name)
        except cfn.exceptions.ClientError as e:
            if "No updates are to be performed" not in str(e):
                raise
            print("No stack updates needed.")
    else:
        raise RuntimeError(
            f"Stack {stack_name} is in non-terminal state {status}; resolve before continuing."
        )

    return {
        o["OutputKey"]: o["OutputValue"]
        for o in cfn.describe_stacks(StackName=stack_name)["Stacks"][0]["Outputs"]
    }


def delete_iam_role(role_name: str) -> None:
    """IAM role과 연결된 관리형·인라인 정책을 삭제합니다. 멱등성을 보장합니다."""
    iam = boto3.client("iam")
    try:
        for p in iam.list_attached_role_policies(RoleName=role_name)[
            "AttachedPolicies"
        ]:
            iam.detach_role_policy(RoleName=role_name, PolicyArn=p["PolicyArn"])
        for name in iam.list_role_policies(RoleName=role_name)["PolicyNames"]:
            iam.delete_role_policy(RoleName=role_name, PolicyName=name)
        iam.delete_role(RoleName=role_name)
        print(f"✓ Deleted IAM role: {role_name}")
    except iam.exceptions.NoSuchEntityException:
        print(f"ℹ️  IAM role not found: {role_name}")


def get_token(
    token_endpoint: str,
    client_id: str,
    client_secret: str,
    scope_string: str,
) -> dict:
    """`token_endpoint`에서 client_credentials access token을 발급합니다.
    `token_endpoint`는 Cognito hosted UI의 `/oauth2/token` URL이며 스택의
    `TokenEndpoint` 출력에서 읽습니다."""
    try:
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": scope_string,
        }
        response = requests.post(
            token_endpoint, headers=headers, data=data, timeout=3600
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as err:
        return {"error": str(err)}


def create_agentcore_gateway_role_with_region(gateway_name, region):
    """
    리전을 명시하여 AgentCore Gateway용 IAM role을 생성합니다.

    인자:
        gateway_name: gateway 이름
        region: gateway를 배포할 AWS 리전

    반환:
        IAM role 응답
    """
    iam_client = boto3.client("iam")
    agentcore_gateway_role_name = f"agentcore-{gateway_name}-role"
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
                    "ArnLike": {
                        "aws:SourceArn": f"arn:aws:bedrock-agentcore:{region}:{account_id}:*"
                    },
                },
            }
        ],
    }

    assume_role_policy_document_json = json.dumps(assume_role_policy_document)
    role_policy_document = json.dumps(role_policy)

    try:
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_gateway_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json,
        )
        time.sleep(10)
    except iam_client.exceptions.EntityAlreadyExistsException:
        print("Role already exists -- deleting and creating it again")
        policies = iam_client.list_role_policies(
            RoleName=agentcore_gateway_role_name, MaxItems=100
        )
        print("policies:", policies)
        for policy_name in policies["PolicyNames"]:
            iam_client.delete_role_policy(
                RoleName=agentcore_gateway_role_name, PolicyName=policy_name
            )
        print(f"deleting {agentcore_gateway_role_name}")
        iam_client.delete_role(RoleName=agentcore_gateway_role_name)
        print(f"recreating {agentcore_gateway_role_name}")
        agentcore_iam_role = iam_client.create_role(
            RoleName=agentcore_gateway_role_name,
            AssumeRolePolicyDocument=assume_role_policy_document_json,
        )

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


def delete_gateway(gateway_client, gatewayId):
    print("Deleting all targets for gateway", gatewayId)
    list_response = gateway_client.list_gateway_targets(
        gatewayIdentifier=gatewayId, maxResults=100
    )
    for item in list_response["items"]:
        targetId = item["targetId"]
        print("Deleting target ", targetId)
        gateway_client.delete_gateway_target(
            gatewayIdentifier=gatewayId, targetId=targetId
        )
        time.sleep(5)
    print("Deleting gateway ", gatewayId)
    gateway_client.delete_gateway(gatewayIdentifier=gatewayId)


def interactive_input_form(params):
    """스키마 기반 prompt-via-input() callback입니다.
    `requestedSchema.properties`의 각 필드는 스키마에서 파생된 힌트(enum 선택지,
    정수 범위, boolean y/N)가 있는 하나의 `input()` prompt가 됩니다.
    어느 prompt에서든 거절하려면 `d`, 취소하려면 `c`를 입력합니다.
    """
    message = params.get("message") or "Please provide input"
    schema = params.get("requestedSchema") or {}
    props = (schema.get("properties") or {}) if isinstance(schema, dict) else {}
    print(f"\n>>> {message}")
    data = {}
    for name, field in props.items():
        ftype = field.get("type") if isinstance(field, dict) else None
        enum = field.get("enum") if isinstance(field, dict) else None
        if ftype == "boolean":
            prompt = f"  {name} [y/N]: "
        elif enum:
            prompt = f"  {name} [{'/'.join(map(str, enum))}]: "
        elif ftype == "integer":
            mn = field.get("minimum") if isinstance(field, dict) else None
            mx = field.get("maximum") if isinstance(field, dict) else None
            range_str = (
                f"[{mn}-{mx}]" if mn is not None and mx is not None else "(integer)"
            )
            prompt = f"  {name} {range_str}: "
        elif ftype == "number":
            prompt = f"  {name} (number): "
        else:
            prompt = f"  {name}: "

        raw = input(prompt).strip()
        if raw.lower() in ("d", "decline"):
            print("  -> declined")
            return {"action": "decline"}
        if raw.lower() in ("c", "cancel"):
            print("  -> cancelled")
            return {"action": "cancel"}

        if ftype == "string":
            data[name] = raw if raw else (enum[0] if enum else "")
        elif ftype == "integer":
            try:
                data[name] = int(raw) if raw else (field.get("minimum") or 0)
            except ValueError:
                data[name] = field.get("minimum") or 0
        elif ftype == "number":
            try:
                data[name] = float(raw) if raw else 0.0
            except ValueError:
                data[name] = 0.0
        elif ftype == "boolean":
            data[name] = raw.lower() in ("y", "yes", "true", "1")
        else:
            data[name] = raw

    return {"action": "accept", "content": data}


def bedrock_sampling(
    params,
    model_id: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    region: str | None = None,
):
    """Converse API를 통해 Amazon Bedrock에 위임하는 실제 sampling callback입니다.
    `GatewayMCPClient.call_tool_streaming(
    sampling_callback=...)`.

    MCP `sampling/createMessage` params를 Bedrock Converse 입력으로 변환한 다음
    응답을 `CreateMessageResult` 형태의 dict로 다시 변환합니다.

    이 Notebook을 실행하는 IAM principal에는 `model_id`에 대한
    `bedrock:InvokeModel` 권한이 있어야 합니다.
    """
    bedrock = boto3.client("bedrock-runtime", region_name=region)

    # MCP는 `messages`를 문자열(서버가 `ctx.sample`에 `messages="..."`를 전달할 때)
    # 또는 {role, content} dict 목록으로 전송
    raw_messages = params.get("messages")
    if isinstance(raw_messages, str):
        raw_messages = [
            {"role": "user", "content": {"type": "text", "text": raw_messages}}
        ]
    elif raw_messages is None:
        raw_messages = []

    converse_messages = []
    for m in raw_messages:
        role = m.get("role", "user")
        content = m.get("content")
        if isinstance(content, dict):
            text = content.get("text", "")
        else:
            text = str(content)
        converse_messages.append({"role": role, "content": [{"text": text}]})

    inference_cfg: dict = {"maxTokens": int(params.get("maxTokens") or 256)}
    if params.get("temperature") is not None:
        inference_cfg["temperature"] = float(params["temperature"])
    if params.get("stopSequences"):
        inference_cfg["stopSequences"] = list(params["stopSequences"])

    kwargs = {
        "modelId": model_id,
        "messages": converse_messages,
        "inferenceConfig": inference_cfg,
    }
    if params.get("systemPrompt"):
        kwargs["system"] = [{"text": params["systemPrompt"]}]

    response = bedrock.converse(**kwargs)
    text = response["output"]["message"]["content"][0]["text"]

    return {
        "role": "assistant",
        "content": {"type": "text", "text": text},
        "model": model_id,
        "stopReason": response.get("stopReason"),
    }


def show(label, outcome):
    """`call_tool_streaming`이 반환한 값을 보기 좋게 출력합니다."""
    result = outcome.get("result") or {}
    error = outcome.get("error")
    print(f"--- {label} ---")
    print(f"  isError: {result.get('isError') if result else None}")
    if error:
        print(f"  error: {error}")
    for c in result.get("content") or []:
        print(f"  content: {c.get('text', c)}")
