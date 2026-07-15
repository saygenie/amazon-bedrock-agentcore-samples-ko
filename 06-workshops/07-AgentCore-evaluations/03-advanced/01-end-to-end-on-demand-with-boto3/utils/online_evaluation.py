"""에이전트 호출 및 평가 워크플로용 Online Evaluation 도우미 함수입니다."""

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .evaluation_client import EvaluationClient


def generate_session_id() -> str:
    """UUID 형식의 유효한 세션 ID를 생성합니다.

    반환값:
        UUID v4 문자열(예: 'de45c51c-27c3-4670-aa72-c8b302b23890')
    """
    return str(uuid.uuid4())


def invoke_agent(
    agentcore_client: Any,
    agent_arn: str,
    prompt: str,
    session_id: str = "",
    qualifier: str = "DEFAULT",
) -> Tuple[str, List[str]]:
    """AgentCore Runtime을 호출하고 세션 ID와 응답 내용을 반환합니다.

    인수:
        agentcore_client: Boto3 agentcore client
        agent_arn: Agent Runtime ARN
        prompt: 사용자 입력 prompt
        session_id: 다중 턴 대화용 선택적 세션 ID(UUID 형식)
                   - 빈 문자열 '' = 새 세션 생성
                   - 유효한 UUID = 기존 세션을 계속하거나 특정 세션 ID 사용
        qualifier: Agent Runtime qualifier(기본값: DEFAULT)

    반환값:
        (session_id, content_list) 튜플
    """
    api_params = {
        "agentRuntimeArn": agent_arn,
        "qualifier": qualifier,
        "payload": json.dumps({"prompt": prompt}),
    }

    if session_id:
        api_params["runtimeSessionId"] = session_id

    boto3_response = agentcore_client.invoke_agent_runtime(**api_params)

    returned_session_id = (
        boto3_response["ResponseMetadata"]["HTTPHeaders"].get("x-amzn-bedrock-agentcore-runtime-session-id")
        or boto3_response.get("runtimeSessionId")
        or session_id
    )

    content = []
    if "text/event-stream" in boto3_response.get("contentType", ""):
        for line in boto3_response["response"].iter_lines(chunk_size=1):
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    content.append(line[6:])
    else:
        try:
            events = [event for event in boto3_response.get("response", [])]
            if events:
                content = [json.loads(events[0].decode("utf-8"))]
        except Exception as e:
            content = [f"Error reading EventStream: {e}"]

    return returned_session_id, content


def evaluate_session(
    eval_client: EvaluationClient,
    session_id: str,
    evaluators: List[str],
    scope: str,
    agent_id: str,
    region: str,
    experiment_name: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Any:
    """지정된 Evaluator로 세션을 평가합니다.

    인수:
        eval_client: EvaluationClient 인스턴스
        session_id: 평가할 세션 ID
        evaluators: Evaluator ID 목록
        scope: 평가 범위(session, trace 또는 span)
        agent_id: Agent ID
        region: AWS 리전
        experiment_name: 추적용 실험 식별자
        metadata: 선택적 메타데이터 딕셔너리

    반환값:
        EvaluationResults 객체
    """
    eval_metadata = {"experiment": experiment_name}
    if metadata:
        eval_metadata.update(metadata)

    results = eval_client.evaluate_session(
        session_id=session_id,
        evaluator_ids=evaluators,
        agent_id=agent_id,
        region=region,
        scope=scope,
        auto_save_input=True,
        auto_save_output=True,
        auto_create_dashboard=True,
        metadata=eval_metadata,
    )

    return results


def evaluate_session_comprehensive(
    eval_client: EvaluationClient,
    session_id: str,
    agent_id: str,
    region: str,
    experiment_name: str,
    flexible_evaluators: List[str],
    session_only_evaluators: List[str],
    span_only_evaluators: List[str],
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Any]:
    """모든 Evaluator를 적절한 범위에서 실행합니다.

    인수:
        eval_client: EvaluationClient 인스턴스
        session_id: 평가할 세션 ID
        agent_id: Agent ID
        region: AWS 리전
        experiment_name: 실험 식별자
        flexible_evaluators: 유연한 범위의 Evaluator 목록
        session_only_evaluators: 세션 전용 Evaluator 목록
        span_only_evaluators: span 전용 Evaluator 목록
        metadata: 선택적 메타데이터 딕셔너리

    반환값:
        결합된 평가 결과 목록
    """
    all_results = []

    evaluation_configs = [
        {"evaluators": flexible_evaluators, "scope": "session"},
        {"evaluators": session_only_evaluators, "scope": "session"},
        {"evaluators": span_only_evaluators, "scope": "span"},
    ]

    for config in evaluation_configs:
        if config["evaluators"]:
            try:
                results = evaluate_session(
                    eval_client=eval_client,
                    session_id=session_id,
                    evaluators=config["evaluators"],
                    scope=config["scope"],
                    agent_id=agent_id,
                    region=region,
                    experiment_name=experiment_name,
                    metadata=metadata,
                )
                all_results.extend(results.results)
            except Exception as e:
                print(f"Error in {config['scope']} evaluation: {e}")

    return all_results


def invoke_and_evaluate(
    agentcore_client: Any,
    eval_client: EvaluationClient,
    agent_arn: str,
    agent_id: str,
    region: str,
    prompt: str,
    experiment_name: str,
    session_id: str = "",
    metadata: Optional[Dict[str, Any]] = None,
    evaluators: Optional[List[str]] = None,
    scope: str = "session",
    delay: int = 90,
    flexible_evaluators: Optional[List[str]] = None,
    session_only_evaluators: Optional[List[str]] = None,
    span_only_evaluators: Optional[List[str]] = None,
) -> Tuple[str, List[Any]]:
    """전체 워크플로: 에이전트를 호출하고 로그 전파를 기다린 다음 평가합니다.

    인수:
        agentcore_client: Boto3 agentcore client
        eval_client: EvaluationClient 인스턴스
        agent_arn: Agent Runtime ARN
        agent_id: Agent ID
        region: AWS 리전
        prompt: 사용자 입력 prompt
        experiment_name: 실험 식별자
        session_id: 선택적 세션 ID(비어 있으면 새 세션, UUID이면 세션 계속 또는 지정)
        metadata: 선택적 메타데이터 딕셔너리
        evaluators: Evaluator ID 목록(None이면 종합 평가 사용)
        scope: 평가 범위(session, trace, span)
        delay: CloudWatch 전파를 기다릴 시간(초)
        flexible_evaluators: evaluators가 None이면 필수
        session_only_evaluators: evaluators가 None이면 필수
        span_only_evaluators: evaluators가 None이면 필수

    반환값:
        (session_id, results_list) 튜플
    """
    returned_session_id, content = invoke_agent(
        agentcore_client=agentcore_client,
        agent_arn=agent_arn,
        prompt=prompt,
        session_id=session_id,
    )

    time.sleep(delay)

    if evaluators is None:
        if not all([flexible_evaluators, session_only_evaluators, span_only_evaluators]):
            raise ValueError("Must provide evaluator lists for comprehensive evaluation")

        results = evaluate_session_comprehensive(
            eval_client=eval_client,
            session_id=returned_session_id,
            agent_id=agent_id,
            region=region,
            experiment_name=experiment_name,
            flexible_evaluators=flexible_evaluators,
            session_only_evaluators=session_only_evaluators,
            span_only_evaluators=span_only_evaluators,
            metadata=metadata,
        )
    else:
        eval_results = evaluate_session(
            eval_client=eval_client,
            session_id=returned_session_id,
            evaluators=evaluators,
            scope=scope,
            agent_id=agent_id,
            region=region,
            experiment_name=experiment_name,
            metadata=metadata,
        )
        results = eval_results.results

    return returned_session_id, content, results
