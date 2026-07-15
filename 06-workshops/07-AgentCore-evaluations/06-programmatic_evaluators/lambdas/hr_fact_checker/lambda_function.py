# pylint: disable=duplicate-code
"""
HRFactChecker - Code-Based Evaluator(SESSION 수준)

SDK 1.6의 @custom_code_based_evaluator() 데코레이터를 사용합니다.
알려진 ground truth 데이터를 기준으로 HR Assistant 응답을 결정론적으로 검증합니다.
LLM-as-judge와 달리 이 Evaluator는 정확한 패턴 일치를 사용합니다.

반환값:
    value       - 통과한 적용 가능 검사의 비율(0.0-1.0)
    label       - "PASS"(모두), "PARTIAL"(>=50%), "FAIL"(<50%), "SKIP"(실행된 검사 없음)
    explanation - 통과하거나 실패한 검사
"""

import re

from bedrock_agentcore.evaluation import (  # pylint: disable=no-name-in-module
    EvaluatorInput,
    EvaluatorOutput,
    custom_code_based_evaluator,
)

# Ground truth 레지스트리(에이전트 모의 데이터와 동일)
PTO_BALANCES = {
    "EMP-001": {"remaining": 10, "total": 15, "used": 5},
    "EMP-002": {"remaining": 3, "total": 15, "used": 12},
    "EMP-042": {"remaining": 13, "total": 20, "used": 7},
}

PAY_STUBS = {
    ("EMP-001", "2026-01"): {"gross": "8,333.33", "net": "5,362.50"},
    ("EMP-001", "2025-12"): {"gross": "8,333.33", "net": "5,362.50"},
    ("EMP-042", "2026-01"): {"gross": "10,416.67", "net": "6,607.30"},
}

MONTH_NAMES = {
    "01": ["january", "jan"],
    "02": ["february", "feb"],
    "03": ["march", "mar"],
    "04": ["april", "apr"],
    "05": ["may"],
    "06": ["june", "jun"],
    "07": ["july", "jul"],
    "08": ["august", "aug"],
    "09": ["september", "sep"],
    "10": ["october", "oct"],
    "11": ["november", "nov"],
    "12": ["december", "dec"],
}

POLICY_FACTS_BY_TOPIC = {
    "pto": [
        (
            "PTO accrual 15 days",
            [r"15\s*days?(\s*of\s*PTO|\s*per\s*year)", r"PTO.{0,30}15\s*days?"],
        ),
        ("PTO advance notice 2 days", [r"2\s*business\s*days?", r"2-business-day"]),
    ],
    "remote_work": [
        (
            "Remote work 3 days/week",
            [r"3\s*days?\s*(per|a)\s*week", r"up\s*to\s*3\s*days?"],
        ),
        (
            "Core hours 10am-3pm",
            [r"10\s*[Aa]\.?[Mm]\.?.*3\s*[Pp]\.?[Mm]", r"10am.*3pm"],
        ),
    ],
    "parental_leave": [
        ("Primary leave 16 weeks", [r"16\s*weeks?", r"primary.*16\s*weeks?"]),
        ("Secondary leave 6 weeks", [r"6\s*weeks?", r"secondary.*6\s*weeks?"]),
    ],
    "401k": [
        ("401k 4% match", [r"4%?\s*(of\s*salary)?.*match", r"matches?\s*4%"]),
        ("401k 3-year vesting", [r"3[-\s]year\s*vest", r"vests?\s*over\s*3"]),
    ],
    "health": [
        (
            "Health 90% coverage",
            [r"90%?\s*(of\s*premiums?|coverage)", r"covers?\s*90%"],
        ),
    ],
}

_THINKING_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL)


def _collect_span_texts(span: dict) -> list:
    """단일 invoke_agent span에서 비어 있지 않은 모든 응답 텍스트를 추출합니다."""
    texts = []
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
                        texts.append(cleaned)
    return texts


def _parse_spans(spans: list) -> tuple:
    """세션 span에서 연결된 응답 텍스트와 도구 이름을 추출합니다."""
    response_parts = []
    tool_names = []
    for span in spans:
        name = (span.get("name") or "").lower()
        attrs = span.get("attributes", {})
        op = attrs.get("gen_ai.operation.name", "")
        # 모든 invoke_agent 응답 텍스트 수집(다중 턴 세션)
        if "invoke_agent" in name:
            response_parts.extend(_collect_span_texts(span))
        # 도구 호출
        if op == "execute_tool":
            tool_name = attrs.get("gen_ai.tool.name", "")
            if tool_name:
                tool_names.append(tool_name)
    # 세션 수준의 사실 검사를 위해 모든 턴 연결
    all_text = " ".join(response_parts)
    return all_text, tool_names


@custom_code_based_evaluator()
def lambda_handler(  # pylint: disable=too-many-branches,too-many-locals,too-many-statements
    evaluator_input: EvaluatorInput, _context
) -> EvaluatorOutput:
    """세션의 모든 턴에 걸쳐 HR 정보의 정확성을 검증합니다."""
    spans = evaluator_input.session_spans
    all_text, tool_names = _parse_spans(spans)
    all_text_lower = all_text.lower()

    checks_run, checks_passed, checks_failed = [], [], []

    # 1. PTO 잔여 일수 정확성
    if "get_pto_balance" in tool_names:
        for emp_id, facts in PTO_BALANCES.items():
            if emp_id not in all_text:
                continue
            correct = str(facts["remaining"])
            near_remaining = rf"\b{re.escape(correct)}\b.{{0,30}}remaining"
            near_value = rf"remaining.{{0,30}}\b{re.escape(correct)}\b"
            remaining_pattern = re.compile(
                f"{near_remaining}|{near_value}",
                re.IGNORECASE,
            )
            check = f"PTO balance {emp_id} = {correct} remaining"
            checks_run.append(check)
            correct_val = bool(re.search(rf"\b{re.escape(correct)}\b", all_text))
            if bool(remaining_pattern.search(all_text)) or (correct_val and "remaining" in all_text_lower):
                checks_passed.append(check)
            else:
                checks_failed.append(f"{check}: value not found near 'remaining'")

    # 2. 급여 명세서 정확성
    for (emp_id, period), figures in PAY_STUBS.items():
        if emp_id not in all_text:
            continue
        year, month_num = period.split("-")
        month_variants = MONTH_NAMES.get(month_num, [])
        if not (year in all_text and any(m in all_text_lower for m in month_variants)):
            continue
        for field, expected_val in [
            ("gross", figures["gross"]),
            ("net", figures["net"]),
        ]:
            check = f"Pay stub {emp_id} {period} {field} = ${expected_val}"
            checks_run.append(check)
            amount_re = re.compile(r"\$?\s*" + re.escape(expected_val).replace(",", ",?"), re.IGNORECASE)
            if amount_re.search(all_text):
                checks_passed.append(check)
            else:
                checks_failed.append(f"{check}: ${expected_val} not found")

    # 3. PTO 요청 ID 형식
    if "submit_pto_request" in tool_names:
        check = "PTO request ID format PTO-2026-NNN"
        checks_run.append(check)
        match = re.search(r"PTO-2026-\d{3}", all_text)
        if match:
            checks_passed.append(f"{check}: found {match.group()}")
        else:
            checks_failed.append(f"{check}: no PTO-2026-NNN ID found")

    # 4. 정책 사실 검사
    if "lookup_hr_policy" in tool_names or "get_benefits_summary" in tool_names:
        kw_topic_map = [
            ("pto", ["paid time off", "pto policy", "pto accrual"]),
            ("remote_work", ["remote work", "work remotely"]),
            ("parental_leave", ["parental leave", "maternity", "paternity"]),
            ("401k", ["401(k)", "401k", "employer match"]),
            ("health", ["health insurance", "health plan", "hmo", "ppo", "hdhp"]),
        ]
        for topic, keywords in kw_topic_map:
            if not any(kw in all_text_lower for kw in keywords):
                continue
            for check_desc, patterns in POLICY_FACTS_BY_TOPIC.get(topic, []):
                check = f"Policy fact: {check_desc}"
                checks_run.append(check)
                if any(re.search(p, all_text, re.IGNORECASE) for p in patterns):
                    checks_passed.append(check)
                else:
                    checks_failed.append(f"{check}: expected phrase not found")

    if not checks_run:
        return EvaluatorOutput(
            value=1.0,
            label="SKIP",
            explanation=(
                f"No applicable checks triggered. "
                f"Tools: {tool_names or ['none']}, response length: {len(all_text)} chars."
            ),
        )

    total = len(checks_run)
    passed = len(checks_passed)
    value = round(passed / total, 3)
    label = "PASS" if value == 1.0 else ("PARTIAL" if value >= 0.5 else "FAIL")

    lines = [f"{passed}/{total} HR fact checks passed."]
    if checks_passed:
        lines.append("Passed: " + "; ".join(checks_passed[:4]))
    if checks_failed:
        lines.append("Failed: " + "; ".join(checks_failed[:4]))

    return EvaluatorOutput(value=value, label=label, explanation=" | ".join(lines))
