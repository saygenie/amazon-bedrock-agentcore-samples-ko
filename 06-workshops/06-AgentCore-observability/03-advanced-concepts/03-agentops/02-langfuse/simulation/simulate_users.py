import json
import os
import sys

# utils를 가져올 수 있도록 상위 디렉터리를 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.agent import invoke_agent

# 구성
AGENT_ARN = "arn:aws:bedrock-agentcore:us-west-2:308819823671:runtime/strands_claude45sonnet_prompt1_PRD-86HGVK6oub"  # 실제 에이전트 ARN으로 교체
CONFIG_FILE = "load_config.json"


def load_config(config_file):
    """
    프롬프트가 포함된 구성 파일을 로드합니다.

    파라미터:
    - config_file (str): 구성 JSON 파일 경로

    반환:
    - dict: 로드된 구성
    """
    config_path = os.path.join(os.path.dirname(__file__), config_file)

    with open(config_path, "r") as f:
        config = json.load(f)

    return config


def simulate_user_interactions(agent_arn, prompts):
    """
    각 프롬프트로 에이전트를 호출하여 사용자 상호작용을 시뮬레이션합니다.

    파라미터:
    - agent_arn (str): 배포된 에이전트 런타임의 ARN
    - prompts (list): 'name' 및 'prompt' 키가 있는 프롬프트 딕셔너리 목록

    반환:
    - list: 각 에이전트 호출의 결과 목록
    """
    results = []

    for idx, prompt_item in enumerate(prompts):
        prompt_name = prompt_item.get("name", f"prompt_{idx}")
        prompt = prompt_item.get("prompt", "")

        print(f"\n{'=' * 80}")
        print(f"Processing: {prompt_name}")
        print(f"Prompt: {prompt}")
        print(f"{'=' * 80}")

        # 에이전트 호출
        result = invoke_agent(agent_arn, prompt)

        # 오류 확인
        if "error" in result:
            print(f"❌ Error invoking agent: {result['error']}")
            results.append(
                {
                    "prompt_name": prompt_name,
                    "prompt": prompt,
                    "status": "error",
                    "error": result["error"],
                }
            )
            continue

        # 콘텐츠 유형에 따라 응답 추출
        if result.get("content_type") == "application/json":
            response = result["response"]
        else:
            response = result.get("response", "")

        print("\n✅ Response received:")
        print(f"{response}\n")

        results.append(
            {
                "prompt_name": prompt_name,
                "prompt": prompt,
                "status": "success",
                "response": response,
                "session_id": result.get("session_id"),
                "content_type": result.get("content_type"),
            }
        )

    return results


def main():
    """
    구성을 로드하고 사용자 상호작용을 시뮬레이션하는 기본 함수입니다.
    """
    print(f"Loading configuration from {CONFIG_FILE}...")

    try:
        config = load_config(CONFIG_FILE)
        prompts = config.get("prompts", [])

        if not prompts:
            print("⚠️  No prompts found in configuration file.")
            return

        print(f"Found {len(prompts)} prompt(s) to process.")
        print(f"Using Agent ARN: {AGENT_ARN}")

        # 사용자 상호작용 시뮬레이션
        results = simulate_user_interactions(AGENT_ARN, prompts)

        # 요약 출력
        print(f"\n{'=' * 80}")
        print("SIMULATION SUMMARY")
        print(f"{'=' * 80}")
        print(f"Total prompts processed: {len(results)}")
        success_count = sum(1 for r in results if r["status"] == "success")
        error_count = sum(1 for r in results if r["status"] == "error")
        print(f"✅ Successful: {success_count}")
        print(f"❌ Failed: {error_count}")
        print(f"{'=' * 80}\n")

    except FileNotFoundError:
        print(f"❌ Error: Config file '{CONFIG_FILE}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON config file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
