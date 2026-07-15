"""
Lab 04: AgentCore Gateway 및 Runtime 대상 설정

Gateway 인프라를 생성하고 prevention Runtime을 대상으로 등록합니다.

Lab-02 패턴과 Gateway-to-Runtime M2M 인증을 기반으로 합니다.

기능:
- 적절한 신뢰 정책이 포함된 Gateway 서비스 역할 생성
- IAM 인증을 사용하는 AgentCore Gateway 생성
- prevention Runtime을 MCP 대상으로 등록
- M2M OAuth2 인증 지원(선택 사항)
- Parameter Store에 구성 저장
"""

import json
import boto3
import time
import logging
from typing import Dict, Optional, List
from botocore.exceptions import ClientError

# 중앙 집중식 구성 가져오기
from lab_helpers.config import AWS_REGION

logger = logging.getLogger(__name__)

# 구성
REGION = AWS_REGION  # config.py의 중앙 집중식 리전 사용
PREFIX = "aiml301"
GATEWAY_NAME = f"{PREFIX}-prevention-gateway"
GATEWAY_ROLE_NAME = f"{PREFIX}-prevention-gateway-role"
GATEWAY_POLICY_NAME = f"{PREFIX}-gateway-runtime-policy"


class AgentCoreGatewaySetup:
    """Runtime 대상이 포함된 AgentCore Gateway 설정 헬퍼입니다."""

    def __init__(self, region: str = REGION, prefix: str = PREFIX, verbose: bool = True):
        """
        Gateway 설정 헬퍼를 초기화합니다.

        인자:
            region: AWS 리전
            prefix: 리소스 명명 접두사
            verbose: 로깅 활성화 여부
        """
        self.region = region
        self.prefix = prefix
        self.verbose = verbose

        # AWS 클라이언트
        self.iam = boto3.client("iam", region_name=region)
        self.agentcore = boto3.client("bedrock-agentcore-control", region_name=region)
        self.ssm = boto3.client("ssm", region_name=region)
        self.sts = boto3.client("sts", region_name=region)

        # 계정 ID 조회
        self.account_id = self.sts.get_caller_identity()["Account"]

        if verbose:
            logging.basicConfig(level=logging.INFO)
            logger.setLevel(logging.INFO)

    def _log(self, message: str):
        """메시지를 기록합니다."""
        print(f"✓ {message}")
        logger.info(message)

    def _error(self, message: str):
        """오류를 기록합니다."""
        print(f"✗ {message}")
        logger.error(message)

    def create_gateway_service_role(self) -> Dict:
        """
        Gateway에서 Runtime 대상을 호출하는 데 사용할 IAM 서비스 역할을 생성합니다.

        Gateway에는 다음 권한이 필요합니다.
        1. Runtime 대상 호출
        2. CloudWatch 로그 접근
        3. AgentCore 리소스 관리
        4. OAuth 자격 증명 접근(M2M 인증용)

        반환:
            역할 ARN, 역할 이름 및 메타데이터가 포함된 딕셔너리
        """
        self._log("Creating IAM role for Gateway...")

        # 신뢰 정책: bedrock-agentcore 서비스가 역할을 수임하도록 허용
        # 이 계정 및 리전의 Gateway ARN으로 제한
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
                    "Action": "sts:AssumeRole",
                    "Condition": {
                        "StringEquals": {"aws:SourceAccount": self.account_id},
                        "ArnLike": {
                            "aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:gateway/*"
                        },
                    },
                }
            ],
        }

        # 권한 정책: Gateway 작업, Runtime 호출, CloudWatch 로그
        # WorkloadIdentity 및 올바른 OAuth2/Secrets 패턴을 사용하는 riv301 배포에 맞게 업데이트
        permissions_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "InvokeRuntimeTarget",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:InvokeRuntime",
                        "bedrock-agentcore:InvokeGateway",
                    ],
                    "Resource": "*",
                },
                {
                    "Sid": "WorkloadIdentity",
                    "Effect": "Allow",
                    "Action": [
                        "bedrock-agentcore:GetWorkloadAccessToken",
                        "bedrock-agentcore:CreateWorkloadIdentity",
                    ],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:workload-identity-directory/default",
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:workload-identity-directory/default/workload-identity/*",
                    ],
                },
                {
                    "Sid": "OAuth2Credentials",
                    "Effect": "Allow",
                    "Action": ["bedrock-agentcore:GetResourceOauth2Token"],
                    "Resource": [
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:token-vault/default",
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:token-vault/*/oauth2credentialprovider/*",
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:workload-identity-directory/default",
                        f"arn:aws:bedrock-agentcore:{self.region}:{self.account_id}:workload-identity-directory/default/workload-identity/*",
                    ],
                },
                {
                    "Sid": "SecretsManager",
                    "Effect": "Allow",
                    "Action": ["secretsmanager:GetSecretValue"],
                    "Resource": [
                        f"arn:aws:secretsmanager:{self.region}:{self.account_id}:secret:bedrock-agentcore-identity!*",
                        f"arn:aws:secretsmanager:{self.region}:{self.account_id}:secret:bedrock-agentcore-*",
                    ],
                },
                {
                    "Sid": "CloudWatchLogs",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:PutLogEvents",
                    ],
                    "Resource": f"arn:aws:logs:{self.region}:{self.account_id}:log-group:/aws/bedrock-agentcore/gateways/*",
                },
            ],
        }

        try:
            # 역할이 이미 존재하는지 확인
            try:
                role = self.iam.get_role(RoleName=GATEWAY_ROLE_NAME)
                self._log(f"Gateway service role already exists: {GATEWAY_ROLE_NAME}")
                role_arn = role["Role"]["Arn"]
            except self.iam.exceptions.NoSuchEntityException:
                # 새 역할 생성
                response = self.iam.create_role(
                    RoleName=GATEWAY_ROLE_NAME,
                    AssumeRolePolicyDocument=json.dumps(trust_policy),
                    Description="Service role for AgentCore Gateway to invoke Runtime targets - Lab 04",
                )
                role_arn = response["Role"]["Arn"]
                self._log(f"Gateway service role created: {GATEWAY_ROLE_NAME}")

                # 역할 전파 대기
                time.sleep(10)

            # 권한 정책 연결
            self.iam.put_role_policy(
                RoleName=GATEWAY_ROLE_NAME,
                PolicyName=GATEWAY_POLICY_NAME,
                PolicyDocument=json.dumps(permissions_policy),
            )
            self._log(f"Permissions policy attached: {GATEWAY_POLICY_NAME}")

            # Parameter Store에 저장
            self.ssm.put_parameter(
                Name=f"/{self.prefix}/lab-04/gateway-role-arn",
                Value=role_arn,
                Type="String",
                Overwrite=True,
                Description="Gateway service role ARN for Lab-03",
            )
            self._log("Gateway role ARN stored in Parameter Store")

            return {
                "role_arn": role_arn,
                "role_name": GATEWAY_ROLE_NAME,
                "policy_name": GATEWAY_POLICY_NAME,
                "account_id": self.account_id,
                "region": self.region,
            }

        except Exception as e:
            self._error(f"Failed to create Gateway service role: {e}")
            raise

    def create_gateway(
        self,
        gateway_name: str = GATEWAY_NAME,
        role_arn: Optional[str] = None,
        protocol_type: str = "MCP",
        authorizer_type: str = "AWS_IAM",
        authorizer_configuration: Optional[Dict] = None,
    ) -> Dict:
        """
        AgentCore Gateway를 생성합니다.

        인자:
            gateway_name: Gateway 이름
            role_arn: 서비스 역할 ARN(제공하지 않으면 Parameter Store에서 조회)
            protocol_type: Gateway 프로토콜(MCP, HTTP 등)
            authorizer_type: 인바운드 인증 유형(AWS_IAM, CUSTOM_JWT)
            authorizer_configuration: JWT authorizer 구성(CUSTOM_JWT에 필요)
                형식: {"customJWTAuthorizer": {"discoveryUrl": "...", "allowedClients": [...]}}

        반환:
            Gateway ID, URL 및 메타데이터가 포함된 딕셔너리
        """
        self._log("Creating AgentCore Gateway...")

        # 제공되지 않은 경우 역할 ARN 조회
        if not role_arn:
            try:
                response = self.ssm.get_parameter(Name=f"/{self.prefix}/lab-04/gateway-role-arn")
                role_arn = response["Parameter"]["Value"]
                self._log("Retrieved Gateway role ARN from Parameter Store")
            except ClientError:
                self._log("Gateway role not found. Creating...")
                role_info = self.create_gateway_service_role()
                role_arn = role_info["role_arn"]

        try:
            # create_gateway API 호출 파라미터 구성
            create_params = {
                "name": gateway_name,
                "roleArn": role_arn,
                "protocolType": protocol_type,
                "authorizerType": authorizer_type,
            }

            # 제공된 경우 authorizer 구성 추가(CUSTOM_JWT에 필요)
            if authorizer_configuration:
                create_params["authorizerConfiguration"] = authorizer_configuration

            # Gateway 생성
            response = self.agentcore.create_gateway(**create_params)

            gateway_id = response["gatewayId"]
            gateway_url = response["gatewayUrl"]

            self._log(f"Gateway created: {gateway_name}")

            gateway_info = {
                "gateway_id": gateway_id,
                "gateway_url": gateway_url,
                "gateway_name": gateway_name,
                "role_arn": role_arn,
                "protocol_type": protocol_type,
                "authorizer_type": authorizer_type,
                "region": self.region,
            }

            # Parameter Store에 저장
            self.ssm.put_parameter(
                Name=f"/{self.prefix}/lab-04/gateway-config",
                Value=json.dumps(gateway_info, indent=2),
                Type="String",
                Overwrite=True,
                Description="Lab-03 Gateway configuration",
            )
            self._log("Gateway configuration stored in Parameter Store")

            return gateway_info

        except ClientError as e:
            if "AlreadyExists" in str(e) or "already" in str(e).lower():
                self._log(f"Gateway already exists: {gateway_name}")
                # 기존 Gateway 조회 시도
                return self._get_gateway_by_name(gateway_name)
            else:
                self._error(f"Failed to create gateway: {e}")
                raise

    def _get_gateway_by_name(self, gateway_name: str) -> Dict:
        """이름으로 기존 Gateway를 조회합니다."""
        try:
            response = self.agentcore.list_gateways()
            for gw in response.get("gateways", []):
                if gw["name"] == gateway_name:
                    return {
                        "gateway_id": gw["gatewayId"],
                        "gateway_url": gw["gatewayUrl"],
                        "gateway_name": gw["name"],
                        "region": self.region,
                    }
        except Exception as e:
            self._error(f"Failed to retrieve gateway: {e}")
        return None

    def register_runtime_target(
        self,
        gateway_id: str,
        runtime_arn: str,
        target_name: str = "prevention-runtime-target",
        tool_schema: Optional[List[Dict]] = None,
        credentials_type: str = "GATEWAY_IAM_ROLE",
    ) -> Dict:
        """
        Runtime을 Gateway의 대상으로 등록합니다.

        인자:
            gateway_id: Gateway 식별자
            runtime_arn: 대상으로 등록할 Runtime ARN
            target_name: 대상 이름
            tool_schema: 도구 스키마 정의(선택 사항)
            credentials_type: Credential provider 유형(GATEWAY_IAM_ROLE, OAUTH2)

        반환:
            대상 ID와 메타데이터가 포함된 딕셔너리
        """
        self._log(f"Registering Runtime as Gateway target: {target_name}...")

        # 제공되지 않은 경우 기본 도구 스키마 사용
        if not tool_schema:
            tool_schema = [
                {
                    "name": "invoke_prevention_agent",
                    "description": "Invoke the prevention agent with Code Interpreter for infrastructure automation",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Natural language query for prevention analysis",
                            }
                        },
                        "required": ["query"],
                    },
                }
            ]

        try:
            # Runtime ARN에서 MCP 엔드포인트 URL 구성
            # 형식: https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT
            encoded_arn = runtime_arn.replace(":", "%3A").replace("/", "%2F")
            mcp_endpoint_url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

            self._log(f"MCP Endpoint URL: {mcp_endpoint_url}")

            # Runtime을 MCP 대상으로 등록
            # 투명하고 디버깅하기 쉬운 대상 등록을 위해 Lab-03과 같은 명시적 엔드포인트 사용
            response = self.agentcore.create_gateway_target(
                gatewayIdentifier=gateway_id,
                name=target_name,
                targetConfiguration={"mcp": {"mcpServer": {"endpoint": mcp_endpoint_url}}},
                credentialProviderConfigurations=[{"credentialProviderType": credentials_type}],
            )

            target_id = response["targetId"]

            self._log("Runtime registered as Gateway target")
            self._log(f"  Target ID: {target_id}")
            self._log(f"  Target Name: {target_name}")
            self._log(f"  Runtime ARN: {runtime_arn}")

            target_info = {
                "target_id": target_id,
                "target_name": target_name,
                "runtime_arn": runtime_arn,
                "gateway_id": gateway_id,
                "credentials_type": credentials_type,
                "tool_schema": tool_schema,
            }

            # Parameter Store에 저장
            self.ssm.put_parameter(
                Name=f"/{self.prefix}/lab-04/gateway-runtime-target",
                Value=json.dumps(target_info, indent=2),
                Type="String",
                Overwrite=True,
                Description="Lab-03 Gateway Runtime target configuration",
            )
            self._log("Target configuration stored in Parameter Store")

            return target_info

        except Exception as e:
            self._error(f"Failed to register Runtime target: {e}")
            raise

    def list_gateway_targets(self, gateway_id: str) -> List[Dict]:
        """Gateway에 등록된 모든 대상을 나열합니다."""
        try:
            response = self.agentcore.list_gateway_targets(gatewayIdentifier=gateway_id)
            targets = response.get("targets", [])
            self._log(f"Found {len(targets)} Gateway target(s)")
            return targets
        except Exception as e:
            self._error(f"Failed to list Gateway targets: {e}")
            return []

    def get_gateway_status(self, gateway_id: str) -> Dict:
        """Gateway 상태를 조회합니다."""
        try:
            response = self.agentcore.get_gateway(gatewayIdentifier=gateway_id)
            gateway = response["gateway"]
            status = {
                "gateway_id": gateway["gatewayId"],
                "gateway_name": gateway["name"],
                "status": gateway.get("status"),
                "url": gateway.get("gatewayUrl"),
                "protocol": gateway.get("protocolType"),
                "created_at": gateway.get("createdAt"),
                "last_modified": gateway.get("lastModifiedAt"),
            }
            self._log(f"Gateway status: {status['status']}")
            return status
        except Exception as e:
            self._error(f"Failed to get Gateway status: {e}")
            return {"status": "UNKNOWN"}

    def get_stored_config(self) -> Dict:
        """Parameter Store에서 저장된 Gateway 및 Runtime 대상 구성을 조회합니다."""
        try:
            config = {}

            # Gateway 구성 조회
            try:
                response = self.ssm.get_parameter(Name=f"/{self.prefix}/lab-04/gateway-config")
                config["gateway"] = json.loads(response["Parameter"]["Value"])
                self._log("Retrieved Gateway configuration from Parameter Store")
            except ClientError:
                self._log("Gateway configuration not found in Parameter Store")

            # Runtime 대상 구성 조회
            try:
                response = self.ssm.get_parameter(Name=f"/{self.prefix}/lab-04/gateway-runtime-target")
                config["runtime_target"] = json.loads(response["Parameter"]["Value"])
                self._log("Retrieved Runtime target configuration from Parameter Store")
            except ClientError:
                self._log("Runtime target configuration not found in Parameter Store")

            return config

        except Exception as e:
            self._error(f"Failed to retrieve stored configuration: {e}")
            return {}

    def cleanup(self, force: bool = False) -> bool:
        """
        Lab-03 Gateway 리소스를 정리합니다.

        인자:
            force: 확인 없이 강제 삭제할지 여부

        반환:
            정리에 성공하면 True
        """
        self._log("Starting Gateway cleanup...")

        if not force:
            confirm = input("Delete Lab-03 Gateway and related resources? This cannot be undone. (yes/no): ")
            if confirm.lower() != "yes":
                self._log("Cleanup cancelled")
                return False

        try:
            # Parameter Store에서 Gateway ID 조회
            try:
                response = self.ssm.get_parameter(Name=f"/{self.prefix}/lab-04/gateway-config")
                config = json.loads(response["Parameter"]["Value"])
                gateway_id = config.get("gateway_id")

                if gateway_id:
                    self.agentcore.delete_gateway(gatewayIdentifier=gateway_id)
                    self._log(f"Deleted Gateway: {gateway_id}")
            except ClientError:
                pass

            # IAM 역할 및 정책 삭제
            try:
                self.iam.delete_role_policy(RoleName=GATEWAY_ROLE_NAME, PolicyName=GATEWAY_POLICY_NAME)
                self._log(f"Deleted role policy: {GATEWAY_POLICY_NAME}")
            except ClientError:
                pass

            try:
                self.iam.delete_role(RoleName=GATEWAY_ROLE_NAME)
                self._log(f"Deleted IAM role: {GATEWAY_ROLE_NAME}")
            except ClientError:
                pass

            # Parameter Store 항목 삭제
            try:
                self.ssm.delete_parameter(Name=f"/{self.prefix}/lab-04/gateway-role-arn")
                self._log("Deleted Parameter Store entry: gateway-role-arn")
            except ClientError:
                pass

            try:
                self.ssm.delete_parameter(Name=f"/{self.prefix}/lab-04/gateway-config")
                self._log("Deleted Parameter Store entry: gateway-config")
            except ClientError:
                pass

            try:
                self.ssm.delete_parameter(Name=f"/{self.prefix}/lab-04/gateway-runtime-target")
                self._log("Deleted Parameter Store entry: gateway-runtime-target")
            except ClientError:
                pass

            self._log("Gateway cleanup completed")
            return True

        except Exception as e:
            self._error(f"Cleanup failed: {e}")
            raise
