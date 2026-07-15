"""
harness-oauth-gateway 노트북에서 사용하는 인프라를 프로비저닝하는
도우미 함수다.

각 함수는 독립적으로 하나의 논리적 리소스 그룹을 생성하고,
진행 상황을 출력한 뒤 노트북에 필요한 값이 담긴 dict를 반환한다.
모든 함수는 멱등성을 보장하므로 리소스가 이미 있어도 안전하게 다시 실행할 수 있다.
"""

import boto3
import io
import json
import time
import uuid
import zipfile


# ─────────────────────────────────────────────────────────────────────
# 내부 도우미
# ─────────────────────────────────────────────────────────────────────


def _find_pool_by_name(cog, pool_name):
    """해당 이름의 Cognito 사용자 풀이 있으면 풀 ID를, 없으면 None을 반환한다."""
    for p in cog.list_user_pools(MaxResults=60).get("UserPools", []):
        if p["Name"] == pool_name:
            return p["Id"]
    return None


def _find_client_by_name(cog, pool_id, client_name):
    """앱 클라이언트가 있으면 (client_id, client_secret|None)을 반환한다."""
    for c in cog.list_user_pool_clients(UserPoolId=pool_id, MaxResults=60)["UserPoolClients"]:
        if c["ClientName"] == client_name:
            full = cog.describe_user_pool_client(
                UserPoolId=pool_id,
                ClientId=c["ClientId"],
            )["UserPoolClient"]
            return full["ClientId"], full.get("ClientSecret")
    return None, None


def _ensure_role(iam_c, role_name, trust_doc):
    """IAM 역할이 없으면 생성하고 역할 ARN을 반환한다."""
    try:
        return iam_c.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=trust_doc,
        )["Role"]["Arn"]
    except iam_c.exceptions.EntityAlreadyExistsException:
        return iam_c.get_role(RoleName=role_name)["Role"]["Arn"]


def _ensure_policy(iam_c, account_id, policy_name, policy_doc):
    """관리형 정책이 없으면 생성하고 ARN을 반환한다."""
    arn = f"arn:aws:iam::{account_id}:policy/{policy_name}"
    try:
        iam_c.create_policy(PolicyName=policy_name, PolicyDocument=policy_doc)
    except iam_c.exceptions.EntityAlreadyExistsException:
        pass
    return arn


# ─────────────────────────────────────────────────────────────────────
# Cognito 풀 #1: 사용자 인증(USER_PASSWORD_AUTH)
# ─────────────────────────────────────────────────────────────────────


def create_user_auth_pool(region: str, prefix: str, username: str, password: str) -> dict:
    """최종 사용자 인증용 Cognito 사용자 풀을 생성하거나 재사용한다.

    생성 항목:
      - USER_PASSWORD_AUTH를 사용하는 사용자 풀
      - 앱 클라이언트(보안 암호 없음)
      - 제공된 자격 증명을 사용하는 테스트 사용자

    반환하는 dict의 키: pool_id, client_id, discovery_url
    """
    cog = boto3.client("cognito-idp", region_name=region)
    pool_name = f"{prefix}-user-pool"
    client_name = f"{prefix}-user-client"

    # ── 풀 ──
    pool_id = _find_pool_by_name(cog, pool_name)
    if pool_id:
        print(f"  Pool #1 already exists: {pool_id}")
    else:
        pool_id = cog.create_user_pool(
            PoolName=pool_name,
            Policies={"PasswordPolicy": {"MinimumLength": 8}},
            AutoVerifiedAttributes=["email"],
        )["UserPool"]["Id"]
        print(f"  Pool #1 created: {pool_id}")

    # ── 앱 클라이언트 ──
    client_id, _ = _find_client_by_name(cog, pool_id, client_name)
    if client_id:
        print(f"  Pool #1 client already exists: {client_id}")
    else:
        client_id = cog.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName=client_name,
            ExplicitAuthFlows=["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"],
            GenerateSecret=False,
        )["UserPoolClient"]["ClientId"]
        print(f"  Pool #1 client created: {client_id}")

    # ── 테스트 사용자(생성 또는 비밀번호 재설정) ──
    try:
        cog.admin_create_user(
            UserPoolId=pool_id,
            Username=username,
            MessageAction="SUPPRESS",
        )
        print(f'  Test user "{username}" created')
    except cog.exceptions.UsernameExistsException:
        print(f'  Test user "{username}" already exists')
    cog.admin_set_user_password(
        UserPoolId=pool_id,
        Username=username,
        Password=password,
        Permanent=True,
    )

    discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
    return dict(pool_id=pool_id, client_id=client_id, discovery_url=discovery_url)


# ─────────────────────────────────────────────────────────────────────
# Cognito 풀 #2: M2M(client_credentials + 리소스 서버)
# ─────────────────────────────────────────────────────────────────────


def create_m2m_pool(region: str, prefix: str) -> dict:
    """M2M 인증용 Cognito 사용자 풀을 생성하거나 재사용한다.

    생성 항목:
      - 사용자 풀
      - 'invoke' 범위가 있는 리소스 서버
      - Cognito 도메인(토큰 엔드포인트용)
      - client_credentials 권한 부여와 보안 암호를 사용하는 앱 클라이언트

    반환하는 dict의 키:
      pool_id, client_id, client_secret, discovery_url,
      scope, domain_prefix, token_endpoint
    """
    cog = boto3.client("cognito-idp", region_name=region)
    pool_name = f"{prefix}-m2m-pool"
    client_name = f"{prefix}-m2m-client"
    rs_id = f"{prefix}-gateway"
    scope = f"{rs_id}/invoke"

    # ── 풀 ──
    pool_id = _find_pool_by_name(cog, pool_name)
    if pool_id:
        print(f"  Pool #2 already exists: {pool_id}")
    else:
        pool_id = cog.create_user_pool(
            PoolName=pool_name,
            Policies={"PasswordPolicy": {"MinimumLength": 8}},
        )["UserPool"]["Id"]
        print(f"  Pool #2 created: {pool_id}")

    # ── 리소스 서버 ──
    try:
        cog.create_resource_server(
            UserPoolId=pool_id,
            Identifier=rs_id,
            Name="Gateway Resource Server",
            Scopes=[{"ScopeName": "invoke", "ScopeDescription": "Invoke gateway tools"}],
        )
        print(f"  Resource server created, scope: {scope}")
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"  Resource server already exists, scope: {scope}")
        else:
            raise

    # ── 도메인 ──
    desc = cog.describe_user_pool(UserPoolId=pool_id)["UserPool"]
    domain_prefix = desc.get("Domain")
    if domain_prefix:
        print(f"  Domain already exists: {domain_prefix}")
    else:
        domain_prefix = f"{prefix}-{uuid.uuid4().hex[:8]}"
        cog.create_user_pool_domain(Domain=domain_prefix, UserPoolId=pool_id)
        print(f"  Domain created: {domain_prefix}")
    token_endpoint = f"https://{domain_prefix}.auth.{region}.amazoncognito.com/oauth2/token"

    # ── 앱 클라이언트 ──
    client_id, client_secret = _find_client_by_name(cog, pool_id, client_name)
    if client_id and client_secret:
        print(f"  Pool #2 client already exists: {client_id}")
    else:
        resp = cog.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName=client_name,
            GenerateSecret=True,
            AllowedOAuthFlows=["client_credentials"],
            AllowedOAuthScopes=[scope],
            AllowedOAuthFlowsUserPoolClient=True,
            SupportedIdentityProviders=["COGNITO"],
        )
        client_id = resp["UserPoolClient"]["ClientId"]
        client_secret = resp["UserPoolClient"]["ClientSecret"]
        print(f"  Pool #2 client created: {client_id}")

    discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}/.well-known/openid-configuration"
    return dict(
        pool_id=pool_id,
        client_id=client_id,
        client_secret=client_secret,
        discovery_url=discovery_url,
        scope=scope,
        domain_prefix=domain_prefix,
        token_endpoint=token_endpoint,
    )


# ─────────────────────────────────────────────────────────────────────
# OAuth2 자격 증명 공급자(AgentCore Identity)
# ─────────────────────────────────────────────────────────────────────


def create_credential_provider(
    region: str,
    prefix: str,
    discovery_url: str,
    client_id: str,
    client_secret: str,
) -> dict:
    """AgentCore Identity에서 OAuth2 자격 증명 공급자를 생성하거나 재사용한다.

    반환하는 dict의 키: name, arn
    """
    ac = boto3.client("bedrock-agentcore-control", region_name=region)
    name = f"{prefix}-m2m-provider"

    # 이미 있는지 확인한다.
    try:
        existing = ac.get_oauth2_credential_provider(name=name)
        arn = existing["credentialProviderArn"]
        print(f"  Credential provider already exists: {arn}")
        return dict(name=name, arn=arn)
    except Exception:
        pass  # 아직 존재하지 않는다.

    resp = ac.create_oauth2_credential_provider(
        name=name,
        credentialProviderVendor="CustomOauth2",
        oauth2ProviderConfigInput={
            "customOauth2ProviderConfig": {
                "oauthDiscovery": {"discoveryUrl": discovery_url},
                "clientId": client_id,
                "clientSecret": client_secret,
            }
        },
    )
    arn = resp["credentialProviderArn"]
    print(f"  Credential provider created: {arn}")
    return dict(name=name, arn=arn)


# ─────────────────────────────────────────────────────────────────────
# Lambda 함수
# ─────────────────────────────────────────────────────────────────────


def deploy_lambda(region: str, prefix: str) -> dict:
    """주문 관리 Lambda 함수를 배포하거나 재사용한다.

    반환하는 dict의 키: function_name, function_arn, role_name
    """
    iam_c = boto3.client("iam")
    lam = boto3.client("lambda", region_name=region)

    role_name = f"{prefix}-lambda-role"
    trust = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    )
    role_arn = _ensure_role(iam_c, role_name, trust)
    try:
        iam_c.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
        )
    except Exception:
        pass
    print(f"  Role: {role_name}")

    fn_name = f"{prefix}-order-mgmt"

    # Lambda가 이미 있는지 확인한다.
    try:
        fn_arn = lam.get_function(FunctionName=fn_name)["Configuration"]["FunctionArn"]
        print(f"  Lambda already exists: {fn_name}")
    except lam.exceptions.ResourceNotFoundException:
        # 새 역할에만 IAM 전파 시간이 필요하다.
        print("  Waiting 10 s for IAM propagation…")
        time.sleep(10)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write("utils/lambda_function_code.py", "lambda_function.py")
        buf.seek(0)

        fn_arn = lam.create_function(
            FunctionName=fn_name,
            Runtime="python3.12",
            Role=role_arn,
            Handler="lambda_function.lambda_handler",
            Code={"ZipFile": buf.read()},
            Description="Order management for AgentCore Gateway",
            Timeout=30,
        )["FunctionArn"]
        print(f"  Lambda created: {fn_name}")

    lam.get_waiter("function_active_v2").wait(FunctionName=fn_name)
    print("  Lambda is Active")
    return dict(function_name=fn_name, function_arn=fn_arn, role_name=role_name)


# ─────────────────────────────────────────────────────────────────────
# Gateway + Lambda 대상
# ─────────────────────────────────────────────────────────────────────


def create_gateway_with_lambda_target(
    region: str,
    prefix: str,
    account_id: str,
    discovery_url: str,
    allowed_client: str,
    allowed_scope: str,
    lambda_arn: str,
    lambda_function_name: str,
) -> dict:
    """CUSTOM_JWT 인바운드 인증을 사용하는 AgentCore Gateway와
    GATEWAY_IAM_ROLE 아웃바운드 인증을 사용하는 Lambda 대상을 생성하거나 재사용한다.

    반환하는 dict의 키:
      gateway_id, gateway_arn, gateway_url, target_id,
      role_name, policy_name
    """
    iam_c = boto3.client("iam")
    ac = boto3.client("bedrock-agentcore-control", region_name=region)

    # ── Gateway 실행 역할 ──
    gw_role_name = f"{prefix}-gateway-role"
    trust = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    )
    gw_role_arn = _ensure_role(iam_c, gw_role_name, trust)
    print(f"  Gateway role: {gw_role_name}")

    gw_policy_name = f"{prefix}-gw-lambda-policy"
    policy_doc = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "lambda:InvokeFunction",
                    "Resource": f"arn:aws:lambda:{region}:{account_id}:function:{lambda_function_name}",
                }
            ],
        }
    )
    gw_policy_arn = _ensure_policy(iam_c, account_id, gw_policy_name, policy_doc)
    iam_c.attach_role_policy(RoleName=gw_role_name, PolicyArn=gw_policy_arn)

    # ── Gateway(생성을 시도하고 이미 있으면 충돌 처리) ──
    gateway_name = f"{prefix}-gateway"
    try:
        print("  Waiting 10 s for IAM propagation…")
        time.sleep(10)
        gw = ac.create_gateway(
            name=gateway_name,
            protocolType="MCP",
            roleArn=gw_role_arn,
            authorizerType="CUSTOM_JWT",
            authorizerConfiguration={
                "customJWTAuthorizer": {
                    "discoveryUrl": discovery_url,
                    "allowedClients": [allowed_client],
                    "allowedScopes": [allowed_scope],
                }
            },
        )
        gw_id = gw["gatewayId"]
        gw_arn = gw["gatewayArn"]
        gw_url = gw.get("gatewayUrl", "")
        print(f"  Gateway created: {gw_id}")
    except ac.exceptions.ConflictException:
        # 이미 존재하므로 목록을 순회하여 찾는다.
        gw_id = None
        for g in ac.list_gateways().get("items", []):
            info = ac.get_gateway(gatewayIdentifier=g["gatewayId"])
            if info.get("name") == gateway_name:
                gw_id = info["gatewayId"]
                gw_arn = info.get("gatewayArn", "")
                gw_url = info.get("gatewayUrl", "")
                break
        if not gw_id:
            raise RuntimeError(f"Gateway {gateway_name} exists but could not be found via list")
        print(f"  Gateway already exists: {gw_id}")

    # READY 상태가 될 때까지 기다린다.
    print("  Waiting for gateway READY…")
    for _ in range(30):
        status = ac.get_gateway(gatewayIdentifier=gw_id)["status"]
        if status == "READY":
            break
        time.sleep(10)
    print(f"  Gateway status: {status}")

    # ── Lambda 대상(생성을 시도하고 충돌 처리) ──
    target_name = f"{prefix}-lambda-target"
    tool_schemas = [
        {
            "name": "get_order",
            "description": "Look up an order by ID. Returns item, status, amount.",
            "inputSchema": {
                "type": "object",
                "properties": {"orderId": {"type": "string", "description": "e.g. ORD-001"}},
                "required": ["orderId"],
            },
        },
        {
            "name": "update_order_status",
            "description": "Update the status of an existing order.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "orderId": {"type": "string", "description": "Order ID to update"},
                    "status": {"type": "string", "description": "New status value"},
                },
                "required": ["orderId", "status"],
            },
        },
    ]
    try:
        tgt = ac.create_gateway_target(
            gatewayIdentifier=gw_id,
            name=target_name,
            targetConfiguration={
                "mcp": {
                    "lambda": {
                        "lambdaArn": lambda_arn,
                        "toolSchema": {"inlinePayload": tool_schemas},
                    }
                }
            },
            credentialProviderConfigurations=[{"credentialProviderType": "GATEWAY_IAM_ROLE"}],
        )
        tgt_id = tgt["targetId"]
        print(f"  Target created: {tgt_id}")
    except ac.exceptions.ConflictException:
        # 이미 존재하므로 찾아서 사용한다.
        tgt_id = None
        for t in ac.list_gateway_targets(gatewayIdentifier=gw_id).get("items", []):
            tgt_id = t["targetId"]
            break
        if not tgt_id:
            raise RuntimeError(f"Target on {gw_id} exists but could not be found via list")
        print(f"  Target already exists: {tgt_id}")

    # 대상이 READY 상태가 될 때까지 기다린다.
    print("  Waiting for target READY…")
    for _ in range(30):
        status = ac.get_gateway_target(gatewayIdentifier=gw_id, targetId=tgt_id)["status"]
        if status == "READY":
            break
        time.sleep(10)
    print(f"  Target status: {status}")

    # 재사용한 경우 전체 ARN/URL을 가져오기 위해 Gateway를 다시 조회한다.
    gw_full = ac.get_gateway(gatewayIdentifier=gw_id)
    return dict(
        gateway_id=gw_id,
        gateway_arn=gw_full.get("gatewayArn", gw_arn),
        gateway_url=gw_full.get("gatewayUrl", gw_url),
        target_id=tgt_id,
        role_name=gw_role_name,
        policy_name=gw_policy_name,
    )


# ─────────────────────────────────────────────────────────────────────
# Harness 실행 역할
# ─────────────────────────────────────────────────────────────────────


def create_harness_execution_role(region: str, prefix: str, account_id: str) -> dict:
    """Harness가 런타임에 수임하는 IAM 실행 역할을 생성하거나 재사용한다.

    반환하는 dict의 키: role_arn, role_name, policy_name
    """
    iam_c = boto3.client("iam")
    role_name = f"{prefix}-harness-role"
    trust = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                }
            ],
        }
    )
    role_arn = _ensure_role(iam_c, role_name, trust)
    print(f"  Role: {role_name} (already exists or created)")

    policy_name = f"{prefix}-harness-policy"
    policy_doc = json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "Bedrock",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock:InvokeModel",
                        "bedrock:InvokeModelWithResponseStream",
                    ],
                    "Resource": [
                        "arn:aws:bedrock:*::foundation-model/*",
                        f"arn:aws:bedrock:{region}:{account_id}:*",
                    ],
                },
                {
                    "Sid": "Gateway",
                    "Effect": "Allow",
                    "Action": "bedrock-agentcore:InvokeGateway",
                    "Resource": f"arn:aws:bedrock-agentcore:{region}:{account_id}:gateway/*",
                },
                {
                    "Sid": "OAuth2TokenVault",
                    "Effect": "Allow",
                    "Action": "bedrock-agentcore:GetResourceOauth2Token",
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{region}:{account_id}:token-vault/default",
                        f"arn:aws:bedrock-agentcore:{region}:{account_id}:token-vault/default/oauth2credentialprovider/*",
                        f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default",
                        f"arn:aws:bedrock-agentcore:{region}:{account_id}:workload-identity-directory/default/workload-identity/*",
                    ],
                },
                {
                    "Sid": "OAuth2Secret",
                    "Effect": "Allow",
                    "Action": "secretsmanager:GetSecretValue",
                    "Resource": f"arn:aws:secretsmanager:{region}:{account_id}:secret:bedrock-agentcore-identity!default/oauth2/*",
                },
                {
                    "Sid": "WorkloadIdentity",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetWorkloadAccessToken",
                        "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    ],
                    "Resource": ["*"],
                },
                {
                    "Sid": "EcrPublic",
                    "Effect": "Allow",
                    "Action": [
                        "ecr-public:GetAuthorizationToken",
                        "sts:GetServiceBearerToken",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "CloudWatch",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                        "logs:DescribeLogGroups",
                        "logs:DescribeLogStreams",
                    ],
                    "Resource": f"arn:aws:logs:{region}:{account_id}:log-group:/aws/bedrock-agentcore/*",
                },
                {
                    "Sid": "XRay",
                    "Effect": "Allow",
                    "Action": [
                        "xray:PutTraceSegments",
                        "xray:PutTelemetryRecords",
                        "xray:GetSamplingRules",
                        "xray:GetSamplingTargets",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "CWMetrics",
                    "Effect": "Allow",
                    "Action": "cloudwatch:PutMetricData",
                    "Resource": "*",
                    "Condition": {"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}},
                },
            ],
        }
    )
    policy_arn = _ensure_policy(iam_c, account_id, policy_name, policy_doc)
    iam_c.attach_role_policy(RoleName=role_name, PolicyArn=policy_arn)
    print(f"  Policy: {policy_name}")
    print("  Waiting 15 s for IAM propagation…")
    time.sleep(15)
    return dict(role_arn=role_arn, role_name=role_name, policy_name=policy_name)


# ─────────────────────────────────────────────────────────────────────
# 정리: 이름으로 모든 리소스를 찾아 삭제
# ─────────────────────────────────────────────────────────────────────


def cleanup_all(region: str, prefix: str):
    """이 노트북에서 생성한 모든 리소스를 역순으로 삭제한다.

    이름으로 리소스를 찾으므로 커널을 다시 시작한 뒤에도 동작한다.
    생성된 적 없는 리소스는 문제없이 건너뛴다.
    """
    account_id = boto3.client("sts", region_name=region).get_caller_identity()["Account"]
    cog = boto3.client("cognito-idp", region_name=region)
    lam = boto3.client("lambda", region_name=region)
    iam_c = boto3.client("iam")
    ac = boto3.client("bedrock-agentcore-control", region_name=region)

    harness_name = f"{prefix}-harness".replace("-", "_")
    gateway_name = f"{prefix}-gateway"
    fn_name = f"{prefix}-order-mgmt"
    cred_name = f"{prefix}-m2m-provider"
    lambda_role = f"{prefix}-lambda-role"
    gw_role = f"{prefix}-gateway-role"
    harness_role = f"{prefix}-harness-role"
    gw_policy = f"{prefix}-gw-lambda-policy"
    harness_policy = f"{prefix}-harness-policy"
    pool1_name = f"{prefix}-user-pool"
    pool2_name = f"{prefix}-m2m-pool"

    deleted, skipped = [], []

    def ok(m):
        deleted.append(m)
        print(f"  ✓ {m}")

    def skip(m):
        skipped.append(m)
        print(f"  – {m}")

    def _wait_gone(check_fn, retries=24, delay=5, **kwargs):
        for _ in range(retries):
            try:
                check_fn(**kwargs)
                time.sleep(delay)
            except Exception:
                return

        # 1. Harness 구성
    print("\n[1/7] Harness")
    try:
        matches = [h for h in ac.list_harnesses().get("harnesses", []) if h.get("harnessName") == harness_name]
        if matches:
            hid = matches[0]["harnessId"]
            ac.delete_harness(harnessId=hid)
            ok(f"Harness {hid} delete initiated")
            _wait_gone(ac.get_harness, harnessId=hid)
            ok("Harness deleted")
        else:
            skip("Harness not found")
    except Exception as e:
        skip(f"Harness: {e}")

    # 2. Gateway + 대상
    print("\n[2/7] Gateway + targets")
    try:
        gws = [g for g in ac.list_gateways().get("items", []) if g.get("name") == gateway_name]
        if gws:
            gid = gws[0]["gatewayId"]
            for t in ac.list_gateway_targets(gatewayIdentifier=gid).get("items", []):
                tid = t["targetId"]
                ac.delete_gateway_target(gatewayIdentifier=gid, targetId=tid)
                ok(f"Target {tid} delete initiated")
                _wait_gone(ac.get_gateway_target, gatewayIdentifier=gid, targetId=tid)
                ok(f"Target {tid} deleted")
            ac.delete_gateway(gatewayIdentifier=gid)
            ok(f"Gateway {gid} delete initiated")
            _wait_gone(ac.get_gateway, gatewayIdentifier=gid)
            ok("Gateway deleted")
        else:
            skip("Gateway not found")
    except Exception as e:
        skip(f"Gateway: {e}")

    # 3. 자격 증명 공급자
    print("\n[3/7] Credential provider")
    try:
        ac.get_oauth2_credential_provider(name=cred_name)
        ac.delete_oauth2_credential_provider(name=cred_name)
        ok(f"{cred_name} deleted")
    except Exception as e:
        skip(
            "Credential provider not found"
            if "not found" in str(e).lower() or "ResourceNotFound" in str(type(e).__name__)
            else f"{e}"
        )

        # 4. Lambda 구성
    print("\n[4/7] Lambda")
    try:
        lam.get_function(FunctionName=fn_name)
        lam.delete_function(FunctionName=fn_name)
        ok(f"{fn_name} deleted")
    except lam.exceptions.ResourceNotFoundException:
        skip("Lambda not found")
    except Exception as e:
        skip(f"Lambda: {e}")

    # 5. IAM 역할 및 정책
    print("\n[5/7] IAM roles & policies")

    def _del_role(rname, policy_names=None):
        try:
            iam_c.get_role(RoleName=rname)
        except iam_c.exceptions.NoSuchEntityException:
            skip(f"Role {rname} not found")
            return
        except Exception as e:
            skip(f"{rname}: {e}")
            return
        try:
            for p in iam_c.list_attached_role_policies(RoleName=rname)["AttachedPolicies"]:
                iam_c.detach_role_policy(RoleName=rname, PolicyArn=p["PolicyArn"])
        except Exception:
            pass
        for pn in policy_names or []:
            try:
                iam_c.delete_policy(PolicyArn=f"arn:aws:iam::{account_id}:policy/{pn}")
                ok(f"Policy {pn} deleted")
            except Exception:
                pass
        try:
            iam_c.delete_role(RoleName=rname)
            ok(f"Role {rname} deleted")
        except Exception as e:
            skip(f"Role {rname}: {e}")

    _del_role(lambda_role)
    _del_role(gw_role, [gw_policy])
    _del_role(harness_role, [harness_policy])

    # 6. Cognito 풀 #2
    print("\n[6/7] Cognito Pool #2")
    try:
        m = [p for p in cog.list_user_pools(MaxResults=60)["UserPools"] if p["Name"] == pool2_name]
        if m:
            pid = m[0]["Id"]
            try:
                d = cog.describe_user_pool(UserPoolId=pid)["UserPool"].get("Domain")
                if d:
                    cog.delete_user_pool_domain(Domain=d, UserPoolId=pid)
                    ok(f"Domain {d} deleted")
            except Exception:
                pass
            cog.delete_user_pool(UserPoolId=pid)
            ok(f"Pool #2 {pid} deleted")
        else:
            skip("Pool #2 not found")
    except Exception as e:
        skip(f"Pool #2: {e}")

    # 7. Cognito 풀 #1
    print("\n[7/7] Cognito Pool #1")
    try:
        m = [p for p in cog.list_user_pools(MaxResults=60)["UserPools"] if p["Name"] == pool1_name]
        if m:
            pid = m[0]["Id"]
            cog.delete_user_pool(UserPoolId=pid)
            ok(f"Pool #1 {pid} deleted")
        else:
            skip("Pool #1 not found")
    except Exception as e:
        skip(f"Pool #1: {e}")

    print(f"\n{'=' * 50}")
    print(f"Deleted {len(deleted)} resources, skipped {len(skipped)}")
    print("✅ Cleanup complete!")
