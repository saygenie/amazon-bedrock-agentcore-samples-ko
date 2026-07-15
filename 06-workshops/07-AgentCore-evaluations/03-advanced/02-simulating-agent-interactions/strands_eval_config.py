# 평가 구성
# 평가 설정을 사용자 지정하려면 아래 값을 편집하세요.

# AWS 구성
AWS_REGION = "us-east-1"

# Runtime에 배포된 agent의 AgentCore 구성
# TODO: <YOUR_ACCOUNT_ID>와 <YOUR_AGENT_NAME>을 실제 값으로 바꾸세요.
AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:<YOUR_ACCOUNT_ID>:runtime/<YOUR_AGENT_NAME>"
QUALIFIER = "DEFAULT"
LOG_GROUP_NAME = "/aws/bedrock-agentcore/runtimes/<YOUR_AGENT_NAME>-DEFAULT"
SERVICE_NAME = "<YOUR_AGENT_NAME>.DEFAULT"

# Online API를 사용하는 AgentCore Evaluators의 평가 구성
EVAL_CONFIG_NAME = "actor_simulator_online_eval"
EVAL_DESCRIPTION = "Online evaluation for actor simulator test cases with builtin metrics"
# TODO: <YOUR_ACCOUNT_ID>를 실제 AWS 계정 ID로 바꾸세요.
EVALUATION_ROLE_ARN = "arn:aws:iam::<YOUR_ACCOUNT_ID>:role/AgentCoreEvaluationRole"
SAMPLING_PERCENTAGE = 100.0
SESSION_TIMEOUT_MINUTES = 5
EVALUATION_ENDPOINT_URL = "https://bedrock-agentcore-control.us-east-1.amazonaws.com"

# Builtin Evaluators - 필요에 따라 추가하거나 제거
EVALUATORS = [
    "Builtin.Helpfulness",
    "Builtin.ToolSelectionAccuracy",
    "Builtin.Faithfulness",
    "Builtin.GoalSuccessRate",
    "Builtin.ToolParameterAccuracy",
    "Builtin.Correctness",
]

# strands eval 데이터 세트 생성기용 에이전트 컨텍스트
AGENT_CAPABILITIES = "Simple arithmetic: addition, subtraction, multiplication, division"
AGENT_LIMITATIONS = "Cannot solve trigonometry, calculus, linear algebra, or multi-step word problems"
AGENT_TOOLS = ["calculator"]
AGENT_TOPICS = ["basic mathematics", "simple arithmetic", "number comparison"]
AGENT_COMPLEXITY = "single-step or two-step calculations only"

# strands eval actor simulator용 테스트 생성 설정
NUM_TEST_CASES = 10
MAX_TURNS = 7
