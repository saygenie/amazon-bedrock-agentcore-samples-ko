# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Admin API를 통해 PingFederate를 구성하는 Lambda 핸들러입니다.

내부 ALB에 직접 접근할 수 있도록 VPC 내부에서 CDK 사용자 지정 리소스로 실행됩니다.
"""

import json
import logging
import os
import time
import urllib.request
import ssl

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# PingFederate 구성 상수
CLIENT_ID = "agentcore-client"
CLIENT_SECRET = os.environ.get("PINGFED_CLIENT_SECRET", "agentcore-test-secret-12345")  # pragma: allowlist secret
ATM_ID = "agentcoreJwtAtm"
OIDC_POLICY_ID = "agentcoreOidcPolicy"
SIGNING_KEY_ID = "agentcore-signing-key"


def handler(event, context):
    """CloudFormation 사용자 지정 리소스 핸들러입니다."""
    request_type = event.get("RequestType", "")
    response_url = event.get("ResponseURL", "")
    stack_id = event.get("StackId", "")
    request_id = event.get("RequestId", "")
    logical_id = event.get("LogicalResourceId", "")
    physical_id = event.get("PhysicalResourceId", logical_id)

    props = event.get("ResourceProperties", {})
    admin_url = props.get("AdminUrl", "")
    admin_user = props.get("AdminUser", "")
    secret_id = props.get("SecretId", "")
    base_url = props.get("BaseUrl", "")

    # Secrets Manager에서 관리자 암호 가져오기
    # Lambda VPC ENI는 콜드 스타트 시 초기화에 몇 초가 걸려 첫 네트워크 호출에서
    # "[Errno 16] Device or resource busy" 오류가 발생할 수 있으므로 재시도 로직 적용
    sm = boto3.client("secretsmanager")
    secret_value = json.loads(_retry_on_eni_busy(lambda: sm.get_secret_value(SecretId=secret_id))["SecretString"])
    admin_password = secret_value["adminPassword"]

    try:
        if request_type in ("Create", "Update"):
            configure_pingfederate(admin_url, admin_user, admin_password, base_url)
            discovery_url = f"{base_url}/.well-known/openid-configuration"
            send_response(
                response_url,
                "SUCCESS",
                stack_id,
                request_id,
                logical_id,
                physical_id,
                {
                    "DiscoveryUrl": discovery_url,
                    "ClientId": CLIENT_ID,
                },
            )
        else:
            # Delete 요청에서는 해제할 항목이 없음
            send_response(response_url, "SUCCESS", stack_id, request_id, logical_id, physical_id)
    except Exception as e:
        logger.exception("Configuration failed")
        send_response(
            response_url,
            "FAILED",
            stack_id,
            request_id,
            logical_id,
            physical_id,
            reason=str(e),
        )


def _retry_on_eni_busy(fn, max_attempts=6, delay=5):
    """'[Errno 16] Device or resource busy'로 실패할 수 있는 호출을 재시도합니다.

    VPC의 Lambda 함수는 콜드 스타트 시 ENI가 실행 환경에 연결되는 동안 일시적인
    OSError가 발생할 수 있습니다. 포기하기 전에 최대 30초(6회 x 5초) 동안 재시도합니다.
    """
    for attempt in range(max_attempts):
        try:
            return fn()
        except OSError as e:
            if attempt == max_attempts - 1:
                raise
            logger.warning(f"VPC ENI not ready (attempt {attempt + 1}/{max_attempts}): {e}")
            time.sleep(delay)


def configure_pingfederate(admin_url, admin_user, admin_password, base_url):
    """Admin API를 통해 PingFederate OAuth/OIDC를 구성합니다."""
    api = f"{admin_url}/pf-admin-api/v1"
    auth = _basic_auth(admin_user, admin_password)
    ctx = _insecure_ssl_context()

    # PingFederate가 준비될 때까지 최대 8분간 대기
    # PingFederate 시작에는 3~5분이 걸릴 수 있으며, ALB 대상 그룹은 트래픽을
    # 라우팅하기 전에 상태 확인을 통과해야 함
    logger.info("Waiting for PingFederate to be ready...")
    max_attempts = 96  # 96 x 5초 = 8분
    for i in range(max_attempts):
        try:
            _api_call("GET", f"{api}/version", auth=auth, ssl_ctx=ctx)
            logger.info("PingFederate is ready")
            break
        except Exception:
            if i == max_attempts - 1:
                raise TimeoutError(f"PingFederate not ready after {max_attempts} attempts")
            time.sleep(5)

    # 1. 서명 키 페어 생성
    logger.info("1. Creating signing key pair...")
    _api_call(
        "POST",
        f"{api}/keyPairs/signing/generate",
        auth=auth,
        ssl_ctx=ctx,
        body={
            "id": SIGNING_KEY_ID,
            "commonName": "AgentCore Signing Key",
            "organization": "AgentCore Sample",
            "country": "US",
            "validDays": 3650,
            "keyAlgorithm": "RSA",
            "keySize": 2048,
            "signatureAlgorithm": "SHA256withRSA",
        },
    )

    # 2. JWT Access Token Manager 생성
    logger.info("2. Creating JWT Access Token Manager...")
    _api_call(
        "POST",
        f"{api}/oauth/accessTokenManagers",
        auth=auth,
        ssl_ctx=ctx,
        body={
            "id": ATM_ID,
            "name": "AgentCore JWT Token Manager",
            "pluginDescriptorRef": {
                "id": "com.pingidentity.pf.access.token.management.plugins.JwtBearerAccessTokenManagementPlugin"
            },
            "configuration": {
                "tables": [
                    {"name": "Symmetric Keys", "rows": []},
                    {"name": "Certificates", "rows": []},
                ],
                "fields": [
                    {"name": "Token Lifetime", "value": "120"},
                    {"name": "Use Centralized Signing Key", "value": "true"},
                    {"name": "JWS Algorithm", "value": "RS256"},
                    {"name": "Active Symmetric Key ID", "value": ""},
                    {"name": "Active Signing Certificate Key ID", "value": ""},
                    {"name": "JWE Algorithm", "value": ""},
                    {"name": "JWE Content Encryption Algorithm", "value": ""},
                    {"name": "Active Symmetric Encryption Key ID", "value": ""},
                    {"name": "Asymmetric Encryption Key", "value": ""},
                    {"name": "Asymmetric Encryption JWKS URL", "value": ""},
                    {"name": "Enable Token Revocation", "value": "false"},
                    {"name": "Include Key ID Header Parameter", "value": "true"},
                    {"name": "Include Issued At Claim", "value": "true"},
                    {"name": "Client ID Claim Name", "value": "client_id"},
                    {"name": "Scope Claim Name", "value": "scope"},
                    {"name": "Space Delimit Scope Values", "value": "true"},
                    {"name": "JWT ID Claim Length", "value": "22"},
                    {
                        "name": "Include X.509 Thumbprint Header Parameter",
                        "value": "false",
                    },
                    {"name": "Default JWKS URL Cache Duration", "value": "720"},
                    {"name": "Include JWE Key ID Header Parameter", "value": "true"},
                    {
                        "name": "Include JWE X.509 Thumbprint Header Parameter",
                        "value": "false",
                    },
                    {
                        "name": "Authorization Details Claim Name",
                        "value": "authorization_details",
                    },
                    {"name": "Issuer Claim Value", "value": base_url},
                    {"name": "Audience Claim Value", "value": ""},
                    {"name": "Not Before Claim Offset", "value": ""},
                    {"name": "Access Grant GUID Claim Name", "value": ""},
                    {
                        "name": "Publish Keys to the PingFederate JWKS Endpoint",
                        "value": "false",
                    },
                    {"name": "JWKS Endpoint Path", "value": ""},
                    {"name": "JWKS Endpoint Cache Duration", "value": "720"},
                    {"name": "Publish Key ID X.509 URL", "value": "false"},
                    {"name": "Publish Thumbprint X.509 URL", "value": "false"},
                    {"name": "Expand Scope Groups", "value": "false"},
                    {"name": "Type Header Value", "value": ""},
                ],
            },
            "attributeContract": {
                "coreAttributes": [],
                "extendedAttributes": [
                    {"name": "sub", "multiValued": False},
                    {"name": "scope", "multiValued": False},
                    {"name": "client_id", "multiValued": False},
                ],
                "defaultSubjectAttribute": "sub",
            },
            "selectionSettings": {"resourceUris": []},
            "accessControlSettings": {"restrictClients": False, "allowedClients": []},
            "sessionValidationSettings": {
                "checkValidAuthnSession": False,
                "checkSessionRevocationStatus": False,
                "updateAuthnSessionActivity": False,
                "includeSessionId": False,
            },
        },
    )

    # 3. 기본 ATM 설정
    logger.info("3. Setting default access token manager...")
    _api_call(
        "PUT",
        f"{api}/oauth/accessTokenManagers/settings",
        auth=auth,
        ssl_ctx=ctx,
        body={"defaultAccessTokenManagerRef": {"id": ATM_ID}},
    )

    # 4. OAuth 인증 서버 설정 구성
    logger.info("4. Configuring OAuth auth server settings...")
    _api_call(
        "PUT",
        f"{api}/oauth/authServerSettings",
        auth=auth,
        ssl_ctx=ctx,
        body={
            "defaultScopeDescription": "",
            "scopes": [
                {"name": "openid", "description": "OpenID Connect", "dynamic": False},
                {"name": "profile", "description": "User profile", "dynamic": False},
                {"name": "email", "description": "Email", "dynamic": False},
            ],
            "scopeGroups": [],
            "exclusiveScopes": [],
            "exclusiveScopeGroups": [],
            "authorizationCodeTimeout": 60,
            "authorizationCodeEntropy": 30,
            "disallowPlainPKCE": False,
            "includeIssuerInAuthorizationResponse": False,
            "persistentGrantLifetime": -1,
            "persistentGrantLifetimeUnit": "DAYS",
            "persistentGrantIdleTimeout": 30,
            "persistentGrantIdleTimeoutTimeUnit": "DAYS",
            "refreshTokenLength": 42,
            "rollRefreshTokenValues": False,
            "refreshTokenRollingGracePeriod": 60,
            "refreshRollingInterval": 0,
            "refreshRollingIntervalTimeUnit": "HOURS",
            "persistentGrantReuseGrantTypes": ["IMPLICIT"],
            "persistentGrantContract": {
                "extendedAttributes": [],
                "coreAttributes": [{"name": "USER_KEY"}, {"name": "USER_NAME"}],
            },
            "bypassAuthorizationForApprovedGrants": False,
            "allowUnidentifiedClientROCreds": False,
            "allowUnidentifiedClientExtensionGrants": False,
            "tokenEndpointBaseUrl": base_url,
            "parReferenceTimeout": 60,
            "parReferenceLength": 24,
            "parStatus": "ENABLED",
            "clientSecretRetentionPeriod": 0,
            "jwtSecuredAuthorizationResponseModeLifetime": 600,
            "dpopProofRequireNonce": False,
            "dpopProofLifetimeSeconds": 120,
            "dpopProofEnforceReplayPrevention": False,
            "bypassAuthorizationForApprovedConsents": False,
            "consentLifetimeDays": -1,
        },
    )

    # 5. 서버 설정 구성
    logger.info("5. Configuring server settings...")
    _api_call(
        "PUT",
        f"{api}/serverSettings",
        auth=auth,
        ssl_ctx=ctx,
        body={
            "contactInfo": {},
            "rolesAndProtocols": {
                "oauthRole": {"enableOauth": True, "enableOpenIdConnect": True},
                "idpRole": {
                    "enable": True,
                    "enableSaml11": True,
                    "enableSaml10": True,
                    "enableWsFed": True,
                    "enableWsTrust": True,
                    "saml20Profile": {"enable": True},
                    "enableOutboundProvisioning": True,
                },
                "spRole": {
                    "enable": True,
                    "enableSaml11": True,
                    "enableSaml10": True,
                    "enableWsFed": True,
                    "enableWsTrust": True,
                    "saml20Profile": {"enable": True, "enableXASP": True},
                    "enableInboundProvisioning": True,
                    "enableOpenIDConnect": True,
                },
                "enableIdpDiscovery": True,
            },
            "federationInfo": {
                "baseUrl": base_url,
                "saml2EntityId": "evaluation",
                "saml1xIssuerId": "",
                "saml1xSourceId": "",
                "wsfedRealm": "",
            },
        },
    )

    # 6. OIDC 정책 생성
    logger.info("6. Creating OIDC policy...")
    _api_call(
        "POST",
        f"{api}/oauth/openIdConnect/policies",
        auth=auth,
        ssl_ctx=ctx,
        body={
            "id": OIDC_POLICY_ID,
            "name": "AgentCore OIDC Policy",
            "idTokenLifetime": 5,
            "attributeContract": {
                "coreAttributes": [{"name": "sub", "multiValued": False}],
                "extendedAttributes": [
                    {"name": "name", "multiValued": False},
                    {"name": "email", "multiValued": False},
                ],
            },
            "attributeMapping": {
                "attributeSources": [],
                "attributeContractFulfillment": {
                    "sub": {"source": {"type": "NO_MAPPING"}},
                    "name": {"source": {"type": "NO_MAPPING"}},
                    "email": {"source": {"type": "NO_MAPPING"}},
                },
                "issuanceCriteria": {"conditionalCriteria": []},
            },
            "includeSriInIdToken": True,
            "includeUserInfoInIdToken": False,
            "includeSHashInIdToken": False,
            "includeX5tInIdToken": False,
            "idTokenTypHeaderValue": "",
            "returnIdTokenOnRefreshGrant": False,
            "reissueIdTokenInHybridFlow": False,
            "accessTokenManagerRef": {"id": ATM_ID},
            "scopeAttributeMappings": {},
        },
    )

    # 7. 기본 OIDC 정책 설정
    logger.info("7. Setting default OIDC policy...")
    _api_call(
        "PUT",
        f"{api}/oauth/openIdConnect/settings",
        auth=auth,
        ssl_ctx=ctx,
        body={
            "defaultPolicyRef": {"id": OIDC_POLICY_ID},
            "sessionSettings": {
                "trackUserSessionsForLogout": False,
                "revokeUserSessionOnLogout": True,
                "sessionRevocationLifetime": 490,
            },
        },
    )

    # 8. OAuth 클라이언트 생성
    logger.info("8. Creating OAuth client...")
    _api_call(
        "POST",
        f"{api}/oauth/clients",
        auth=auth,
        ssl_ctx=ctx,
        body={
            "clientId": CLIENT_ID,
            "enabled": True,
            "redirectUris": [
                f"https://bedrock-agentcore.{os.environ.get('AWS_REGION', 'us-east-1')}.amazonaws.com/identities/oauth2/callback",
                "https://localhost/callback",
            ],
            "grantTypes": ["AUTHORIZATION_CODE", "CLIENT_CREDENTIALS", "REFRESH_TOKEN"],
            "name": "AgentCore OAuth Client",
            "refreshRolling": "SERVER_DEFAULT",
            "refreshTokenRollingIntervalType": "SERVER_DEFAULT",
            "persistentGrantExpirationType": "SERVER_DEFAULT",
            "persistentGrantIdleTimeoutType": "SERVER_DEFAULT",
            "persistentGrantReuseType": "SERVER_DEFAULT",
            "bypassApprovalPage": True,
            "restrictScopes": False,
            "restrictedScopes": [],
            "exclusiveScopes": [],
            "restrictedResponseTypes": [],
            "defaultAccessTokenManagerRef": {"id": ATM_ID},
            "restrictToDefaultAccessTokenManager": False,
            "oidcPolicy": {
                "grantAccessSessionRevocationApi": False,
                "grantAccessSessionSessionManagementApi": False,
                "logoutMode": "NONE",
                "pingAccessLogoutCapable": False,
                "pairwiseIdentifierUserType": False,
            },
            "clientAuth": {
                "type": "SECRET",
                "secret": CLIENT_SECRET,
                "secondarySecrets": [],
            },
            "deviceFlowSettingType": "SERVER_DEFAULT",
            "requireProofKeyForCodeExchange": False,
            "refreshTokenRollingGracePeriodType": "SERVER_DEFAULT",
            "clientSecretRetentionPeriodType": "SERVER_DEFAULT",
            "requireDpop": False,
            "requireSignedRequests": False,
        },
    )

    # 검증: VPC 내부에서 확인되지 않을 수 있는 퍼블릭 도메인 대신 ALB 내부 DNS 이름으로
    # 토큰 요청. 엔진 리스너는 포트 443을 사용
    logger.info("Verifying: requesting client_credentials token...")
    alb_host = admin_url.split("//")[1].split(":")[0]  # ALB DNS 이름 추출
    token_resp = _token_request(f"https://{alb_host}", ctx)
    if "access_token" not in token_resp:
        raise RuntimeError(f"Token verification failed: {token_resp}")
    logger.info("Configuration complete — token verification successful")


def _token_request(base_url, ssl_ctx):
    """구성을 검증하기 위해 client_credentials 토큰을 요청합니다."""
    url = f"{base_url}/as/token.oauth2"
    data = f"grant_type=client_credentials&client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}&scope=openid"
    req = urllib.request.Request(url, data=data.encode(), method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=30) as resp:  # nosec B310
        return json.loads(resp.read())


def _api_call(method, url, auth, ssl_ctx, body=None):
    """PingFederate에 API를 호출합니다."""
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", auth)
    req.add_header("X-XSRF-Header", "PingFederate")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, context=ssl_ctx, timeout=30) as resp:  # nosec B310
        resp_body = resp.read()
        if resp_body:
            result = json.loads(resp_body)
            if "resultId" in result:
                raise RuntimeError(f"API call failed: {result}")
            return result
        return {}


def _basic_auth(user, password):
    """Basic 인증 헤더 값을 반환합니다."""
    import base64

    credentials = base64.b64encode(f"{user}:{password}".encode()).decode()
    return f"Basic {credentials}"


def _insecure_ssl_context():
    """인증서 검증을 건너뛰는 SSL 컨텍스트를 생성합니다(프라이빗 CA)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def send_response(
    response_url,
    status,
    stack_id,
    request_id,
    logical_id,
    physical_id,
    data=None,
    reason="",
):
    """CloudFormation 사용자 지정 리소스에 응답을 전송합니다."""
    body = json.dumps(
        {
            "Status": status,
            "Reason": reason or "See CloudWatch Log Stream",
            "PhysicalResourceId": physical_id,
            "StackId": stack_id,
            "RequestId": request_id,
            "LogicalResourceId": logical_id,
            "Data": data or {},
        }
    ).encode()
    req = urllib.request.Request(response_url, data=body, method="PUT")
    req.add_header("Content-Type", "")
    req.add_header("Content-Length", str(len(body)))
    urllib.request.urlopen(req, timeout=30)  # nosec B310
