#!/usr/bin/env python3
"""
CI/CD 파이프라인용 에이전트 배포 스크립트입니다.
이 스크립트는 hp_config.json에서 에이전트 하이퍼파라미터를 읽고,
utils.agent의 deploy_agent 함수와 지정된 환경(TST 또는 PRD)을 사용하여 에이전트를 배포합니다.
"""

import json
import sys
import argparse
from pathlib import Path

# utils를 가져올 수 있도록 상위 디렉터리를 Python 경로에 추가
sys.path.append(str(Path(__file__).parent.parent))

from utils.agent import deploy_agent


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


def main():
    """에이전트를 배포하는 기본 함수입니다."""
    # 명령줄 인수 파싱
    parser = argparse.ArgumentParser(description="Deploy agent to specified environment")
    parser.add_argument(
        "--environment",
        choices=["TST", "PRD"],
        help="Environment to deploy to (TST or PRD)",
        default="TST",
    )
    args = parser.parse_args()

    environment = args.environment

    print("Loading agent hyperparameters...")
    config = load_hp_config()

    # 구성에서 모델과 시스템 프롬프트 추출
    if not config.get("model") or not config.get("system_prompt"):
        print("Error: Configuration must contain 'model' and 'system_prompt' objects.")
        sys.exit(1)

    model = config["model"]
    system_prompt = config["system_prompt"]

    print("Deploying agent with:")
    print(f"  Model: {model['name']} ({model['model_id']})")
    print(f"  System Prompt: {system_prompt['name']}")
    print(f"  Environment: {environment}")

    try:
        # 지정된 환경에 에이전트 배포
        result = deploy_agent(
            model=model,
            system_prompt=system_prompt,
            force_redeploy=False,
            environment=environment,
        )

        print("Agent deployment successful!")
        print(f"Agent Name: {result['agent_name']}")
        print(f"Agent ARN: {result['launch_result'].agent_arn}")
        print(f"Agent ID: {result['launch_result'].agent_id}")

        # 후속 파이프라인 단계에서 사용하도록 기존 hp_config.json에 에이전트 ARN 추가
        # TST와 PRD 배포 간 충돌을 방지하도록 환경별 키 사용
        # 환경 키가 없으면 생성
        if environment.lower() not in config:
            config[environment.lower()] = {}

        config[environment.lower()]["agent_arn"] = result["launch_result"].agent_arn
        config[environment.lower()]["agent_name"] = result["agent_name"]
        config[environment.lower()]["agent_id"] = result["launch_result"].agent_id

        with open("cicd/hp_config.json", "w") as f:
            json.dump(config, f, indent=2)
        print(f"Agent ARN added to hp_config.json with {environment} environment key")

        # 에이전트가 준비될 때까지 대기
        print("Waiting for agent to be ready...")
        import time

        time.sleep(60)
        # status_response = result['launch_result'].status()
        # status = status_response.endpoint['status']
        # end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']
        # while status not in end_status:
        #     time.sleep(10)
        #     status_response = result['launch_result'].status()
        #     status = status_response.endpoint['status']
        #     print(f"Agent status: {status}")

        # if status == 'READY':
        #     print("Agent is ready!")
        # else:
        #     print(f"Agent deployment failed with status: {status}")
        #     sys.exit(1)

        return result

    except Exception as e:
        print(f"Error deploying agent: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
