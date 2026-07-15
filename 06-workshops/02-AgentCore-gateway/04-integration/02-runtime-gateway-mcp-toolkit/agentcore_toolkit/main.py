#!/usr/bin/env python3
"""
AgentCore Gateway 및 Runtime 설정 툴킷
YAML 구성을 사용해 AgentCore Runtime과 Gateway를 생성하는 구성 가능한 설정 스크립트입니다.
"""

import os
import boto3
import logging
import json
import stat
from pathlib import Path
from bedrock_agentcore_starter_toolkit import Runtime

from . import utils


class AgentCoreToolkit:
    def __init__(self, config=None):
        if config is None:
            raise ValueError("Configuration is required")

        self.config = config

        try:
            self.region = os.environ.get("AWS_DEFAULT_REGION", self.config["aws"]["region"])
        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid configuration: missing 'aws.region' field: {e}")

        self._setup_logging()

    def _derive_gateway_names(self, gateway_name):
        """Gateway 이름에서 모든 Gateway 관련 이름을 파생합니다."""
        return {
            "iam_role_name": f"{gateway_name}-role",
            "user_pool_name": f"{gateway_name}-pool",
            "resource_server_id": f"{gateway_name}-id",
            "resource_server_name": f"{gateway_name}-name",
            "client_name": f"{gateway_name}-client",
        }

    def _derive_runtime_names(self, runtime_name):
        """Runtime 이름에서 모든 Runtime 관련 이름을 파생합니다."""
        return {
            "user_pool_name": f"{runtime_name}-pool",
            "resource_server_id": f"{runtime_name}-id",
            "resource_server_name": f"{runtime_name}-name",
            "client_name": f"{runtime_name}-client",
            "agent_name": runtime_name.replace("-", "_"),
        }

    def _derive_target_names(self, runtime_name):
        """Runtime 이름에서 대상 관련 이름을 파생합니다."""
        return {
            "name": f"{runtime_name}-target",
            "identity_provider_name": f"{runtime_name}-identity",
        }

    def _setup_logging(self):
        """로깅을 구성합니다."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            handlers=[logging.StreamHandler()],
        )
        logging.getLogger("strands").setLevel(logging.INFO)

    def _validate_runtime_config(self, runtime_config):
        """보안을 위해 Runtime 구성을 검증합니다."""
        required_fields = ["name", "entrypoint", "requirements_file"]
        for field in required_fields:
            if field not in runtime_config:
                raise ValueError(f"Missing required field: {field}")

        # 파일 경로 검증
        entrypoint = runtime_config["entrypoint"]
        requirements_file = runtime_config["requirements_file"]

        # 경로 탐색 시도 확인
        if ".." in entrypoint or ".." in requirements_file:
            raise ValueError("Path traversal detected in file paths")

        # 파일 확장자 검증
        if not entrypoint.endswith(".py"):
            raise ValueError("Entrypoint must be a Python file (.py)")
        if not requirements_file.endswith(".txt"):
            raise ValueError("Requirements file must be a .txt file")

    def setup_gateway_cognito(self):
        """Gateway용 Cognito 리소스를 설정합니다."""
        print("Setting up Gateway Cognito resources...")

        try:
            cognito = boto3.client("cognito-idp", region_name=self.region)
        except Exception as e:
            raise RuntimeError(f"Failed to create Cognito client: {e}")

        try:
            gw_config = self.config["gateway"]
            gateway_name = gw_config["name"]
        except KeyError as e:
            raise ValueError(f"Missing required gateway configuration: {e}")

        # Gateway 이름에서 이름 파생
        derived_names = self._derive_gateway_names(gateway_name)

        try:
            # User Pool 생성
            gw_user_pool_id = utils.get_or_create_user_pool(cognito, derived_names["user_pool_name"])
            print(f"Gateway User Pool ID: {gw_user_pool_id}")

            # 리소스 서버 생성
            if "scopes" not in self.config:
                raise ValueError("Missing required 'scopes' configuration")

            scopes = [
                {"ScopeName": scope["name"], "ScopeDescription": scope["description"]}
                for scope in self.config["scopes"]
            ]
            utils.get_or_create_resource_server(
                cognito,
                gw_user_pool_id,
                derived_names["resource_server_id"],
                derived_names["resource_server_name"],
                scopes,
            )

            # 클라이언트 생성
            scope_names = [f"{derived_names['resource_server_id']}/{scope['name']}" for scope in self.config["scopes"]]
            gw_client_id, gw_client_secret = utils.get_or_create_m2m_client(
                cognito,
                gw_user_pool_id,
                derived_names["client_name"],
                derived_names["resource_server_id"],
                scope_names,
            )

        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid configuration structure: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to setup gateway Cognito resources: {e}")

        gw_discovery_url = (
            f"https://cognito-idp.{self.region}.amazonaws.com/{gw_user_pool_id}/.well-known/openid-configuration"
        )

        return {
            "user_pool_id": gw_user_pool_id,
            "client_id": gw_client_id,
            "client_secret": gw_client_secret,
            "discovery_url": gw_discovery_url,
            "scope_string": " ".join(scope_names),
            "resource_server_id": derived_names["resource_server_id"],
        }

    def setup_runtime_cognito(self, runtime_config):
        """단일 Runtime용 Cognito 리소스를 설정합니다."""
        print(f"Setting up Runtime Cognito resources for {runtime_config['name']}...")

        try:
            cognito = boto3.client("cognito-idp", region_name=self.region)
        except Exception as e:
            raise RuntimeError(f"Failed to create Cognito client: {e}")

        try:
            runtime_name = runtime_config["name"]
        except KeyError as e:
            raise ValueError(f"Missing required runtime configuration: {e}")

        # Runtime 이름에서 이름 파생
        derived_names = self._derive_runtime_names(runtime_name)

        try:
            # User Pool 생성
            rt_user_pool_id = utils.get_or_create_user_pool(cognito, derived_names["user_pool_name"])
            print(f"Runtime User Pool ID: {rt_user_pool_id}")

            # 리소스 서버 생성
            if "scopes" not in self.config:
                raise ValueError("Missing required 'scopes' configuration")

            scopes = [
                {"ScopeName": scope["name"], "ScopeDescription": scope["description"]}
                for scope in self.config["scopes"]
            ]
            utils.get_or_create_resource_server(
                cognito,
                rt_user_pool_id,
                derived_names["resource_server_id"],
                derived_names["resource_server_name"],
                scopes,
            )

            # 클라이언트 생성
            scope_names = [f"{derived_names['resource_server_id']}/{scope['name']}" for scope in self.config["scopes"]]
            rt_client_id, rt_client_secret = utils.get_or_create_m2m_client(
                cognito,
                rt_user_pool_id,
                derived_names["client_name"],
                derived_names["resource_server_id"],
                scope_names,
            )

        except (KeyError, TypeError) as e:
            raise ValueError(f"Invalid configuration structure: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to setup runtime Cognito resources: {e}")

        rt_discovery_url = (
            f"https://cognito-idp.{self.region}.amazonaws.com/{rt_user_pool_id}/.well-known/openid-configuration"
        )

        return {
            "user_pool_id": rt_user_pool_id,
            "client_id": rt_client_id,
            "client_secret": rt_client_secret,
            "discovery_url": rt_discovery_url,
            "scope_string": " ".join(scope_names),
        }

    def create_gateway(self, gateway_cognito):
        """AgentCore Gateway를 생성합니다."""
        print("Creating AgentCore Gateway...")

        try:
            gw_config = self.config["gateway"]
            derived_names = self._derive_gateway_names(gw_config["name"])
        except KeyError as e:
            raise ValueError(f"Missing required gateway configuration: {e}")

        try:
            # IAM 역할 생성
            iam_role = utils.create_agentcore_gateway_role(derived_names["iam_role_name"], region=self.region)
            print(f"Gateway IAM Role ARN: {iam_role['Role']['Arn']}")

            auth_config = {
                "customJWTAuthorizer": {
                    "allowedClients": [gateway_cognito["client_id"]],
                    "discoveryUrl": gateway_cognito["discovery_url"],
                }
            }

            gw_info = utils.get_or_create_agentcore_gateway(self.region, iam_role, auth_config, gw_config)
            return gw_info
        except Exception as e:
            raise RuntimeError(f"Failed to create gateway: {e}")

    def _create_auth_config(self, cognito_info):
        """인증 구성을 생성합니다."""
        return {
            "customJWTAuthorizer": {
                "allowedClients": [cognito_info["client_id"]],
                "discoveryUrl": cognito_info["discovery_url"],
            }
        }

    def _configure_runtime(self, runtime_config, auth_config, agent_name):
        """제공된 설정으로 AgentCore Runtime을 구성합니다."""
        try:
            # 이 Runtime용으로 다시 생성되도록 공유 Dockerfile 제거
            dockerfile_path = Path.cwd() / "Dockerfile"
            if dockerfile_path.exists():
                dockerfile_path.unlink()

            agentcore_runtime = Runtime()

            agentcore_runtime.configure(
                entrypoint=runtime_config["entrypoint"],
                auto_create_execution_role=runtime_config.get("auto_create_execution_role", True),
                auto_create_ecr=runtime_config.get("auto_create_ecr", True),
                requirements_file=runtime_config["requirements_file"],
                region=self.region,
                authorizer_configuration=auth_config,
                protocol=runtime_config.get("protocol", "MCP"),
                agent_name=agent_name,
            )
            return agentcore_runtime
        except Exception as e:
            raise RuntimeError(f"Failed to configure runtime: {e}")

    def _launch_runtime(self, agentcore_runtime, runtime_name):
        """구성된 Runtime을 시작하고 연결 정보를 반환합니다."""
        print(f"Launching MCP server {runtime_name} to AgentCore Runtime...")
        launch_result = agentcore_runtime.launch(auto_update_on_conflict=True)

        agent_arn = launch_result.agent_arn
        encoded_arn = agent_arn.replace(":", "%3A").replace("/", "%2F")
        agent_url = f"https://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"

        print(f"Agent ARN: {agent_arn}")
        return {"agent_arn": agent_arn, "agent_url": agent_url}

    def setup_runtime(self, runtime_config, runtime_cognito):
        """AgentCore Runtime을 설정하고 시작합니다."""
        print(f"Setting up AgentCore Runtime for {runtime_config['name']}...")

        # Runtime 이름에서 에이전트 이름 파생
        derived_names = self._derive_runtime_names(runtime_config["name"])

        # 인증 구성 생성
        auth_config = self._create_auth_config(runtime_cognito)

        # Runtime 구성
        agentcore_runtime = self._configure_runtime(runtime_config, auth_config, derived_names["agent_name"])

        # Runtime을 시작하고 연결 정보 반환
        return self._launch_runtime(agentcore_runtime, runtime_config["name"])

    def _create_target_params(self, gateway_info, runtime_info, runtime_cognito, target_config, provider_arn):
        """대상 생성 매개변수를 생성합니다."""
        return {
            "gateway_id": gateway_info["gateway_id"],
            "agent_url": runtime_info["agent_url"],
            "scope_string": runtime_cognito["scope_string"],
            "name": target_config["name"],
            "cognito_provider_arn": provider_arn,
        }

    def create_gateway_target(self, gateway_info, runtime_info, runtime_cognito, target_config):
        """Gateway 대상을 생성하고 인증을 구성합니다."""
        print("Creating Oauth Credential Provider")
        cognito_provider_arn = utils.get_or_create_oauth2_credential_provider(
            self.region, target_config["identity_provider_name"], runtime_cognito
        )

        print(f"Creating gateway target {target_config['name']}...")
        target_params = self._create_target_params(
            gateway_info,
            runtime_info,
            runtime_cognito,
            target_config,
            cognito_provider_arn,
        )

        return utils.get_or_create_agentcore_gateway_target(self.region, target_params)

    def run(self):
        """전체 설정 프로세스를 실행합니다."""
        print("Starting AgentCore Gateway and Runtime setup...")

        # Gateway Cognito 리소스 설정
        gateway_cognito = self.setup_gateway_cognito()

        # Gateway 생성
        gateway_info = self.create_gateway(gateway_cognito)

        # 여러 Runtime 및 대상 처리
        runtime_infos = []
        for runtime_config in self.config["runtime"]:
            # Runtime Cognito 리소스 설정
            runtime_cognito = self.setup_runtime_cognito(runtime_config)

            # Runtime 설정
            runtime_info = self.setup_runtime(runtime_config, runtime_cognito)
            runtime_infos.append(runtime_info)

            # Runtime 이름에서 대상 구성 파생
            target_config = self._derive_target_names(runtime_config["name"])
            self.create_gateway_target(gateway_info, runtime_info, runtime_cognito, target_config)

        # Gateway 연결 정보 표시
        gateway_info_result = self.display_gateway_info(gateway_info["gateway_id"], gateway_cognito)
        print("\n✅ Setup completed successfully!")
        return gateway_info_result

    def _write_credentials_to_file(self, gateway_cognito, access_token, gateway_url):
        """제한된 권한으로 자격 증명을 보안 파일에 씁니다."""
        creds_file = f".agentcore-credentials-{self.config['gateway']['name']}.json"

        credentials = {
            "gateway_url": gateway_url,
            "user_pool_id": gateway_cognito["user_pool_id"],
            "client_id": gateway_cognito["client_id"],
            "client_secret": gateway_cognito["client_secret"],
            "access_token": access_token,
        }

        try:
            with open(creds_file, "w") as f:
                json.dump(credentials, f, indent=2)

            # 파일 권한을 소유자 읽기/쓰기로만 설정(600)
            os.chmod(creds_file, stat.S_IRUSR | stat.S_IWUSR)

            print(f"Credentials saved to: {creds_file}")
            print("File permissions set to owner-only access (600)")
            print(f"Use: cat {creds_file}")

        except (OSError, IOError) as e:
            print(f"Warning: Could not write credentials file: {e}")
            print("Credentials will be displayed in console (less secure)")
            return False

        return True

    def display_gateway_info(self, gateway_id, gateway_cognito):
        """Gateway 연결 정보를 표시합니다."""
        print("\n" + "=" * 60)
        print("GATEWAY CONNECTION INFORMATION")
        print("=" * 60)

        # Gateway URL 가져오기
        gateway_url = f"https://{gateway_id}.gateway.bedrock-agentcore.{self.config['aws']['region']}.amazonaws.com/mcp"
        # 액세스 토큰 가져오기
        access_token = self._get_access_token(gateway_cognito)
        # 보안 파일에 자격 증명 쓰기 시도
        self._write_credentials_to_file(gateway_cognito, access_token, gateway_url)
        print("=" * 60)

        return {
            "gateway_url": gateway_url,
            "user_pool_id": gateway_cognito["user_pool_id"],
            "client_id": gateway_cognito["client_id"],
            "client_secret": gateway_cognito["client_secret"],
            "access_token": access_token,
        }

    def _get_access_token(self, gateway_cognito):
        """client credentials 흐름으로 액세스 토큰을 가져옵니다."""
        try:
            # scope 구성 가져오기
            scope_names = [
                f"{gateway_cognito['resource_server_id']}/{scope['name']}" for scope in self.config["scopes"]
            ]
            scope_string = " ".join(scope_names)

            # utils를 사용해 토큰 가져오기
            token_response = utils.get_token(
                gateway_cognito["user_pool_id"],
                gateway_cognito["client_id"],
                gateway_cognito["client_secret"],
                scope_string,
                self.config["aws"]["region"],
            )

            if "error" in token_response:
                print(f"Warning: Token request failed: {token_response['error']}")
                return None

            return token_response.get("access_token")  # codeql[py/clear-text-logging-sensitive-data]

        except KeyError as e:
            print(f"Warning: Missing required field in token response: {e}")
            return None
        except Exception as e:
            print(f"Warning: Could not retrieve access token: {e}")
            return None


def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="AgentCore Gateway and Runtime Setup Toolkit")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--gateway-name", required=True, help="Gateway name")
    parser.add_argument("--gateway-description", help="Gateway description")
    parser.add_argument(
        "--runtime-configs",
        required=True,
        help='JSON string of runtime configurations: [{"name":"runtime1","description":"desc","entrypoint":"path","requirements_file":"path"}]',
    )

    args = parser.parse_args()

    # JSON에서 Runtime 구성 파싱
    try:
        runtime_configs = json.loads(args.runtime_configs)

        # Runtime 구성 구조 검증
        if not isinstance(runtime_configs, list):
            raise ValueError("Runtime configs must be a JSON array")

        if not runtime_configs:
            raise ValueError("At least one runtime configuration is required")

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format for --runtime-configs: {e}")
        return 1
    except ValueError as e:
        print(f"Error: {e}")
        return 1

    # 하드코딩된 scope로 구성 구조 생성
    config = {
        "aws": {"region": args.region},
        "gateway": {
            "name": args.gateway_name,
            "description": args.gateway_description or f"{args.gateway_name} Gateway",
        },
        "runtime": runtime_configs,
        "scopes": [
            {
                "name": "invoke",
                "description": "Scope for invoking the agentcore gateway",
            }
        ],
    }

    try:
        toolkit = AgentCoreToolkit(config)
        toolkit.run()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1
    except ValueError as e:
        print(f"Error: {e}")
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    main()
