"""
HR Assistant Agent — Bedrock AgentCore Runtime에 배포되는 Strands 에이전트입니다.

도구(재현 가능한 평가를 위한 결정론적 동작/모의 데이터):
  get_pto_balance        — 직원의 남은 PTO 일수
  submit_pto_request     — 휴가 신청
  lookup_hr_policy       — 회사 정책 문서
  get_benefits_summary   — 건강, 치과, 시력, 401k, 생명 보험 세부 정보
  get_pay_stub           — 지정된 기간의 급여 명세서
"""

import logging

from bedrock_agentcore.runtime import BedrockAgentCoreApp, BedrockAgentCoreContext
from strands import Agent, tool
from strands.models import BedrockModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()

# ---------------------------------------------------------------------------
# 모의 데이터
# ---------------------------------------------------------------------------

_PTO_BALANCES = {
    "EMP-001": {"total_days": 15, "used_days": 5, "remaining_days": 10},
    "EMP-002": {"total_days": 15, "used_days": 12, "remaining_days": 3},
    "EMP-042": {"total_days": 20, "used_days": 7, "remaining_days": 13},
}

_HR_POLICIES = {
    "pto": (
        "PTO Policy: Full-time employees accrue 15 days of PTO per year (20 days after 3 years). "
        "PTO requests must be submitted at least 2 business days in advance. "
        "Unused PTO up to 5 days rolls over to the next year. "
        "PTO cannot be taken in advance of accrual."
    ),
    "remote_work": (
        "Remote Work Policy: Employees may work remotely up to 3 days per week"
        " with manager approval. "
        "Core collaboration hours are 10am-3pm local time. "
        "A dedicated workspace with reliable internet (25 Mbps+) is required. "
        "Employees must be reachable via Slack and email during core hours."
    ),
    "parental_leave": (
        "Parental Leave Policy: Primary caregivers receive 16 weeks of fully paid parental leave. "
        "Secondary caregivers receive 6 weeks of fully paid parental leave. "
        "Leave may begin up to 2 weeks before the expected birth or adoption date. "
        "Benefits continue unchanged during parental leave."
    ),
    "code_of_conduct": (
        "Code of Conduct: All employees are expected to treat colleagues, customers, and partners "
        "with respect and professionalism. Harassment, discrimination, and retaliation of any kind "
        "are strictly prohibited. Violations should be reported to HR or via the anonymous hotline."
    ),
}

_BENEFITS = {
    "health": (
        "Health Insurance: The company covers 90% of premiums for employee-only coverage and 75% "
        "for family coverage. Plans available: Blue Shield PPO, Kaiser HMO, and HDHP with HSA. "
        "Annual deductible: $500 (PPO), $0 (HMO), $1,500 (HDHP). "
        "Open enrollment is each November for the following calendar year."
    ),
    "dental": (
        "Dental Insurance: 100% coverage for preventive care (cleanings, X-rays). "
        "80% coverage for basic restorative care (fillings, extractions). "
        "50% coverage for major restorative care (crowns, bridges). "
        "Annual maximum benefit: $2,000 per person. Orthodontia lifetime maximum: $1,500."
    ),
    "vision": (
        "Vision Insurance: Annual eye exam covered in full. "
        "Frames or contacts allowance: $200 per year. "
        "Laser vision correction discount: 15% off at participating providers."
    ),
    "401k": (
        "401(k) Plan: The company matches 100% of employee contributions up to 4% of salary. "
        "An additional 50% match on the next 2% (total effective match up to 5%). "
        "Employees are eligible to contribute immediately; company match vests over 3 years. "
        "2026 IRS contribution limit: $23,500 (under 50), $31,000 (age 50+)."
    ),
    "life_insurance": (
        "Life Insurance: Basic life insurance of 2x annual salary provided at no cost. "
        "Employees may purchase supplemental coverage up to 5x salary during open enrollment. "
        "Accidental death and dismemberment (AD&D) coverage equal to"
        " basic life benefit is included."
    ),
}

_PAY_STUBS = {
    ("EMP-001", "2025-12"): {
        "gross_pay": 8333.33,
        "federal_tax": 1458.33,
        "state_tax": 416.67,
        "social_security": 516.67,
        "medicare": 120.83,
        "health_premium": 125.00,
        "401k_contribution": 333.33,
        "net_pay": 5362.50,
        "period": "December 2025",
    },
    ("EMP-001", "2026-01"): {
        "gross_pay": 8333.33,
        "federal_tax": 1458.33,
        "state_tax": 416.67,
        "social_security": 516.67,
        "medicare": 120.83,
        "health_premium": 125.00,
        "401k_contribution": 333.33,
        "net_pay": 5362.50,
        "period": "January 2026",
    },
    ("EMP-042", "2026-01"): {
        "gross_pay": 10416.67,
        "federal_tax": 1875.00,
        "state_tax": 520.83,
        "social_security": 645.83,
        "medicare": 151.04,
        "health_premium": 200.00,
        "401k_contribution": 416.67,
        "net_pay": 6607.30,
        "period": "January 2026",
    },
}

_PTO_REQUEST_COUNTER = {"n": 0}


# ---------------------------------------------------------------------------
# Strands 도구
# ---------------------------------------------------------------------------


@tool
def get_pto_balance(employee_id: str) -> dict:
    """
    Return the current PTO balance for an employee.

    Args:
        employee_id: Employee identifier (e.g. EMP-001). Supported: EMP-001, EMP-002, EMP-042.

    Returns:
        Dict with total_days, used_days, and remaining_days.
        Call this tool first before submitting any PTO request.
    """
    balance = _PTO_BALANCES.get(employee_id)
    if balance:
        return {"employee_id": employee_id, **balance}
    return {"employee_id": employee_id, "error": f"Employee {employee_id} not found."}


@tool
def submit_pto_request(
    employee_id: str,
    start_date: str,
    end_date: str,
    reason: str = "Personal time off",
) -> dict:
    """
    Submit a PTO (paid time off) request for an employee.

    Args:
        employee_id: Employee identifier (e.g. EMP-001). Must exist in the system.
        start_date:  First day of leave in YYYY-MM-DD format (e.g. 2026-06-01).
        end_date:    Last day of leave in YYYY-MM-DD format (e.g. 2026-06-05).
        reason:      Short reason for the request (e.g. "Family vacation").
                     Requests must be submitted at least 2 business days in advance.

    Returns:
        Dict with request_id (format PTO-2026-NNN), status, and confirmation message.
    """
    _PTO_REQUEST_COUNTER["n"] += 1
    request_id = f"PTO-2026-{_PTO_REQUEST_COUNTER['n']:03d}"
    return {
        "request_id": request_id,
        "employee_id": employee_id,
        "start_date": start_date,
        "end_date": end_date,
        "reason": reason,
        "status": "APPROVED",
        "message": (f"PTO request {request_id} approved for {employee_id} from {start_date} to {end_date}."),
    }


@tool
def lookup_hr_policy(topic: str) -> dict:
    """
    Look up a company HR policy document by topic.

    Args:
        topic: Policy topic. Supported values: pto, remote_work, parental_leave, code_of_conduct.
               Use 'pto' for questions about time-off accrual, carryover, or advance notice rules.

    Returns:
        Dict with topic and policy_text containing the full policy document.
    """
    key = topic.lower().replace(" ", "_").replace("-", "_")
    text = _HR_POLICIES.get(key)
    if text:
        return {"topic": topic, "policy_text": text}
    return {
        "topic": topic,
        "error": f"Policy '{topic}' not found. Available: {list(_HR_POLICIES.keys())}",
    }


@tool
def get_benefits_summary(benefit_type: str) -> dict:
    """
    Return a detailed summary of a specific employee benefit.

    Args:
        benefit_type: Type of benefit. Supported values: health, dental, vision, 401k, life_insurance.
                      Use '401k' for retirement plan details including employer match percentages.
                      Use 'health' for insurance coverage percentages and available plans.

    Returns:
        Dict with benefit_type and summary containing full benefit details.
    """
    key = benefit_type.lower().replace(" ", "_").replace("-", "_")
    text = _BENEFITS.get(key)
    if text:
        return {"benefit_type": benefit_type, "summary": text}
    return {
        "benefit_type": benefit_type,
        "error": f"Benefit '{benefit_type}' not found. Available: {list(_BENEFITS.keys())}",
    }


@tool
def get_pay_stub(employee_id: str, period: str) -> dict:
    """
    Retrieve a pay stub for an employee for a specific pay period.

    Args:
        employee_id: Employee identifier (e.g. EMP-001). Supported: EMP-001, EMP-042.
        period:      Pay period in YYYY-MM format (e.g. 2026-01 for January 2026).
                     Available periods: 2025-12, 2026-01 for EMP-001; 2026-01 for EMP-042.

    Returns:
        Dict with gross pay, itemized deductions (federal tax, state tax, FICA, benefits), and net pay.
    """
    stub = _PAY_STUBS.get((employee_id, period))
    if stub:
        return {"employee_id": employee_id, **stub}
    return {
        "employee_id": employee_id,
        "period": period,
        "error": f"Pay stub not found for {employee_id} period {period}.",
    }


# ---------------------------------------------------------------------------
# 에이전트
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM_PROMPT = """You are a helpful HR Assistant for Acme Corp.

You help employees with:
- Checking PTO (paid time off) balances
- Submitting PTO requests
- Looking up HR policies (PTO, remote work, parental leave, code of conduct)
- Understanding employee benefits (health, dental, vision, 401k, life insurance)
- Retrieving pay stub information

Always use the available tools to answer questions accurately. Do not make up
policy details, benefit amounts, or pay information — look them up.
Be concise, professional, and friendly."""

_MODEL = BedrockModel(model_id="us.amazon.nova-lite-v1:0")
_TOOLS = [
    get_pto_balance,
    submit_pto_request,
    lookup_hr_policy,
    get_benefits_summary,
    get_pay_stub,
]

# 세션 캐시: session_id -> Agent(턴 간 대화 기록 유지)
_SESSION_AGENTS: dict[str, Agent] = {}


@app.entrypoint
async def invoke(payload, context):
    """AgentCore Runtime의 에이전트 호출을 처리합니다."""
    prompt = payload.get("prompt", "")
    session_id = context.session_id
    logger.info("Received prompt (session=%s): %s", session_id, prompt[:80])

    # baggage 헤더를 통해 주입된 Configuration Bundle에서 구성을 읽습니다.
    # 번들이 없으면 기본값을 사용합니다.
    bundle = BedrockAgentCoreContext.get_config_bundle()
    system_prompt = DEFAULT_SYSTEM_PROMPT
    tool_descs: dict = {}
    if bundle:
        system_prompt = bundle.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        tool_descs = bundle.get("tool_descriptions", {})

    if session_id and session_id in _SESSION_AGENTS:
        agent = _SESSION_AGENTS[session_id]
        agent.system_prompt = system_prompt
    else:
        agent = Agent(model=_MODEL, tools=_TOOLS, system_prompt=system_prompt)
        if session_id:
            _SESSION_AGENTS[session_id] = agent

    # 번들의 도구 설명 재정의를 적용합니다.
    # strands-agents 1.x에서는 agent.tool_registry.registry를 통해 도구에 접근합니다.
    if tool_descs:
        for t in agent.tool_registry.registry.values():
            name = getattr(t, "tool_name", None)
            if name and name in tool_descs and hasattr(t, "tool_spec"):
                t.tool_spec["description"] = tool_descs[name]

    async def stream():
        async for event in agent.stream_async(prompt):
            if "data" in event:
                yield event["data"]

    return stream()


if __name__ == "__main__":
    app.run()
