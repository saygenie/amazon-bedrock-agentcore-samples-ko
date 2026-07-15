"""
Lab 03: OAuth2 Credential Provider 및 M2M 인증 설정

Cognito의 OAuth2 client credentials grant를 사용하여 Gateway와 Runtime 간
machine-to-machine(M2M) 인증을 설정합니다.

아키텍처:
- Gateway는 M2M 클라이언트 자격 증명을 사용해 Cognito에서 액세스 토큰을 얻음
- M2M 토큰에는 세분화된 권한 부여를 위한 사용자 지정 scope가 포함됨
- Runtime은 M2M 토큰을 검증하고 승인된 scope 내의 작업만 허용함
- OAuth2 credential provider는 AWS Secrets Manager의 자격 증명 저장을 관리함

기반 파일: gateway-to-runtime/07_connect_gateway_to_runtime.py
"""

import json
import boto3
import time
from typing import Dict, Optional
from botocore.exceptions import ClientError

from lab_helpers.config import AWS_REGION, AWS_PROFILE
from lab_helpers.parameter_store import get_parameter, put_parameter
from lab_helpers.constants import PARAMETER_PATHS


class OAuth2CredentialProviderSetup:
    """M2M 인증용 OAuth2 credential provider를 관리합니다."""

    def __init__(self, region: str = AWS_REGION, profile: str = AWS_PROFILE):
        """OAuth2 설정 헬퍼를 초기화합니다."""
        self.session = boto3.Session(profile_name=profile, region_name=region)
        self.agentcore = self.session.client("bedrock-agentcore-control", region_name=region)
        self.iam = self.session.client("iam", region_name=region)
        self.ssm = self.session.client("ssm", region_name=region)
        self.sts = self.session.client("sts", region_name=region)

        self.region = region
        self.account_id = self.sts.get_caller_identity()["Account"]
        self.prefix = "aiml301"

    def create_oauth2_credential_provider(self) -> Dict:
        """
        M2M 인증용 OAuth2 credential provider를 생성합니다.

        이 provider는 M2M 클라이언트 자격 증명을 관리하고 Gateway가
        client credentials grant를 사용해 Runtime을 인증하도록 합니다.

        반환:
            provider_arn, secret_arn 및 구성이 포함된 딕셔너리
        """
        print("\n" + "=" * 70)
        print("CREATING OAUTH2 CREDENTIAL PROVIDER")
        print("=" * 70 + "\n")

        # Cognito 구성에서 M2M 자격 증명 조회(Lab-01에서 설정)
        try:
            m2m_client_id = get_parameter(PARAMETER_PATHS["cognito"]["m2m_client_id"])
            m2m_client_secret = get_parameter(PARAMETER_PATHS["cognito"]["m2m_client_secret"])
            user_pool_id = get_parameter(PARAMETER_PATHS["cognito"]["user_pool_id"])
        except Exception as e:
            print(f"❌ Failed to retrieve Cognito M2M credentials from SSM: {e}")
            print("   Ensure Lab-01 Cognito setup has been completed first")
            raise

        print("✅ Retrieved M2M credentials from Cognito")
        print(f"   - M2M Client ID: {m2m_client_id}")
        print("   - M2M Client Secret: ****")
        print(f"   - User Pool ID: {user_pool_id}")

        # OAuth2 discovery 엔드포인트용 discovery URL 구성
        # AgentCore에 Cognito OIDC 구성 위치를 알려 줌
        discovery_url = (
            f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"
        )

        provider_name = f"{self.prefix}-runtime-m2m-credentials"

        print(f"\nCreating OAuth2 credential provider: {provider_name}")
        print(f"Discovery URL: {discovery_url}\n")

        try:
            # OAuth2 credential provider 생성
            # AgentCore에서 다음 작업을 자동으로 수행:
            # 1. AWS Secrets Manager에 자격 증명 저장
            # 2. 필요한 경우 자격 증명 교체 관리
            # 3. client credentials grant로 토큰 생성
            response = self.agentcore.create_oauth2_credential_provider(
                name=provider_name,
                credentialProviderVendor="CustomOauth2",
                oauth2ProviderConfigInput={
                    "customOauth2ProviderConfig": {
                        "oauthDiscovery": {"discoveryUrl": discovery_url},
                        "clientId": m2m_client_id,
                        "clientSecret": m2m_client_secret,
                    }
                },
            )

            provider_arn = response["oAuth2CredentialProviderArn"]
            secret_arn = response.get("secretArn", "")

            print("✅ OAuth2 credential provider created")
            print(f"   - Provider ARN: {provider_arn}")  # codeql[py/clear-text-logging-sensitive-data]
            print(f"   - Secret ARN: {secret_arn}")  # codeql[py/clear-text-logging-sensitive-data]

            # 구성 저장
            oauth2_config = {
                "provider_name": provider_name,
                "provider_arn": provider_arn,
                "secret_arn": secret_arn,
                "discovery_url": discovery_url,
                "m2m_client_id": m2m_client_id,
                "region": self.region,
                "account_id": self.account_id,
            }

            # SSM에 저장
            put_parameter(f"/{self.prefix}/lab-03/oauth2-provider-arn", provider_arn)
            put_parameter(f"/{self.prefix}/lab-03/oauth2-secret-arn", secret_arn)
            put_parameter(f"/{self.prefix}/lab-03/oauth2-config", json.dumps(oauth2_config))

            print("\n✅ OAuth2 configuration saved to SSM Parameter Store")

            return oauth2_config

        except Exception as e:
            print(f"❌ Failed to create OAuth2 credential provider: {e}")
            raise

    def add_runtime_as_oauth2_target(
        self,
        gateway_id: str,
        runtime_arn: str,
        oauth2_provider_arn: Optional[str] = None,
    ) -> Dict:
        """
        OAuth2 M2M 인증을 사용해 Runtime을 Gateway 대상으로 추가합니다.

        Gateway가 Runtime 호출 요청을 받으면 다음 작업을 수행합니다.
        1. OAuth2 provider를 사용해 M2M 액세스 토큰 획득
        2. 요청에 토큰 포함: Authorization: Bearer {M2M_token}
        3. Runtime에서 토큰을 검증하고 scope를 기준으로 작업 승인

        인자:
            gateway_id: Gateway 식별자
            runtime_arn: 대상으로 등록할 Runtime ARN
            oauth2_provider_arn: OAuth2 provider ARN(제공하지 않으면 SSM에서 조회)

        반환:
            대상 구성이 포함된 딕셔너리
        """
        print("\n" + "=" * 70)
        print("ADDING RUNTIME AS GATEWAY TARGET WITH OAUTH2")
        print("=" * 70 + "\n")

        # 제공되지 않은 경우 OAuth2 provider ARN 조회
        if not oauth2_provider_arn:
            try:
                oauth2_provider_arn = get_parameter(f"/{self.prefix}/lab-03/oauth2-provider-arn")
                print(
                    f"✅ Retrieved OAuth2 provider ARN from SSM: {oauth2_provider_arn}"
                )  # codeql[py/clear-text-logging-sensitive-data]
            except Exception as e:
                print(f"❌ OAuth2 provider ARN not found in SSM: {e}")
                print("   Ensure OAuth2 credential provider has been created first")
                raise

        # scope에 사용할 resource server 식별자 조회
        try:
            resource_server_id = get_parameter(PARAMETER_PATHS["cognito"]["resource_server_identifier"])
        except Exception as e:
            print(f"❌ Failed to retrieve resource server identifier: {e}")
            raise

        # M2M scope 정의
        # 이 scope는 M2M 토큰에 포함되고 Runtime에서 검증됨
        scopes = [
            f"{resource_server_id}/mcp.invoke",
            f"{resource_server_id}/runtime.access",
        ]

        target_name = f"{self.prefix}-runtime-m2m-target"

        print("Creating Gateway target with OAuth2 M2M authentication:")
        print(f"  - Gateway ID: {gateway_id}")
        print(f"  - Runtime ARN: {runtime_arn}")
        print(f"  - Target Name: {target_name}")
        print(f"  - Scopes: {', '.join(scopes)}\n")

        try:
            # OAuth2 credential provider를 사용해 Gateway 대상 생성
            response = self.agentcore.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name=target_name,
                targetConfiguration={"mcp": {"mcpServer": {"runtimeArn": runtime_arn}}},
                credentialProviderConfigurations=[
                    {
                        "credentialProviderType": "OAUTH",
                        "credentialProvider": {
                            "oauthCredentialProvider": {
                                "providerArn": oauth2_provider_arn,
                                "scopes": scopes,
                            }
                        },
                    }
                ],
            )

            target_id = response["targetId"]

            print("✅ Runtime added as Gateway target with OAuth2 M2M auth")
            print(f"   - Target ID: {target_id}")
            print(f"   - Target Name: {target_name}")

            target_config = {
                "target_id": target_id,
                "target_name": target_name,
                "gateway_id": gateway_id,
                "runtime_arn": runtime_arn,
                "oauth2_provider_arn": oauth2_provider_arn,
                "scopes": scopes,
                "credential_type": "OAUTH",
            }

            # SSM에 저장
            put_parameter(f"/{self.prefix}/lab-03/gateway-m2m-target", json.dumps(target_config))

            print("\n✅ Gateway M2M target configuration saved to SSM Parameter Store")

            return target_config

        except Exception as e:
            print(f"❌ Failed to add Runtime as Gateway target: {e}")
            raise

    def update_gateway_oauth2_permissions(self, gateway_role_arn: Optional[str] = None) -> None:
        """
        OAuth2 자격 증명 접근 권한으로 Gateway IAM 역할을 업데이트합니다.

        Gateway 역할에 필요한 권한:
        - bedrock-agentcore:GetResourceOauth2Token
        - secretsmanager:GetSecretValue

        인자:
            gateway_role_arn: Gateway 역할 ARN(제공하지 않으면 SSM에서 조회)
        """
        print("\n" + "=" * 70)
        print("UPDATING GATEWAY IAM ROLE WITH OAUTH2 PERMISSIONS")
        print("=" * 70 + "\n")

        # OAuth2 보안 암호 ARN 조회
        try:
            secret_arn = get_parameter(f"/{self.prefix}/lab-03/oauth2-secret-arn")
            provider_arn = get_parameter(f"/{self.prefix}/lab-03/oauth2-provider-arn")
        except Exception as e:
            print(f"❌ Failed to retrieve OAuth2 configuration: {e}")
            raise

        # 제공되지 않은 경우 Gateway 역할 ARN 조회
        if not gateway_role_arn:
            try:
                # 먼저 기존 파라미터에서 조회 시도
                response = self.ssm.get_parameter(Name=f"/{self.prefix}/lab-03/gateway-role-arn")
                gateway_role_arn = response["Parameter"]["Value"]
                print(f"✅ Retrieved Gateway role ARN from SSM: {gateway_role_arn}")
            except ClientError:
                print("❌ Gateway role ARN not found in SSM")
                raise

        # ARN에서 역할 이름 추출
        # ARN 형식: arn:aws:iam::ACCOUNT:role/ROLE_NAME
        role_name = gateway_role_arn.split("/")[-1]

        print(f"Updating IAM role: {role_name}\n")

        # OAuth2 권한 정책 정의
        oauth2_permissions = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "GetResourceOauth2Token",
                    "Effect": "Allow",
                    "Action": ["bedrock-agentcore:GetResourceOauth2Token"],
                    "Resource": [provider_arn],
                },
                {
                    "Sid": "AccessSecretsManager",
                    "Effect": "Allow",
                    "Action": ["secretsmanager:GetSecretValue"],
                    "Resource": [secret_arn],
                },
            ],
        }

        try:
            self.iam.put_role_policy(
                RoleName=role_name,
                PolicyName=f"{self.prefix}-oauth2-credentials-policy",
                PolicyDocument=json.dumps(oauth2_permissions),
            )

            print("✅ OAuth2 permissions attached to Gateway role")
            print(f"   - GetResourceOauth2Token: {provider_arn}")
            print(f"   - GetSecretValue: {secret_arn}")  # codeql[py/clear-text-logging-sensitive-data]

        except Exception as e:
            print(f"❌ Failed to update Gateway role permissions: {e}")
            raise

    def setup_m2m_authentication_complete(self, gateway_id: str, runtime_arn: str, gateway_role_arn: str) -> Dict:
        """
        M2M 인증 설정 워크플로를 완료합니다.

        단계:
        1. OAuth2 credential provider 생성
        2. OAuth2를 사용해 Runtime을 Gateway 대상으로 추가
        3. OAuth2 권한으로 Gateway IAM 역할 업데이트

        인자:
            gateway_id: Gateway 식별자
            runtime_arn: Runtime ARN
            gateway_role_arn: Gateway IAM 역할 ARN

        반환:
            전체 M2M 인증 구성
        """
        print("\n" + "=" * 70)
        print("SETTING UP M2M AUTHENTICATION (GATEWAY ↔ RUNTIME)")
        print("=" * 70 + "\n")

        print("Configuration:")
        print(f"  Gateway ID: {gateway_id}")
        print(f"  Runtime ARN: {runtime_arn}")
        print(f"  Gateway Role: {gateway_role_arn}\n")

        # 1단계: OAuth2 credential provider 생성
        oauth2_config = self.create_oauth2_credential_provider()
        time.sleep(5)  # provider 준비 대기

        # 2단계: OAuth2를 사용해 Runtime을 Gateway 대상으로 추가
        target_config = self.add_runtime_as_oauth2_target(
            gateway_id=gateway_id,
            runtime_arn=runtime_arn,
            oauth2_provider_arn=oauth2_config["provider_arn"],
        )

        # 3단계: OAuth2 권한으로 Gateway IAM 역할 업데이트
        self.update_gateway_oauth2_permissions(gateway_role_arn=gateway_role_arn)

        complete_config = {
            "oauth2_provider": oauth2_config,
            "gateway_target": target_config,
            "gateway_id": gateway_id,
            "runtime_arn": runtime_arn,
            "gateway_role_arn": gateway_role_arn,
        }

        # 전체 구성 저장
        put_parameter(
            f"/{self.prefix}/lab-03/m2m-auth-complete-config",
            json.dumps(complete_config, indent=2),
        )

        print("\n" + "=" * 70)
        print("✅ M2M AUTHENTICATION SETUP COMPLETE")
        print("=" * 70 + "\n")

        print("Gateway-to-Runtime M2M Flow:")
        print("  1. Client sends request to Gateway with User JWT")
        print("  2. Gateway validates User JWT")
        print("  3. Gateway uses OAuth2 provider to get M2M token from Cognito")
        print("  4. Gateway calls Runtime with M2M Bearer token")
        print("  5. Runtime validates M2M token and authorizes operation")
        print(f"\nM2M Scopes: {', '.join(target_config['scopes'])}")  # codeql[py/clear-text-logging-sensitive-data]
        print("\nAll configuration saved to SSM Parameter Store")

        return complete_config

    def cleanup_oauth2_resources(self) -> None:
        """OAuth2 credential provider 및 관련 리소스를 정리합니다."""
        print("\nCleaning up OAuth2 resources...")

        try:
            # SSM에서 provider ARN 조회
            provider_arn = get_parameter(f"/{self.prefix}/lab-03/oauth2-provider-arn")

            # OAuth2 credential provider 삭제
            provider_id = provider_arn.split("/")[-1]
            self.agentcore.delete_oauth2_credential_provider(oAuth2CredentialProviderId=provider_id)
            print("✅ Deleted OAuth2 credential provider")

        except Exception as e:
            print(f"⚠️  Could not delete OAuth2 provider: {e}")

        # SSM 파라미터 삭제
        ssm_params = [
            f"/{self.prefix}/lab-03/oauth2-provider-arn",
            f"/{self.prefix}/lab-03/oauth2-secret-arn",
            f"/{self.prefix}/lab-03/oauth2-config",
            f"/{self.prefix}/lab-03/gateway-m2m-target",
            f"/{self.prefix}/lab-03/m2m-auth-complete-config",
        ]

        for param in ssm_params:
            try:
                self.ssm.delete_parameter(Name=param)
            except:  # noqa: E722
                pass

        print("✅ OAuth2 cleanup complete")
