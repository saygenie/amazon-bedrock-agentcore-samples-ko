"""
AIML301 Workshop용 Cognito 설정 헬퍼
Lab 3~5의 인증 인프라를 설정합니다.

인증 흐름:
- Lab 3: 최종 사용자용 Cognito JWT 인증을 사용하는 Gateway
- Lab 3~5: client credentials를 사용하는 Gateway-to-Runtime M2M 인증
- Lab 4 이상: 고급 사용 사례를 위한 선택적 사용자 기반 접근 제어

생성하는 Cognito 리소스:
1. User Pool: aiml301-UserPool
2. User Auth Client: aiml301-UserAuthClient(최종 사용자 인증용 public 클라이언트)
3. M2M Client: aiml301-M2MClient(서비스 간 인증용 confidential 클라이언트)
4. Resource Server: aiml301-agentcore-runtime(사용자 지정 scope 포함)
5. User Pool Domain: aiml301-agentcore-{timestamp}
6. 테스트 사용자: testuser@aiml301.example.com
"""

import json
import time
import boto3
from typing import Dict, Any, Optional
from lab_helpers.config import AWS_REGION, AWS_PROFILE
from lab_helpers.parameter_store import put_parameter, get_parameter, delete_parameter
from lab_helpers.constants import PARAMETER_PATHS


class CognitoSetup:
    """Cognito User Pool 설정 및 구성을 관리합니다."""

    def __init__(self, region: str = AWS_REGION, profile: str = AWS_PROFILE):
        """Cognito 클라이언트와 세션을 초기화합니다."""
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.cognito = self.session.client("cognito-idp", region_name=region)
        self.region = region
        self.prefix = "aiml301"
        self.test_user_email = f"testuser@{self.prefix}.example.com"
        self.test_user_password = "<enter password>"  # 대문자, 소문자, 숫자, 기호 policy 충족

    def create_user_pool(self) -> str:
        """
        보안 모범 사례에 따라 Cognito User Pool을 생성합니다.
        반환: User Pool ID
        """
        user_pool_name = f"{self.prefix}-UserPool"

        print(f"Creating User Pool: {user_pool_name}...")

        try:
            response = self.cognito.create_user_pool(
                PoolName=user_pool_name,
                Policies={
                    "PasswordPolicy": {
                        "MinimumLength": 8,
                        "RequireUppercase": True,
                        "RequireLowercase": True,
                        "RequireNumbers": True,
                        "RequireSymbols": True,
                        "TemporaryPasswordValidityDays": 7,
                    }
                },
                # 가입 시 이메일 자동 확인
                AutoVerifiedAttributes=["email"],
                # 이메일 기반 사용자 이름(대소문자 구분 안 함)
                UsernameAttributes=["email"],
                EmailConfiguration={"EmailSendingAccount": "COGNITO_DEFAULT"},
                MfaConfiguration="OFF",  # Workshop 단순화를 위해 비활성화
                AccountRecoverySetting={"RecoveryMechanisms": [{"Name": "verified_email", "Priority": 1}]},
            )

            user_pool_id = response["UserPool"]["Id"]
            user_pool_arn = response["UserPool"]["Arn"]

            print(f"✅ User Pool created: {user_pool_id}")

            return user_pool_id, user_pool_arn

        except self.cognito.exceptions.UserPoolTaggingException as e:
            print(f"❌ Error creating user pool: {e}")
            raise

    def create_resource_server(self, user_pool_id: str) -> str:
        """
        세분화된 권한 부여를 위한 사용자 지정 scope가 있는 Resource Server를 생성합니다.

        Scope:
        - mcp.invoke: MCP 서버 도구 호출 권한
        - runtime.access: AgentCore Runtime 접근 권한

        반환: Resource Server 식별자
        """
        resource_server_id = f"{self.prefix}-agentcore-runtime"
        resource_server_name = f"{self.prefix} AgentCore Runtime API"

        print(f"Creating Resource Server: {resource_server_id}...")

        try:
            response = self.cognito.create_resource_server(  # noqa: F841
                UserPoolId=user_pool_id,
                Identifier=resource_server_id,
                Name=resource_server_name,
                Scopes=[
                    {
                        "ScopeName": "mcp.invoke",
                        "ScopeDescription": "Permission to invoke MCP server tools",
                    },
                    {
                        "ScopeName": "runtime.access",
                        "ScopeDescription": "Permission to access AgentCore Runtime",
                    },
                ],
            )

            print(f"✅ Resource Server created: {resource_server_id}")
            return resource_server_id

        except Exception as e:
            print(f"❌ Error creating resource server: {e}")
            raise

    def create_user_auth_client(self, user_pool_id: str) -> str:
        """
        public User Auth Client를 생성합니다.
        사용자 이름과 암호를 사용하는 최종 사용자 인증에 사용합니다.

        반환: Client ID
        """
        client_name = f"{self.prefix}-UserAuthClient"

        print(f"Creating User Auth Client: {client_name}...")

        try:
            response = self.cognito.create_user_pool_client(
                UserPoolId=user_pool_id,
                ClientName=client_name,
                GenerateSecret=False,  # public 클라이언트 - secret 없음
                RefreshTokenValidity=30,
                AccessTokenValidity=60,
                IdTokenValidity=60,
                TokenValidityUnits={
                    "AccessToken": "minutes",
                    "IdToken": "minutes",
                    "RefreshToken": "days",
                },
                ExplicitAuthFlows=[
                    "ALLOW_USER_PASSWORD_AUTH",
                    "ALLOW_ADMIN_USER_PASSWORD_AUTH",
                    "ALLOW_REFRESH_TOKEN_AUTH",
                    "ALLOW_USER_SRP_AUTH",
                ],
                PreventUserExistenceErrors="ENABLED",
                EnableTokenRevocation=True,
                EnablePropagateAdditionalUserContextData=False,
            )

            client_id = response["UserPoolClient"]["ClientId"]
            print(f"✅ User Auth Client created: {client_id}")

            return client_id

        except Exception as e:
            print(f"❌ Error creating user auth client: {e}")
            raise

    def create_m2m_client(self, user_pool_id: str, resource_server_id: str) -> tuple:
        """
        confidential M2M Client를 생성합니다.
        client credentials grant를 사용하는 서비스 간 인증에 사용합니다.

        반환: (Client ID, Client Secret)
        """
        client_name = f"{self.prefix}-M2MClient"

        print(f"Creating M2M Client: {client_name}...")

        try:
            response = self.cognito.create_user_pool_client(
                UserPoolId=user_pool_id,
                ClientName=client_name,
                GenerateSecret=True,  # confidential 클라이언트 - secret 필요
                RefreshTokenValidity=30,
                AccessTokenValidity=60,
                TokenValidityUnits={"AccessToken": "minutes", "RefreshToken": "days"},
                ExplicitAuthFlows=["ALLOW_REFRESH_TOKEN_AUTH"],
                AllowedOAuthFlows=["client_credentials"],
                AllowedOAuthFlowsUserPoolClient=True,
                AllowedOAuthScopes=[
                    f"{resource_server_id}/mcp.invoke",
                    f"{resource_server_id}/runtime.access",
                ],
                EnableTokenRevocation=True,
                EnablePropagateAdditionalUserContextData=True,
            )

            client_id = response["UserPoolClient"]["ClientId"]
            client_secret = response["UserPoolClient"]["ClientSecret"]

            print(f"✅ M2M Client created: {client_id}")
            print("   ⚠️  Client secret: ****")
            print("   ⚠️  Store client secret securely (AWS Secrets Manager recommended)")

            return client_id, client_secret

        except Exception as e:
            print(f"❌ Error creating M2M client: {e}")
            raise

    def create_user_pool_domain(self, user_pool_id: str) -> str:
        """
        OAuth2 토큰 엔드포인트용 User Pool Domain을 생성합니다.

        반환: 도메인 URL
        """
        # 타임스탬프로 고유한 도메인 접두사 생성
        timestamp = str(int(time.time()))
        domain_prefix = f"{self.prefix}-agentcore-{timestamp}"

        print(f"Creating User Pool Domain: {domain_prefix}...")

        try:
            response = self.cognito.create_user_pool_domain(  # noqa: F841
                Domain=domain_prefix, UserPoolId=user_pool_id
            )

            # 전체 도메인 URL 구성
            domain_url = f"https://{domain_prefix}.auth.{self.region}.amazoncognito.com"
            print(f"✅ User Pool Domain created: {domain_url}")

            return domain_url

        except Exception as e:
            print(f"❌ Error creating user pool domain: {e}")
            raise

    def create_groups(self, user_pool_id: str) -> None:
        """
        역할 기반 접근 제어용 Cognito 그룹을 생성합니다.

        그룹:
        - sre: 교정 계획을 생성하는 SRE 사용자(Precedence 10)
        - approvers: 계획을 승인하고 실행하는 사용자(Precedence 5)

        Precedence 숫자가 낮을수록 우선순위가 높습니다.
        """
        groups = [
            {
                "GroupName": "sre",
                "Description": "SRE users who create remediation plans",
                "Precedence": 10,
            },
            {
                "GroupName": "approvers",
                "Description": "Approvers who approve and execute remediation plans",
                "Precedence": 5,
            },
        ]

        print("Creating Cognito groups...")

        for group in groups:
            try:
                self.cognito.create_group(
                    UserPoolId=user_pool_id,
                    GroupName=group["GroupName"],
                    Description=group["Description"],
                    Precedence=group["Precedence"],
                )
                print(f"✅ Group created: {group['GroupName']} (Precedence: {group['Precedence']})")
            except self.cognito.exceptions.GroupExistsException:
                print(f"ℹ️  Group already exists: {group['GroupName']}")
            except Exception as e:
                print(f"❌ Error creating group {group['GroupName']}: {e}")
                raise

    def assign_user_to_group(self, user_pool_id: str, username: str, group_name: str) -> None:
        """사용자를 Cognito 그룹에 할당합니다."""
        try:
            self.cognito.admin_add_user_to_group(UserPoolId=user_pool_id, Username=username, GroupName=group_name)
            print(f"✅ User {username} added to group '{group_name}'")  # codeql[py/clear-text-logging-sensitive-data]
        except Exception as e:
            print(f"❌ Error adding user to group: {e}")
            raise

    def create_test_user(self, user_pool_id: str) -> None:
        """Workshop용 테스트 사용자를 생성합니다(SRE 역할)."""
        print(f"Creating test user: {self.test_user_email}...")

        try:
            self.cognito.admin_create_user(
                UserPoolId=user_pool_id,
                Username=self.test_user_email,
                TemporaryPassword=self.test_user_password,
                UserAttributes=[
                    {"Name": "email", "Value": self.test_user_email},
                    {"Name": "email_verified", "Value": "true"},
                ],
                MessageAction="SUPPRESS",  # 환영 이메일을 보내지 않음
            )

            # Workshop 단순화를 위해 임시 암호와 같은 영구 암호 설정
            self.cognito.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=self.test_user_email,
                Password=self.test_user_password,
                Permanent=True,
            )

            print(f"✅ Test user created: {self.test_user_email}")

        except self.cognito.exceptions.UsernameExistsException:
            print(f"ℹ️  Test user already exists: {self.test_user_email}")
        except Exception as e:
            print(f"❌ Error creating test user: {e}")
            raise

    def create_approver_user(self, user_pool_id: str) -> Dict[str, str]:
        """여러 actor가 참여하는 워크플로용 승인자 테스트 사용자를 생성합니다."""
        approver_email = f"approver@{self.prefix}.example.com"
        approver_password = "<enter password>"  # policy 요구 사항 충족

        print(f"Creating approver user: {approver_email}...")

        try:
            self.cognito.admin_create_user(
                UserPoolId=user_pool_id,
                Username=approver_email,
                TemporaryPassword=approver_password,
                UserAttributes=[
                    {"Name": "email", "Value": approver_email},
                    {"Name": "email_verified", "Value": "true"},
                ],
                MessageAction="SUPPRESS",  # 환영 이메일을 보내지 않음
            )

            # 영구 암호 설정
            self.cognito.admin_set_user_password(
                UserPoolId=user_pool_id,
                Username=approver_email,
                Password=approver_password,
                Permanent=True,
            )

            print(f"✅ Approver user created: {approver_email}")

            return {"email": approver_email, "password": approver_password}

        except self.cognito.exceptions.UsernameExistsException:
            print(f"ℹ️  Approver user already exists: {approver_email}")
            return {"email": approver_email, "password": approver_password}
        except Exception as e:
            print(f"❌ Error creating approver user: {e}")
            raise

    def update_user_auth_client_for_oauth(self, user_pool_id: str, client_id: str, resource_server_id: str) -> None:
        """
        OAuth 흐름과 사용자 지정 scope를 지원하도록 User Auth Client를 업데이트합니다.
        이메일, 그룹 등의 다양한 claim이 포함된 ID 토큰을 사용할 수 있게 합니다.
        """
        print("Updating User Auth Client for OAuth support...")

        try:
            self.cognito.update_user_pool_client(
                UserPoolId=user_pool_id,
                ClientId=client_id,
                # 기존 인증 흐름 유지
                ExplicitAuthFlows=[
                    "ALLOW_USER_PASSWORD_AUTH",
                    "ALLOW_ADMIN_USER_PASSWORD_AUTH",
                    "ALLOW_REFRESH_TOKEN_AUTH",
                    "ALLOW_USER_SRP_AUTH",
                ],
                # OAuth 흐름 추가
                AllowedOAuthFlows=["code", "implicit"],
                AllowedOAuthFlowsUserPoolClient=True,
                # 사용자 지정 scope 추가
                AllowedOAuthScopes=[
                    "openid",
                    "profile",
                    "email",
                    f"{resource_server_id}/mcp.invoke",
                    f"{resource_server_id}/runtime.access",
                ],
                # 로컬 테스트용 콜백 URL 추가
                CallbackURLs=["http://localhost:8080/callback"],
                LogoutURLs=["http://localhost:8080/logout"],
                SupportedIdentityProviders=["COGNITO"],
                # 토큰 유효 기간
                IdTokenValidity=60,
                AccessTokenValidity=60,
                RefreshTokenValidity=30,
                TokenValidityUnits={
                    "AccessToken": "minutes",
                    "IdToken": "minutes",
                    "RefreshToken": "days",
                },
                # secret이 없는 public 클라이언트에서는 비활성화
                EnablePropagateAdditionalUserContextData=False,
                EnableTokenRevocation=True,
                PreventUserExistenceErrors="ENABLED",
            )

            print("✅ User Auth Client updated with OAuth support")
            print("   • OAuth flows: code, implicit")
            print("   • Scopes: openid, profile, email, custom scopes")
            print("   • ID Token will include email and cognito:groups claims")

        except Exception as e:
            print(f"❌ Error updating User Auth Client: {e}")
            raise

    def setup_cognito(self) -> Dict[str, Any]:
        """
        전체 Cognito 설정을 실행하고 구성을 반환합니다.
        """
        print("\n" + "=" * 70)
        print("COGNITO SETUP FOR AIML301 WORKSHOP")
        print("=" * 70 + "\n")

        # User Pool 생성
        user_pool_id, user_pool_arn = self.create_user_pool()

        # Resource Server 생성(M2M Client보다 먼저 생성해야 함)
        resource_server_id = self.create_resource_server(user_pool_id)

        # 인증 클라이언트 생성
        user_auth_client_id = self.create_user_auth_client(user_pool_id)
        m2m_client_id, m2m_client_secret = self.create_m2m_client(user_pool_id, resource_server_id)

        # 도메인 생성
        domain_url = self.create_user_pool_domain(user_pool_id)
        token_endpoint = f"{domain_url}/oauth2/token"

        # 역할 기반 접근 제어용 그룹 생성
        self.create_groups(user_pool_id)

        # 테스트 사용자 생성(개발자 역할)
        self.create_test_user(user_pool_id)
        self.assign_user_to_group(user_pool_id, self.test_user_email, "sre")

        # 승인자 사용자 생성
        approver_user = self.create_approver_user(user_pool_id)
        self.assign_user_to_group(user_pool_id, approver_user["email"], "approvers")

        # 다양한 claim이 있는 ID 토큰을 위해 User Auth Client에 OAuth 지원 추가
        self.update_user_auth_client_for_oauth(user_pool_id, user_auth_client_id, resource_server_id)

        # 구성 생성
        cognito_config = {
            "region": self.region,
            "user_pool_id": user_pool_id,
            "user_pool_arn": user_pool_arn,
            "user_pool_name": f"{self.prefix}-UserPool",
            "domain": domain_url,
            "token_endpoint": token_endpoint,
            "user_auth_client": {
                "client_id": user_auth_client_id,
                "client_name": f"{self.prefix}-UserAuthClient",
                "has_secret": False,
                "oauth_flows": ["code", "implicit"],
                "oauth_scopes": [
                    "openid",
                    "profile",
                    "email",
                    f"{resource_server_id}/mcp.invoke",
                    f"{resource_server_id}/runtime.access",
                ],
            },
            "m2m_client": {
                "client_id": m2m_client_id,
                "client_secret": m2m_client_secret,
                "client_name": f"{self.prefix}-M2MClient",
                "has_secret": True,
            },
            "resource_server": {
                "identifier": resource_server_id,
                "name": f"{self.prefix} AgentCore Runtime API",
                "scopes": [
                    f"{resource_server_id}/mcp.invoke",
                    f"{resource_server_id}/runtime.access",
                ],
            },
            "groups": [
                {"name": "sre", "precedence": 10},
                {"name": "approvers", "precedence": 5},
            ],
            "test_user": {
                "username": self.test_user_email,
                "password": self.test_user_password,
                "email": self.test_user_email,
                "group": "sre",
            },
            "approver_user": {
                "username": approver_user["email"],
                "password": approver_user["password"],
                "email": approver_user["email"],
                "group": "approvers",
            },
        }

        return cognito_config

    def save_to_ssm(self, cognito_config: Dict[str, Any]) -> None:
        """Cognito 구성을 SSM Parameter Store에 저장합니다."""
        print("\n" + "=" * 70)
        print("SAVING COGNITO CONFIG TO SSM PARAMETER STORE")
        print("=" * 70 + "\n")

        params = PARAMETER_PATHS["cognito"]

        # 개별 파라미터 저장
        put_parameter(params["user_pool_id"], cognito_config["user_pool_id"])
        put_parameter(params["user_pool_name"], cognito_config["user_pool_name"])
        put_parameter(params["user_pool_arn"], cognito_config["user_pool_arn"])
        put_parameter(params["domain"], cognito_config["domain"])
        put_parameter(params["token_endpoint"], cognito_config["token_endpoint"])

        put_parameter(
            params["user_auth_client_id"],
            cognito_config["user_auth_client"]["client_id"],
        )
        put_parameter(
            params["user_auth_client_name"],
            cognito_config["user_auth_client"]["client_name"],
        )

        put_parameter(params["m2m_client_id"], cognito_config["m2m_client"]["client_id"])
        put_parameter(params["m2m_client_secret"], cognito_config["m2m_client"]["client_secret"])
        put_parameter(params["m2m_client_name"], cognito_config["m2m_client"]["client_name"])

        put_parameter(
            params["resource_server_id"],
            cognito_config["resource_server"]["identifier"],
        )
        put_parameter(
            params["resource_server_identifier"],
            cognito_config["resource_server"]["identifier"],
        )

        put_parameter(params["test_user_email"], cognito_config["test_user"]["email"])
        put_parameter(params["test_user_password"], cognito_config["test_user"]["password"])

        # 승인자 사용자 자격 증명 저장
        put_parameter(params["approver_user_email"], cognito_config["approver_user"]["email"])
        put_parameter(
            params["approver_user_password"],
            cognito_config["approver_user"]["password"],
        )

        print("✅ Cognito configuration saved to SSM Parameter Store")

    def save_to_file(self, cognito_config: Dict[str, Any], filename: str = "cognito_config.json") -> None:
        """참조용 Cognito 구성을 로컬 JSON 파일에 저장합니다."""
        print(f"\nSaving configuration to {filename}...")

        with open(filename, "w") as f:
            json.dump(cognito_config, f, indent=2)

        print(f"✅ Configuration saved to {filename}")


def setup_cognito_complete() -> Dict[str, Any]:
    """
    전체 Cognito 설정 워크플로를 실행합니다.
    1. 모든 Cognito 리소스 생성
    2. SSM Parameter Store에 저장
    3. 구성 반환
    """
    setup = CognitoSetup()

    # 설정 실행
    cognito_config = setup.setup_cognito()

    # SSM에 저장
    setup.save_to_ssm(cognito_config)

    # 참조용 파일에 저장
    setup.save_to_file(cognito_config)

    print("\n" + "=" * 70)
    print("✅ COGNITO SETUP COMPLETE")
    print("=" * 70)
    print("\nKey Configuration:")
    print(f"  User Pool ID: {cognito_config['user_pool_id']}")  # codeql[py/clear-text-logging-sensitive-data]
    print(f"  Domain: {cognito_config['domain']}")  # codeql[py/clear-text-logging-sensitive-data]
    print(f"  Token Endpoint: {cognito_config['token_endpoint']}")  # codeql[py/clear-text-logging-sensitive-data]
    print("\n  User Auth Client:")
    print(
        f"    • Client ID: {cognito_config['user_auth_client']['client_id']}"
    )  # codeql[py/clear-text-logging-sensitive-data]
    print(
        f"    • OAuth Flows: {', '.join(cognito_config['user_auth_client']['oauth_flows'])}"
    )  # codeql[py/clear-text-logging-sensitive-data]
    print("    • OAuth Scopes: openid, profile, email, custom scopes")
    print("\n  M2M Client:")
    print(
        f"    • Client ID: {cognito_config['m2m_client']['client_id']}"
    )  # codeql[py/clear-text-logging-sensitive-data]
    print("    • Client Secret: ****")
    print("\n  Groups Created:")
    print("    • sre (Precedence: 10) - Tools: generate_remediation_plan")
    print("    • approvers (Precedence: 5) - Tools: execute_remediation_step, validate_remediation_environment")
    print("\n  Users Created:")
    print("    • Test User (SRE): **** (password: ****)")
    print("    • Approver User: **** (password: ****)")
    print("\nAll configuration stored in SSM Parameter Store under /aiml301/cognito/*")
    print("Reference copy saved to cognito_config.json\n")

    return cognito_config


def cleanup_cognito(user_pool_id: Optional[str] = None) -> None:
    """
    Cognito 리소스를 정리합니다.

    인자:
        user_pool_id: 삭제할 User Pool ID(None이면 SSM에서 가져옴)
    """
    setup = CognitoSetup()

    # 제공되지 않은 경우 SSM에서 User Pool ID 가져오기
    if user_pool_id is None:
        try:
            user_pool_id = get_parameter(PARAMETER_PATHS["cognito"]["user_pool_id"])
        except Exception as e:
            print(f"❌ Could not retrieve User Pool ID from SSM: {e}")
            return

    print(
        f"Cleaning up Cognito resources for User Pool: {user_pool_id}..."
    )  # codeql[py/clear-text-logging-sensitive-data]
    print("")

    try:
        # 1단계: User Pool에서 도메인 가져오기(있는 경우)
        print("Step 1: Checking for User Pool Domain...")
        try:
            domain_response = setup.cognito.describe_user_pool(UserPoolId=user_pool_id)
            domain = domain_response.get("UserPool", {}).get("Domain")

            if domain:
                print(f"  Found domain: {domain}")
                print("  Deleting domain...")
                setup.cognito.delete_user_pool_domain(Domain=domain, UserPoolId=user_pool_id)
                print(f"  ✅ Domain deleted: {domain}")
            else:
                print("  No domain configured")
        except Exception as e:
            print(f"  ⚠️  Could not check/delete domain: {e}")

        print("")

        # 2단계: User Pool 삭제
        print(f"Step 2: Deleting User Pool: {user_pool_id}...")
        setup.cognito.delete_user_pool(UserPoolId=user_pool_id)
        print(f"  ✅ User Pool deleted: {user_pool_id}")

        print("")

        # 3단계: SSM 파라미터 삭제
        print("Step 3: Deleting SSM parameters...")
        params = PARAMETER_PATHS["cognito"]
        deleted_count = 0
        for key, param_path in params.items():
            try:
                delete_parameter(param_path)
                deleted_count += 1
            except:  # noqa: E722
                pass  # 파라미터가 없을 수 있음

        print(f"  ✅ Deleted {deleted_count} SSM parameters")
        print("")
        print("✅ Cognito cleanup complete")

    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        raise
