import os
from datetime import datetime
from langfuse import get_client
from utils.agent import invoke_agent
from utils.aws import get_ssm_parameter


def get_langfuse_client():
    """
    올바른 구성으로 Langfuse 클라이언트를 초기화하여 반환합니다.

    반환:
    - Langfuse 클라이언트 인스턴스
    """

    os.environ["LANGFUSE_HOST"] = get_ssm_parameter("/langfuse/LANGFUSE_HOST")
    os.environ["LANGFUSE_SECRET_KEY"] = get_ssm_parameter("/langfuse/LANGFUSE_SECRET_KEY")
    os.environ["LANGFUSE_PUBLIC_KEY"] = get_ssm_parameter("/langfuse/LANGFUSE_PUBLIC_KEY")
    os.environ["LANGFUSE_PROJECT_NAME"] = get_ssm_parameter("/langfuse/LANGFUSE_PROJECT_NAME")
    # Langfuse 클라이언트 초기화
    client = get_client()

    return client


def run_experiment(
    agent_arn,
    dataset_name="strands-ai-mcp-agent-evaluation",
    experiment_name=None,
    experiment_description=None,
    evaluators=None,
    run_evaluators=None,
    max_concurrency=1,
    metadata=None,
):
    """
    invoke_agent를 작업 함수로 사용하여 Langfuse 데이터 세트에서 실험을 실행합니다.

    파라미터:
    - agent_arn (str): 배포된 에이전트 런타임의 ARN
    - dataset_name (str): Langfuse의 데이터 세트 이름(기본값: "strands-ai-mcp-agent-evaluation")
    - experiment_name (str): 이 실험 실행의 이름(기본값: "{timestamp}_strands_langfuse_mcp_experimentation")
    - experiment_description (str, optional): 실험 설명
    - evaluators (list, optional): 항목 수준 평가를 위한 평가기 함수 목록
    - run_evaluators (list, optional): 실행 수준 평가를 위한 평가기 함수 목록
    - max_concurrency (int): 동시 작업 실행의 최댓값(기본값: 1)

    반환:
    - dict: 트레이스, 점수 및 메타데이터가 포함된 실험 결과
    """

    # 실험 이름에 타임스탬프 추가
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    experiment_name_ts = f"{timestamp}_{experiment_name}"

    # Langfuse 클라이언트 초기화
    langfuse = get_langfuse_client()

    # 데이터 세트 가져오기
    dataset = langfuse.get_dataset(dataset_name)

    # invoke_agent를 래핑하는 작업 함수 정의
    def agent_task(*, item, **kwargs):
        """
        데이터 세트 항목의 입력으로 에이전트를 호출하는 작업 함수입니다.

        파라미터:
        - item: input 및 선택적 expected_output이 포함된 DatasetItemClient 객체

        반환:
        - str: 에이전트의 응답
        """
        # 데이터 세트 항목에서 프롬프트 추출
        # 점 표기법으로 DatasetItemClient 속성에 접근
        prompt = item.input["question"]

        # 에이전트 호출
        result = invoke_agent(agent_arn, prompt, environment="DEV")

        # 오류 확인
        if "error" in result:
            raise Exception(f"Agent invocation error: {result['error']}")

        # 콘텐츠 유형에 따라 응답 추출
        if result.get("content_type") == "application/json":
            response = result["response"]
        else:
            response = result.get("response", "")

        return response

    # 데이터 세트에서 실험 실행
    result = dataset.run_experiment(
        name=experiment_name_ts,
        description=experiment_description or f"Evaluation of agent {agent_arn}",
        task=agent_task,
        metadata=metadata,
        # evaluators=evaluators or [],
        # run_evaluators=run_evaluators or [],
        # max_concurrency=max_concurrency
    )

    # 형식이 지정된 결과 출력
    print("\n" + "=" * 80)
    print("EXPERIMENT RESULTS")
    print("=" * 80)
    print(result.format())
    print("=" * 80 + "\n")

    return result


def run_experiment_with_evaluators(
    agent_arn,
    dataset_name="strands-ai-mcp-agent-evaluation",
    experiment_name="Agent Evaluation with Scoring",
    experiment_description=None,
    max_concurrency=1,
):
    """
    응답 품질 평가를 위한 예제 평가기로 실험을 실행합니다.

    파라미터:
    - agent_arn (str): 배포된 에이전트 런타임의 ARN
    - dataset_name (str): Langfuse의 데이터 세트 이름
    - experiment_name (str): 이 실험 실행의 이름
    - experiment_description (str, optional): 실험 설명
    - max_concurrency (int): 동시 작업 실행의 최댓값

    반환:
    - dict: 평가가 포함된 실험 결과
    """
    from langfuse import Evaluation

    # 항목 수준 평가기 정의
    def response_length_evaluator(*, input, output, expected_output, metadata, **kwargs):
        """
        응답 길이가 너무 짧지 않고 적절한지 평가합니다.
        """
        if isinstance(output, str):
            response_text = output
        else:
            response_text = str(output)

        # 응답이 10자 이상인지 확인
        is_adequate = len(response_text) >= 10

        return Evaluation(
            name="response_length",
            value=1.0 if is_adequate else 0.0,
            comment=f"Response length: {len(response_text)} characters",
        )

    def response_quality_evaluator(*, input, output, expected_output, metadata, **kwargs):
        """
        기본 품질 검사: 응답에 오류 징후가 없는지 확인합니다.
        """
        if isinstance(output, str):
            response_text = output.lower()
        else:
            response_text = str(output).lower()

        # 일반적인 오류 패턴 확인
        error_indicators = ["error", "failed", "unable", "cannot", "invalid"]
        has_errors = any(indicator in response_text for indicator in error_indicators)

        return Evaluation(
            name="response_quality",
            value=0.0 if has_errors else 1.0,
            comment="Response contains error indicators" if has_errors else "Response appears valid",
        )

    # 실행 수준 평가기 정의
    def average_score_evaluator(*, run_evaluations, **kwargs):
        """
        모든 항목 평가의 평균 점수를 계산합니다.
        """
        if not run_evaluations:
            return Evaluation(name="avg_score", value=0.0, comment="No evaluations to average")

        # response_quality 점수의 평균 계산
        quality_scores = [eval.value for eval in run_evaluations if eval.name == "response_quality"]

        if quality_scores:
            avg = sum(quality_scores) / len(quality_scores)
            return Evaluation(
                name="avg_response_quality",
                value=avg,
                comment=f"Average response quality: {avg:.2%}",
            )

        return Evaluation(name="avg_response_quality", value=0.0, comment="No quality scores found")

    # 평가기를 사용하여 실험 실행
    return run_experiment(
        agent_arn=agent_arn,
        dataset_name=dataset_name,
        experiment_name=experiment_name,
        experiment_description=experiment_description,
        evaluators=[response_length_evaluator, response_quality_evaluator],
        run_evaluators=[average_score_evaluator],
        max_concurrency=max_concurrency,
    )
