import sys
import os
import json

from langfuse.experiment import create_evaluator_from_autoevals
from autoevals.llm import Factuality
from openai import OpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils.langfuse import get_langfuse_client
from utils.agent import invoke_agent
from utils.aws import get_ssm_parameter

# 스크립트 상단에 다음 설정 추가
# logging.basicConfig(level=logging.DEBUG)
# logger = logging.getLogger("autoevals")
# logger.setLevel(logging.DEBUG)


# hp_config.json에서 하이퍼파라미터와 에이전트 구성 로드
def load_hp_config(config_path="cicd/hp_config.json"):
    """JSON 파일에서 하이퍼파라미터와 에이전트 구성을 로드합니다."""
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        return config["tst"]
    except FileNotFoundError:
        print(f"Error: Configuration file {config_path} not found.")
        print("Make sure to run the deployment step first.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {config_path}: {e}")
        sys.exit(1)


# 구성 로드
print("Loading agent configuration from hp_config.json...")
config = load_hp_config()

# 구성에 agent_arn이 있는지 확인
if not config.get("agent_arn"):
    print("Error: agent_arn not found in hp_config.json.")
    print("Make sure to run the deployment step first.")
    sys.exit(1)

agent_arn = config["agent_arn"]
print(f"Using agent ARN from deployment: {agent_arn}")
print(f"Agent Name: {config.get('agent_name', 'N/A')}")
print(f"Agent ID: {config.get('agent_id', 'N/A')}")

# Langfuse 클라이언트 초기화
langfuse_client = get_langfuse_client()

# Bedrock 모델을 LLMaaJ 모델로 정의
# Bedrock을 가리키도록 환경 변수 설정
os.environ["OPENAI_API_KEY"] = get_ssm_parameter("/autoevals/OPENAI_API_KEY")
os.environ["OPENAI_BASE_URL"] = get_ssm_parameter("/autoevals/OPENAI_BASE_URL")


# 데이터 세트 가져오기
dataset_name = "strands-ai-mcp-agent-evaluation"
dataset = langfuse_client.get_dataset(dataset_name)

# 원본 데이터 세트의 처음 3개 항목 출력
print(f"\n{'=' * 80}\nFirst 3 ORIGINAL items from dataset '{dataset_name}':\n{'=' * 80}")
for i, item in enumerate(dataset.items[:3]):
    print(f"\nItem {i + 1}:")
    print(f"  ID: {item.id}")
    print(f"  Input: {item.input}")
    print(f"  Expected Output: {item.expected_output}")
    print(f"  Metadata: {item.metadata}")
print(f"{'=' * 80}\n")

# 데이터 세트 항목 변환: response_facts를 개별 항목으로 확장
expanded_items = []
for item in dataset.items:
    # expected_output에서 response_facts 추출
    response_facts = item.expected_output.get("response_facts", [])

    # 각 response_fact에 대해 새 항목 생성
    for idx, fact in enumerate(response_facts):
        # 변환된 데이터로 딕셔너리 생성
        # 입력 딕셔너리에서 질문 문자열 추출
        expanded_item = {"input": item.input["question"], "expected_output": fact}
        expanded_items.append(expanded_item)

# 변환된 데이터 세트의 처음 3개 항목 출력
print(f"\n{'=' * 80}\nFirst 3 EXPANDED items from dataset '{dataset_name}':\n{'=' * 80}")
for i, item in enumerate(expanded_items[:3]):
    print(f"\nItem {i + 1}:")
    print(f"  Input: {item['input']}")
    print(f"  Expected Output: {item['expected_output']}")
print(f"{'=' * 80}\n")


# invoke_agent를 래핑하는 작업 함수 정의
def agent_task(*, item, **kwargs):
    """
    데이터 세트 항목의 입력으로 에이전트를 호출하는 작업 함수입니다.

    파라미터:
    - item: 'input'과 'expected_output'이 포함된 딕셔너리

    반환:
    - str: 에이전트의 응답
    """
    # 데이터 세트 항목에서 프롬프트 추출
    # 이제 item은 딕셔너리이며 input에 질문이 직접 포함됨
    prompt = item["input"]

    # 에이전트 호출
    result = invoke_agent(agent_arn, prompt)

    # 오류 확인
    if "error" in result:
        raise Exception(f"Agent invocation error: {result['error']}")

    # 콘텐츠 유형에 따라 응답 추출
    if result.get("content_type") == "application/json":
        response = result["response"]
    else:
        response = result.get("response", "")

    return response


# autoevals 평가기 정의
evaluator = create_evaluator_from_autoevals(Factuality(client=OpenAI(), model="qwen.qwen3-235b-a22b-2507-v1:0"))

result = langfuse_client.run_experiment(
    name="Autoevals Integration Test",
    data=expanded_items,
    task=agent_task,
    evaluators=[evaluator],
)

print(result.format(include_item_results=True))

# Factuality 점수를 추출하여 파일에 저장

factuality_scores = []
# 실험 결과에서 항목 결과에 접근
for item_result in result.item_results:
    for evaluation in item_result.evaluations:
        if evaluation.name == "Factuality":
            evaluation_dict = {
                "name": evaluation.name,
                "value": evaluation.value,
                "comment": evaluation.comment,
            }
            factuality_scores.append(evaluation_dict)
            print(evaluation_dict)

# 평균 계산
avg_score = sum(s["value"] for s in factuality_scores) / len(factuality_scores) if factuality_scores else 0

# 결과 저장
results = {
    "experiment_name": result.name,
    "total_items": len(factuality_scores),
    "average_factuality_score": avg_score,
    "scores": factuality_scores,
}

with open("factuality_results.json", "w") as f:
    json.dump(results, f, indent=2)

print(f"\n{'=' * 80}")
print("Factuality Results Summary:")
print(f"  Average Score: {avg_score:.3f} ({avg_score * 100:.1f}%)")
print(f"  Total Items: {len(factuality_scores)}")
print("  Results saved to: factuality_results.json")
print(f"{'=' * 80}\n")
