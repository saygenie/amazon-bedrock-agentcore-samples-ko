"""CloudWatch trace 데이터 내보내기 및 평가에 사용하는 상수입니다."""

import os

# API 구성
DEFAULT_MAX_EVALUATION_ITEMS = int(os.getenv("AGENTCORE_MAX_EVAL_ITEMS", "1000"))
MAX_SPAN_IDS_IN_CONTEXT = int(os.getenv("AGENTCORE_MAX_SPAN_IDS", "20"))

DEFAULT_RUNTIME_SUFFIX = "DEFAULT"

# 대시보드 구성
EVALUATION_OUTPUT_DIR = "evaluation_output"
EVALUATION_INPUT_DIR = "evaluation_input"
DASHBOARD_DATA_FILE = "dashboard_data.js"
DASHBOARD_HTML_FILE = "evaluation_dashboard.html"
EVALUATION_OUTPUT_PATTERN = "*.json"
DEFAULT_FILE_ENCODING = "utf-8"

# 세션 범위 Evaluator(sessionId만 사용)
# 이 Evaluator에는 세션의 모든 trace에 걸친 데이터가 필요함
SESSION_SCOPED_EVALUATORS = {
    "Builtin.GoalSuccessRate",
}

# span 범위 Evaluator(spanIds만 사용)
# 이 Evaluator에는 특정 span 수준 데이터(도구 호출)가 필요함
SPAN_SCOPED_EVALUATORS = {
    "Builtin.ToolSelectionAccuracy",
    "Builtin.ToolParameterAccuracy",
}

# 유연한 범위의 Evaluator(notSpanIds)
# 이 Evaluator는 span ID 없이 세션 또는 trace 수준에서 작동할 수 있음
FLEXIBLE_SCOPED_EVALUATORS = {
    "Builtin.Correctness",
    "Builtin.Faithfulness",
    "Builtin.Helpfulness",
    "Builtin.ResponseRelevance",
    "Builtin.Conciseness",
    "Builtin.Coherence",
    "Builtin.InstructionFollowing",
    "Builtin.Refusal",
    "Builtin.Harmfulness",
    "Builtin.Stereotyping",
}


class AttributePrefixes:
    """OpenTelemetry 속성 접두사입니다."""

    GEN_AI = "gen_ai"
