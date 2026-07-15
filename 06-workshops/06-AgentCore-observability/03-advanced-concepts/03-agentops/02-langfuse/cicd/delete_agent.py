#!/usr/bin/env python3
"""
CI/CD 파이프라인 정리를 위한 에이전트 삭제 스크립트입니다.
이 스크립트는 utils.agent의 delete_agent 함수를 사용하여 배포된 에이전트를 삭제합니다.
"""

import json
import sys
from pathlib import Path

# utils를 가져올 수 있도록 상위 디렉터리를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

from utils.agent import delete_agent


def load_hp_config(config_path="cicd/hp_config.json"):
    """구성 파일에서 하이퍼파라미터를 로드합니다."""
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"Error: Configuration file {config_path} not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {config_path}: {e}")
        sys.exit(1)


def get_agent_info_from_deploy_result():
    """
    배포 결과에서 에이전트 정보를 가져옵니다.
    실제 CI/CD 시나리오에서는 배포 단계에서 설정된 파일이나 환경 변수에서
    이 정보를 읽습니다.
    """
    # 현재는 구성에서 에이전트 이름을 조합하여 검색
    # 프로덕션 시나리오에서는 에이전트 정보를 파일에 저장하거나
    # 워크플로 단계 사이에서 환경 변수로 전달할 수 있음

    config = load_hp_config()
    model = config["model"]
    system_prompt = config["system_prompt"]
    environment = "TST"

    agent_name = f"strands_{model['name']}_{system_prompt['name']}_{environment}"

    # 에이전트를 찾기 위해 boto3 가져오기
    import boto3
    from boto3.session import Session

    boto_session = Session()
    region = boto_session.region_name

    try:
        agentcore_control_client = boto3.client("bedrock-agentcore-control", region_name=region)

        # 대상 에이전트를 찾기 위해 모든 에이전트 런타임 조회
        list_response = agentcore_control_client.list_agent_runtimes()
        existing_agents = list_response.get("agentRuntimes", [])

        # 지정한 이름의 에이전트 찾기
        target_agent = None
        for agent_summary in existing_agents:
            if agent_summary.get("agentRuntimeName") == agent_name:
                target_agent = agent_summary
                break

        if not target_agent:
            print(f"Warning: Agent '{agent_name}' not found. It may have already been deleted.")
            return None

        # ECR URI를 추출하기 위해 에이전트 런타임의 전체 세부 정보 가져오기
        agent_runtime_id = target_agent.get("agentRuntimeId")

        print(f"Agent Runtime ID: {agent_runtime_id}")

        try:
            get_response = agentcore_control_client.get_agent_runtime(agentRuntimeId=agent_runtime_id)

            print(f"Get Response: {get_response}")

            ecr_uri = get_response["agentRuntimeArtifact"]["containerConfiguration"]["containerUri"]

            print(f"ECR URI: {ecr_uri}")
        except Exception as e:
            print(f"Warning: Could not retrieve ECR URI: {str(e)}")
            ecr_uri = ""

        return {
            "agent_runtime_id": agent_runtime_id,
            "ecr_uri": ecr_uri,
            "agent_name": agent_name,
        }

    except Exception as e:
        print(f"Error finding agent: {str(e)}")
        return None


def main():
    """에이전트를 삭제하는 기본 함수입니다."""
    print("Finding deployed agent...")
    agent_info = get_agent_info_from_deploy_result()

    if not agent_info:
        print("No agent found to delete. Exiting.")
        return

    print("Deleting agent:")
    print(f"  Agent Name: {agent_info['agent_name']}")
    print(f"  Agent Runtime ID: {agent_info['agent_runtime_id']}")
    print(f"  ECR URI: {agent_info['ecr_uri']}")

    try:
        # 에이전트 삭제
        result = delete_agent(
            agent_runtime_id=agent_info["agent_runtime_id"],
            ecr_uri=agent_info["ecr_uri"],
        )

        if result["status"] == "success":
            print("Agent deletion successful!")
            print(f"Runtime deletion response: {result.get('runtime_delete_response', {})}")
            print(f"ECR deletion response: {result.get('ecr_delete_response', {})}")
        else:
            print(f"Agent deletion failed: {result.get('error', 'Unknown error')}")
            sys.exit(1)

    except Exception as e:
        print(f"Error deleting agent: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
