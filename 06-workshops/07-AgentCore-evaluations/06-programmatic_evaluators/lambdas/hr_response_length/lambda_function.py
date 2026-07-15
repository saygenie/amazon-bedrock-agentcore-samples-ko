# pylint: disable=duplicate-code
"""
HRResponseLength - Code-Based Evaluator(TRACE 수준)

SDK 1.6의 @custom_code_based_evaluator() 데코레이터를 사용합니다.
에이전트 응답의 문자 수가 MIN_LENGTH와 MAX_LENGTH 사이인지 검사합니다.
측정 전에 thinking 블록(<thinking>...</thinking>)을 제거합니다.

반환값:
    value       - 범위 내이면 1.0(PASS), 그렇지 않으면 0.0(FAIL)
    label       - "PASS" 또는 "FAIL"
    explanation - 실제 길이와 허용 범위
"""

import re

from bedrock_agentcore.evaluation import (  # pylint: disable=no-name-in-module
    EvaluatorInput,
    EvaluatorOutput,
    custom_code_based_evaluator,
)

MIN_LENGTH = 50
MAX_LENGTH = 600

_THINKING_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL)


def _first_clean_message(span: dict) -> str:
    """span 이벤트에서 정리된 첫 번째 비어 있지 않은 메시지를 반환합니다."""
    for se in span.get("span_events", []):
        body = se.get("body", {})
        if not isinstance(body, dict):
            continue
        for msg in body.get("output", {}).get("messages", []):
            content = msg.get("content", {})
            if isinstance(content, dict):
                text = content.get("message", "")
                if text:
                    cleaned = _THINKING_RE.sub("", text).strip()
                    if cleaned:
                        return cleaned
    return ""


def _extract_final_response(spans: list) -> str:
    """invoke_agent span에서 최종적으로 표시되는 응답 텍스트를 추출합니다."""
    for span in spans:
        name = (span.get("name") or "").lower()
        if "invoke_agent" not in name:
            continue
        text = _first_clean_message(span)
        if text:
            return text
    return ""


def _extract_fallback_response(spans: list) -> str:
    """대체 방식: 모든 span_events에서 비어 있지 않은 content 메시지를 찾습니다."""
    for span in reversed(spans):
        for se in span.get("span_events", []):
            body = se.get("body", {})
            if not isinstance(body, dict):
                continue
            for msg in (body.get("output", {}) or {}).get("messages", []):
                content = msg.get("content", {})
                text = (content.get("message") or "") if isinstance(content, dict) else ""
                cleaned = _THINKING_RE.sub("", text).strip()
                if cleaned and not cleaned.startswith("[{"):
                    return cleaned
    return ""


@custom_code_based_evaluator()
def lambda_handler(evaluator_input: EvaluatorInput, _context) -> EvaluatorOutput:
    """단일 에이전트 trace의 응답 길이를 평가합니다."""
    spans = evaluator_input.session_spans

    # TRACE 수준에서는 target_trace_id가 평가할 trace를 식별
    if evaluator_input.evaluation_level == "TRACE" and evaluator_input.target_trace_id:
        spans = [
            s
            for s in spans
            if s.get("traceId") == evaluator_input.target_trace_id
            or s.get("trace_id") == evaluator_input.target_trace_id
        ]

    output_text = _extract_final_response(spans) or _extract_fallback_response(spans)

    if not output_text:
        return EvaluatorOutput(
            label="FAIL",
            errorCode="NoResponseFound",
            errorMessage=(
                f"No agent response text found in {len(spans)} spans. "
                "Expected invoke_agent span with span_events containing output message."
            ),
        )

    length = len(output_text)

    if MIN_LENGTH <= length <= MAX_LENGTH:
        return EvaluatorOutput(
            value=1.0,
            label="PASS",
            explanation=(
                f"Response length {length} chars is within the acceptable range [{MIN_LENGTH}, {MAX_LENGTH}]."
            ),
        )
    if length < MIN_LENGTH:
        return EvaluatorOutput(
            value=0.0,
            label="FAIL",
            explanation=(
                f'Response length {length} chars is too short (minimum {MIN_LENGTH}). Preview: "{output_text[:60]}..."'
            ),
        )
    return EvaluatorOutput(
        value=0.0,
        label="FAIL",
        explanation=(f"Response length {length} chars exceeds maximum {MAX_LENGTH}. Consider a more concise answer."),
    )
