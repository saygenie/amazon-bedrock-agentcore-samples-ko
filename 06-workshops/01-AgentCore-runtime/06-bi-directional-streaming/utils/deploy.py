#!/usr/bin/env python3
"""
Starter Toolkit을 사용하는 Amazon Bedrock AgentCore 배포 스크립트

bedrock-agentcore-starter-toolkit을 사용하는
Python 기반 배포 스크립트입니다.

사용법:
    python deploy.py <websocket-folder> [options]

예시:
    python deploy.py 01-bedrock-sonic-ws
    python deploy.py 02-strands-ws --region us-west-2
    python deploy.py 03-langchain-transcribe-polly-ws --agent-name my-langchain-agent
    python deploy.py 01-bedrock-sonic-ws --agent-name my-sonic-agent
"""

import argparse
import json
import os
import sys
import subprocess
import shutil
import time
import traceback
import yaml
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional

import boto3
from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
from bedrock_agentcore_starter_toolkit.operations.runtime.launch import (
    launch_bedrock_agentcore,
)


class Colors:
    """터미널 출력용 ANSI 색상 코드입니다."""

    GREEN = "\033[0;32m"
    BLUE = "\033[0;34m"
    YELLOW = "\033[1;33m"
    RED = "\033[0;31m"
    NC = "\033[0m"  # 색상 없음


class AgentCoreDeployer:
    """Amazon Bedrock AgentCore Runtime으로의 에이전트 배포를 처리합니다."""

    def __init__(self, websocket_folder: str, args: argparse.Namespace):
        self.websocket_folder = websocket_folder
        self.args = args

        # 프로젝트 루트 디렉터리를 기준으로 경로 확인
        self.base_dir = Path(__file__).parent.parent

        # 폴더 존재 여부 검증
        self.websocket_path = self.base_dir / websocket_folder / "websocket"
        if not self.websocket_path.exists():
            self._error(f"Websocket folder not found: {self.websocket_path}")
            sys.exit(1)

        # 구성 설정
        self.aws_region = args.region or os.getenv("AWS_REGION", "us-east-1")
        self.account_id = args.account_id or os.getenv("ACCOUNT_ID")
        self.agent_name = args.agent_name or f"bidi_{websocket_folder.replace('-', '_')}_agent"

        if not self.account_id:
            self._error("ACCOUNT_ID is required. Set via --account-id or ACCOUNT_ID environment variable")
            sys.exit(1)

        self.config_file = self.base_dir / websocket_folder / "setup_config.json"

    def _print(self, message: str, color: str = Colors.NC):
        """색상이 적용된 메시지를 출력합니다."""
        print(f"{color}{message}{Colors.NC}")

    def _error(self, message: str):
        """오류 메시지를 출력합니다."""
        self._print(f"❌ {message}", Colors.RED)

    def _success(self, message: str):
        """성공 메시지를 출력합니다."""
        self._print(f"✅ {message}", Colors.GREEN)

    def _info(self, message: str):
        """정보 메시지를 출력합니다."""
        self._print(f"ℹ️  {message}", Colors.BLUE)

    def _warning(self, message: str):
        """경고 메시지를 출력합니다."""
        self._print(f"⚠️  {message}", Colors.YELLOW)

    def _run_command(self, cmd: list, cwd: Optional[Path] = None, check: bool = True) -> subprocess.CompletedProcess:
        """Shell 명령을 실행하고 결과를 반환합니다."""
        try:
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)
            return result
        except subprocess.CalledProcessError as e:
            self._error(f"Command failed: {' '.join(cmd)}")
            self._error(f"Error: {e.stderr}")
            if check:
                raise
            return e

    def create_memory(self) -> Optional[Dict]:
        """Strands 에이전트용 AgentCore Memory 리소스를 생성합니다."""
        if self.websocket_folder != "02-strands-ws":
            return None

        self._print("\n🧠 Creating AgentCore Memory...", Colors.YELLOW)

        try:
            from bedrock_agentcore.memory import MemoryClient

            client = MemoryClient(region_name=self.aws_region)

            memory_name = f"{self.agent_name}_memory"

            # 목록에서 이름을 대조하여 Memory가 이미 존재하는지 확인
            try:
                existing = client.list_memories()
                for mem in existing.get("memories", []):
                    if mem.get("name") == memory_name:
                        memory_id = mem["id"]
                        self._info(f"Found existing memory: {memory_name} (ID: {memory_id})")
                        return {"memory_id": memory_id, "memory_name": memory_name}
            except Exception:
                pass  # 목록 조회가 지원되지 않거나 비어 있을 수 있으므로 생성 진행

            memory = client.create_memory(
                name=memory_name,
                description=f"Chat history for {self.agent_name}",
            )

            memory_id = memory.get("id")
            self._success(f"Memory created: {memory_name} (ID: {memory_id})")

            return {"memory_id": memory_id, "memory_name": memory_name}

        except ImportError:
            self._warning("bedrock-agentcore package not installed, skipping memory creation")
            self._info("Install with: pip install bedrock-agentcore")
            return None
        except Exception as e:
            self._warning(f"Failed to create memory: {e}")
            self._info("You can create memory manually and set MEMORY_ID env var")
            return None

    def deploy_mcp_gateway(self) -> Optional[Dict]:
        """MCP 도구를 사용하는 Strands 및 LangChain 에이전트용 MCP Gateway를 배포합니다."""
        if self.websocket_folder not in (
            "02-strands-ws",
            "03-langchain-transcribe-polly-ws",
        ):
            return None

        self._print("\n🌐 Deploying MCP Gateways...", Colors.YELLOW)

        # Gateway 클라이언트 초기화
        client = GatewayClient(region_name=self.aws_region)
        bedrock_client = boto3.client("bedrock-agentcore-control", region_name=self.aws_region)

        # 생성할 Gateway 4개 정의
        gateway_configs = [
            {
                "name": "auth-tools",
                "mcp_server": "auth-tools-mcp",
                "tools": ["authenticate_user", "verify_identity"],
            },
            {
                "name": "banking-tools",
                "mcp_server": "banking-tools-mcp",
                "tools": [
                    "get_account_balance",
                    "get_recent_transactions",
                    "transfer_funds",
                    "get_account_summary",
                ],
            },
            {
                "name": "mortgage-tools",
                "mcp_server": "mortgage-tools-mcp",
                "tools": [
                    "get_mortgage_rates",
                    "calculate_mortgage_payment",
                    "check_mortgage_eligibility",
                    "get_mortgage_application_status",
                ],
            },
            {
                "name": "faq-kb-tools",
                "mcp_server": "anybank-faq-kb",
                "tools": ["search_anybank_faq", "answer_anybank_question"],
            },
        ]

        deployed_gateways = []

        for gw_config in gateway_configs:
            gateway_name = gw_config["name"]
            self._print(f"\n📦 Deploying {gateway_name} gateway...", Colors.BLUE)

            gateway = None

            # Gateway가 이미 존재하는지 확인
            try:
                response = bedrock_client.list_gateways()
                for gw in response.get("items", []):
                    if gw.get("name") == gateway_name:
                        self._info(f"Found existing gateway: {gateway_name} (ID: {gw['gatewayId']})")
                        gateway_detail = bedrock_client.get_gateway(gatewayIdentifier=gw["gatewayId"])
                        gateway = gateway_detail
                        break
            except Exception as e:
                self._warning(f"Could not check for existing gateway: {e}")

            # MCP Gateway가 없으면 생성
            if not gateway:
                self._info(f"Creating {gateway_name} gateway...")
                try:
                    gateway = client.create_mcp_gateway(name=gateway_name)
                except Exception as e:
                    error_msg = str(e)
                    if "already exists" in error_msg.lower() or "conflict" in error_msg.lower():
                        self._warning(f"Gateway {gateway_name} already exists, fetching...")
                        response = bedrock_client.list_gateways()
                        for gw in response.get("items", []):
                            if gw.get("name") == gateway_name:
                                gateway_detail = bedrock_client.get_gateway(gatewayIdentifier=gw["gatewayId"])
                                gateway = gateway_detail
                                self._success(f"Retrieved existing gateway: {gw['gatewayId']}")
                                break
                        if not gateway:
                            raise Exception(f"Gateway '{gateway_name}' exists but could not be found")
                    else:
                        raise

            gateway_arn = gateway["gatewayArn"]
            gateway_url = gateway["gatewayUrl"]
            role_arn = gateway["roleArn"]
            gateway_id = gateway["gatewayId"]

            self._success(f"Gateway ready: {gateway_id}")
            self._info(f"   URL: {gateway_url}")

            # MCP Server 대상 생성
            self._info(f"Creating MCP Server Target for {gw_config['mcp_server']}...")

            try:
                target = client.create_mcp_gateway_target(
                    gateway=gateway,
                    name=gw_config["mcp_server"],
                    target_type="lambda",
                    target_payload=None,
                )
                self._success(f"MCP Server target created: {target['targetId']}")
            except Exception as e:
                if "already exists" in str(e).lower() or "conflict" in str(e).lower():
                    self._warning(f"MCP Server target already exists for {gateway_name}, continuing...")
                    targets_response = bedrock_client.list_gateway_targets(gatewayIdentifier=gateway_id)
                    target = targets_response.get("items", [{}])[0] if targets_response.get("items") else {}
                else:
                    raise

            # Gateway 정보 저장
            deployed_gateways.append(
                {
                    "gateway_name": gateway_name,
                    "gateway_id": gateway_id,
                    "gateway_arn": gateway_arn,
                    "gateway_url": gateway_url,
                    "role_arn": role_arn,
                    "target_id": target.get("targetId", "unknown"),
                    "mcp_server_name": gw_config["mcp_server"],
                    "tools": gw_config["tools"],
                }
            )

        # Gateway 구성 저장
        gateway_config = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "deployment_type": "mcp-gateway",
            "gateways": deployed_gateways,
            "aws": {"account_id": self.account_id, "region": self.aws_region},
        }

        config_path = self.base_dir / self.websocket_folder / "gateway_config.json"
        with open(config_path, "w") as f:
            json.dump(gateway_config, f, indent=2)

        self._success(f"Gateway configuration saved to {config_path}")
        self._info(f"   Deployed {len(deployed_gateways)} gateways")

        return {"gateways": deployed_gateways}

    def check_prerequisites(self):
        """필수 도구 설치 여부를 확인합니다."""
        self._print("\n📋 Checking prerequisites...", Colors.YELLOW)

        required_tools = {
            "python3": "Python 3.10+",
            "aws": "AWS CLI",
            "agentcore": "bedrock-agentcore-starter-toolkit",
        }

        missing_tools = []

        for tool, description in required_tools.items():
            if not shutil.which(tool):
                missing_tools.append(f"{tool} ({description})")

        if missing_tools:
            self._error("Missing required tools:")
            for tool in missing_tools:
                print(f"  - {tool}")
            print("\nInstall missing tools:")
            print("  pip install bedrock-agentcore-starter-toolkit")
            sys.exit(1)

        self._success("All prerequisites met")

    def setup_agentcore_project(self):
        """AgentCore 프로젝트 구조를 설정합니다."""
        self._print("\n📦 Setting up AgentCore project...", Colors.YELLOW)

        # .bedrock_agentcore.yaml 구성 생성
        config = {
            "agent_name": self.agent_name,
            "region": self.aws_region,
            "entry_point": "server.py",
            "runtime": "python3.12",
            "bedrock_agentcore": {
                "agent_runtime_name": self.agent_name,
                "network_mode": "PUBLIC",
            },
        }

        config_path = self.websocket_path / ".bedrock_agentcore.yaml"

        # 구성 기록
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False)

        self._success(f"Created AgentCore configuration: {config_path}")

    def create_iam_role(self) -> str:
        """에이전트용 IAM 역할을 생성합니다."""
        self._print("\n🔐 Creating IAM role...", Colors.YELLOW)

        role_name = f"WebSocket{self.websocket_folder.capitalize()}AgentRole"

        # 생성 및 업데이트 경로 모두에서 사용할 수 있도록 정책 파일을 미리 읽기
        deploy_dir = Path(__file__).parent
        agent_role_path = deploy_dir / "agent_role.json"
        trust_policy_path = deploy_dir / "trust_policy.json"

        if not agent_role_path.exists() or not trust_policy_path.exists():
            self._error("Policy files not found (agent_role.json, trust_policy.json)")
            sys.exit(1)

        # 역할 존재 여부 확인
        check_cmd = ["aws", "iam", "get-role", "--role-name", role_name]
        result = self._run_command(check_cmd, check=False)

        if result.returncode == 0:
            role_data = json.loads(result.stdout)
            role_arn = role_data["Role"]["Arn"]
            self._info(f"IAM role {role_name} already exists")

            # 최신 권한이 적용되도록 항상 정책 업데이트
            with open(agent_role_path, "r") as f:
                agent_role_policy = f.read().replace("${ACCOUNT_ID}", self.account_id)

            put_policy_cmd = [
                "aws",
                "iam",
                "put-role-policy",
                "--role-name",
                role_name,
                "--policy-name",
                f"{role_name}Policy",
                "--policy-document",
                agent_role_policy,
            ]
            self._run_command(put_policy_cmd)
            self._success(f"Updated policy on existing role: {role_arn}")
            return role_arn

        # agent_role.json을 읽고 ACCOUNT_ID 치환
        with open(agent_role_path, "r") as f:
            agent_role_policy = f.read().replace("${ACCOUNT_ID}", self.account_id)

        # 역할 생성
        create_role_cmd = [
            "aws",
            "iam",
            "create-role",
            "--role-name",
            role_name,
            "--assume-role-policy-document",
            f"file://{trust_policy_path}",
            "--output",
            "json",
        ]

        result = self._run_command(create_role_cmd)
        self._success("Role created")

        # 정책 연결
        put_policy_cmd = [
            "aws",
            "iam",
            "put-role-policy",
            "--role-name",
            role_name,
            "--policy-name",
            f"{role_name}Policy",
            "--policy-document",
            agent_role_policy,
        ]

        self._run_command(put_policy_cmd)
        self._success("Policy attached")

        # 역할 ARN 가져오기
        result = self._run_command(["aws", "iam", "get-role", "--role-name", role_name, "--output", "json"])
        role_data = json.loads(result.stdout)
        role_arn = role_data["Role"]["Arn"]

        self._success(f"IAM role created: {role_arn}")

        # IAM 반영 대기
        self._info("Waiting 10 seconds for IAM role to propagate...")
        time.sleep(10)

        return role_arn

    def deploy_agent(
        self,
        role_arn: str,
        gateway_info: Optional[Dict] = None,
        memory_info: Optional[Dict] = None,
    ) -> Dict:
        """starter toolkit을 사용해 에이전트를 배포합니다."""
        self._print("\n🚀 Deploying agent to AgentCore Runtime...", Colors.YELLOW)

        # WebSocket 디렉터리로 이동
        original_dir = Path.cwd()
        os.chdir(self.websocket_path)

        try:
            # 먼저 기존 구성 파일 제거
            config_path = Path(".bedrock_agentcore.yaml")
            if config_path.exists():
                self._info("Removing existing configuration...")
                config_path.unlink()

            # .bedrock_agentcore.yaml 구성 파일 직접 생성
            self._info("Creating AgentCore configuration...")

            # toolkit은 에이전트 정의가 포함된 'agents' 섹션을 요구함
            # SDK가 리포지토리를 생성하고 전체 URI를 가져오도록 ecr_auto_create 사용
            config = {
                "agents": {
                    self.agent_name: {
                        "name": self.agent_name,
                        "entrypoint": "server.py",
                        "runtime": "python3.12",
                        "aws": {
                            "account": self.account_id,
                            "region": self.aws_region,
                            "execution_role": role_arn,
                            "ecr_auto_create": True,
                        },
                    }
                },
                "default_agent": self.agent_name,
                "region": self.aws_region,
            }

            # 환경 변수 준비
            env_vars = {}

            # 사용 가능한 경우 MCP Gateway 환경 변수 추가(Strands 및 LangChain용)
            if self.websocket_folder in ("02-strands-ws", "03-langchain-transcribe-polly-ws") and gateway_info:
                gateways = gateway_info.get("gateways", [])

                if gateways:
                    # 모든 Gateway ARN과 URL을 JSON 인코딩된 환경 변수로 전달
                    gateway_arns = [gw["gateway_arn"] for gw in gateways]
                    gateway_urls = [gw["gateway_url"] for gw in gateways]

                    env_vars["MCP_GATEWAY_ARNS"] = json.dumps(gateway_arns)
                    env_vars["MCP_GATEWAY_URLS"] = json.dumps(gateway_urls)

                    self._info(f"Added MCP Gateway environment variables for {len(gateways)} gateways")
                    for gw in gateways:
                        self._info(f"   {gw['gateway_name']}: {gw['gateway_url']}")

            # 사용 가능한 경우 AgentCore Memory 환경 변수 추가(Strands용)
            if memory_info and memory_info.get("memory_id"):
                env_vars["MEMORY_ID"] = memory_info["memory_id"]
                env_vars["MEMORY_REGION"] = self.aws_region
                self._info(f"Added MEMORY_ID={memory_info['memory_id']} to environment")

            # .env 파일에 Pipecat 전용 환경 변수가 있으면 추가
            if self.websocket_folder == "04-pipecat-sonic-ws":
                env_file = self.websocket_path / ".env"
                if env_file.exists():
                    self._info("Loading Pipecat environment variables from .env file...")
                    with open(env_file) as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith("#") and "=" in line:
                                key, _, value = line.partition("=")
                                key, value = key.strip(), value.strip()
                                if value:
                                    env_vars[key] = value
                                    self._info(f"   {key}: ***configured***")

            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)

            self._success(f"Configuration created: {config_path}")

            # 배포 모드 결정
            local = self.args.local
            use_codebuild = not self.args.local_build

            if local:
                self._info("Deploying with local mode (requires Docker)")
            elif not use_codebuild:
                self._info("Deploying with local build mode (requires Docker)")
            else:
                self._info("Deploying with CodeBuild (no Docker required)")

            self._info("Launching agent (this may take a few minutes)...")

            # starter toolkit을 사용해 시작
            result = launch_bedrock_agentcore(
                config_path=config_path,
                agent_name=self.agent_name,
                local=local,
                use_codebuild=use_codebuild,
                env_vars=env_vars,
                auto_update_on_conflict=True,
            )

            # 결과에서 에이전트 정보 추출
            agent_arn = result.agent_arn
            agent_id = result.agent_id

            if not agent_arn:
                raise RuntimeError("Failed to get agent ARN from deployment result")

            self._success("Agent deployed successfully!")
            self._info(f"   Agent ARN: {agent_arn}")
            self._info(f"   Agent ID: {agent_id}")

            return {
                "agent_arn": agent_arn,
                "agent_runtime_name": self.agent_name,
                "role_arn": role_arn,
            }

        finally:
            os.chdir(original_dir)

    def save_configuration(self, deployment_info: Dict):
        """배포 구성을 JSON 파일에 저장합니다."""
        self._print("\n💾 Saving configuration...", Colors.YELLOW)

        config = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "websocket_folder": self.websocket_folder,
            "aws_region": self.aws_region,
            "account_id": self.account_id,
            "agent_name": self.agent_name,
            "agent_runtime_name": deployment_info["agent_runtime_name"],
            "agent_arn": deployment_info["agent_arn"],
            "iam_role_arn": deployment_info["role_arn"],
            "deployment_method": "agentcore-starter-toolkit",
        }

        # 사용 가능한 경우 Memory 정보 포함
        if "memory" in deployment_info:
            config["memory"] = deployment_info["memory"]

        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)

        self._success(f"Configuration saved to {self.config_file}")

    def print_summary(self, deployment_info: Dict):
        """배포 요약을 출력합니다."""
        self._print("\n" + "=" * 80, Colors.GREEN)
        self._print("✅ Deployment Complete!", Colors.GREEN)
        self._print("=" * 80, Colors.GREEN)

        self._print("\n📊 Configuration Summary", Colors.BLUE)
        self._print("=" * 80, Colors.GREEN)

        print(f"\n{Colors.YELLOW}AWS Configuration:{Colors.NC}")
        print(f"   Account ID:        {self.account_id}")
        print(f"   Region:            {self.aws_region}")

        print(f"\n{Colors.YELLOW}Agent Runtime:{Colors.NC}")
        print(f"   Agent Name:        {deployment_info['agent_runtime_name']}")
        print(f"   Agent ARN:         {deployment_info['agent_arn']}")
        print(f"   IAM Role:          {deployment_info['role_arn']}")

        # 사용 가능한 경우 Gateway 정보 표시(Strands 배포)
        if "gateways" in deployment_info:
            gateways = deployment_info["gateways"]
            print(f"\n{Colors.YELLOW}MCP Gateways ({len(gateways)} deployed):{Colors.NC}")
            for gw in gateways:
                print(f"\n   {gw['gateway_name']}:")
                print(f"      Gateway ID:     {gw['gateway_id']}")
                print(f"      Gateway URL:    {gw['gateway_url']}")
                print(f"      Target ID:      {gw['target_id']}")
                print(f"      Tools:          {', '.join(gw['tools'])}")

        # 사용 가능한 경우 Memory 정보 표시(Strands 배포)
        if "memory" in deployment_info:
            mem = deployment_info["memory"]
            print(f"\n{Colors.YELLOW}AgentCore Memory:{Colors.NC}")
            print(f"   Memory ID:         {mem.get('memory_id', 'N/A')}")
            print(f"   Memory Name:       {mem.get('memory_name', 'N/A')}")

        self._print("\n" + "=" * 80, Colors.GREEN)
        self._print("\n🚀 Next Steps", Colors.BLUE)
        self._print("=" * 80, Colors.GREEN)

        print(f"\n{Colors.YELLOW}1. Start the client:{Colors.NC}")
        print(f"   ./utils/start_client.sh {self.websocket_folder}")

        print(f"\n{Colors.YELLOW}2. Or test with agentcore CLI:{Colors.NC}")
        print('   agentcore invoke "Hello!"')

        print(f"\n{Colors.YELLOW}3. View logs:{Colors.NC}")
        print("   Check CloudWatch Logs in AWS Console")

        print(f"\n{Colors.YELLOW}4. When done, clean up:{Colors.NC}")
        print(f"   python utils/cleanup.py {self.websocket_folder}")

        self._print("\n" + "=" * 80, Colors.GREEN)

    def deploy(self):
        """기본 배포 워크플로입니다."""
        try:
            self._print(f"\n🚀 AgentCore Deployment - {self.websocket_folder}", Colors.BLUE)
            self._print(f"📁 Using websocket folder: {self.websocket_folder}\n", Colors.BLUE)

            # 1단계: 필수 조건 확인
            self.check_prerequisites()

            # 1.5단계: MCP Gateway 배포(Strands 전용)
            gateway_info = self.deploy_mcp_gateway()

            # 1.6단계: AgentCore Memory 생성(Strands 전용)
            memory_info = self.create_memory()

            # 2단계: IAM 역할 생성
            role_arn = self.create_iam_role()

            # 3단계: 에이전트 배포
            deployment_info = self.deploy_agent(role_arn, gateway_info, memory_info)

            # 사용 가능한 경우 배포 정보에 Gateway 정보 추가
            if gateway_info:
                deployment_info["gateway"] = gateway_info

            # 사용 가능한 경우 배포 정보에 Memory 정보 추가
            if memory_info:
                deployment_info["memory"] = memory_info

            # 4단계: 구성 저장
            self.save_configuration(deployment_info)

            # 5단계: 요약 출력
            self.print_summary(deployment_info)

        except KeyboardInterrupt:
            self._error("\nDeployment cancelled by user")
            sys.exit(1)
        except Exception as e:
            self._error(f"Deployment failed: {e}")
            traceback.print_exc()
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Deploy agents to Amazon Bedrock AgentCore Runtime using starter toolkit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python deploy.py 01-bedrock-sonic-ws
  python deploy.py 02-strands-ws --region us-west-2
  python deploy.py 03-langchain-transcribe-polly-ws --agent-name my-langchain-agent
  python deploy.py 01-bedrock-sonic-ws --agent-name my-sonic-agent --local-build

Environment Variables:
  ACCOUNT_ID    AWS Account ID (required if not provided via --account-id)
  AWS_REGION    AWS Region (default: us-east-1)
        """,
    )

    parser.add_argument(
        "websocket_folder",
        choices=[
            "01-bedrock-sonic-ws",
            "02-strands-ws",
            "03-langchain-transcribe-polly-ws",
            "04-pipecat-sonic-ws",
            "echo",
            "webrtc-kvs",
        ],
        help="Websocket folder to deploy",
    )

    parser.add_argument("--account-id", help="AWS Account ID (or set ACCOUNT_ID env var)")

    parser.add_argument("--region", help="AWS Region (default: us-east-1 or AWS_REGION env var)")

    parser.add_argument("--agent-name", help="Custom agent name (default: bidi_<folder>_agent)")

    parser.add_argument("--local", action="store_true", help="Build and run locally (requires Docker)")

    parser.add_argument(
        "--local-build",
        action="store_true",
        help="Build locally, deploy to cloud (requires Docker)",
    )

    args = parser.parse_args()

    # 배포 도구를 생성하여 실행
    deployer = AgentCoreDeployer(args.websocket_folder, args)
    deployer.deploy()


if __name__ == "__main__":
    main()
