from strands import Agent, tool, AgentSkills, Skill
from strands_tools import calculator
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp


@tool
def weather() -> dict:
    """Get current weather information."""
    return {
        "condition": "sunny",
        "temp_f": 75,
        "temp_c": 24,
        "humidity": 45,
        "wind_mph": 10,
    }


# 프로그래밍 방식의 skill - 인라인으로 정의하므로 SKILL.md 파일이 필요 없음
math_tutor = Skill(
    name="math-tutor",
    description="Solve math problems step-by-step, showing all work and explaining reasoning",
    instructions=(
        "You are a patient and thorough math tutor. When solving math problems:\n"
        "1. Break down the problem into clear, numbered steps.\n"
        "2. Show all intermediate calculations — never skip steps.\n"
        "3. Explain your reasoning at each step, identifying the mathematical concept applied.\n"
        "4. Use the calculator tool for arithmetic to ensure accuracy.\n"
        "5. Verify your answer against the original problem.\n"
        "6. Summarize with a clear final answer."
    ),
)

model = BedrockModel(model_id="global.anthropic.claude-haiku-4-5-20251001-v1:0")
# 파일 기반 skill(weather-reporter)과 프로그래밍 방식의 skill(math_tutor)을 함께 사용
skills = AgentSkills(skills=["./skills/weather-reporter", math_tutor])
agent = Agent(model=model, tools=[calculator, weather], plugins=[skills])

app = BedrockAgentCoreApp()


@app.entrypoint
def invoke_agent(payload: dict) -> str:
    response = agent(payload.get("prompt", ""))
    return response.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()
