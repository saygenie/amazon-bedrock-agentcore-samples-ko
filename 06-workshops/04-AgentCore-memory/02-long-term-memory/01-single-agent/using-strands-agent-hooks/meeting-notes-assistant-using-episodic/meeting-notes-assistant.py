"""
AgentCore Episodic Memory - 회의록 어시스턴트

이 튜토리얼에서는 AgentCore Episodic Memory와 통합된 Strands agent를 사용하여
회의록 어시스턴트를 구축하는 방법을 설명합니다. Agent는 과거 회의에서 학습하고
결정 사항, 할당된 작업 항목, 참가자 선호도를 기억하여 반복되는 회의 전반에 걸쳐
컨텍스트를 인식하는 지원을 제공할 수 있습니다.

튜토리얼 세부 정보:
- 튜토리얼 유형: Long term Episodic
- Agent 유형: 회의록 어시스턴트
- Agentic Framework: Strands Agents
- LLM 모델: Anthropic Claude Haiku 4.5
- 구성 요소: Reflections가 포함된 AgentCore Episodic Memory

학습 내용:
- Episodic Strategy를 사용한 AgentCore Memory 설정
- 자동 에피소드 캡처를 위한 Memory hook 생성
- 과거 회의 에피소드와 Reflection 검색
- 회의 패턴과 참가자 선호도를 학습하는 Agent 구축
"""

# %% [markdown]
# ## 1단계: 종속성 설치 및 설정

# %%
# !pip install -qr requirements.txt

# %%
import json
import logging
from datetime import datetime
from typing import Dict

from botocore.exceptions import ClientError
from strands import Agent, tool
from strands.hooks import (
    AfterInvocationEvent,
    HookProvider,
    HookRegistry,
    MessageAddedEvent,
)

from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.constants import StrategyType

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("meeting-notes-assistant")

# %%
# 구성
REGION = "us-west-2"
PARTICIPANT_ID = "participant_001"
SESSION_ID = f"meeting_{datetime.now().strftime('%Y%m%d%H%M%S')}"

# %% [markdown]
# ## 2단계: Episodic Strategy를 사용한 Memory 리소스 생성
#
# Episodic Strategy는 다음을 자동으로 수행합니다.
# - 대화에서 에피소드가 완료되는 시점 감지
# - 구조화된 에피소드 레코드(상황, 의도, 평가, 근거) 추출
# - 에피소드 전반의 패턴을 식별하는 Reflection 생성

# %%
client = MemoryClient(region_name=REGION)
memory_name = "MeetingNotesEpisodicMemory"

# Episodic Memory Strategy 정의
strategies = [
    {
        StrategyType.EPISODIC.value: {
            "name": "MeetingEpisodes",
            "description": "Captures meeting discussions and generates reflections on meeting patterns",
            "namespaceTemplates": ["/meetings/actor/{actorId}/episodes/"],
            "reflectionConfiguration": {"namespaceTemplates": ["/meetings/actor/{actorId}/"]},
        }
    }
]

# Memory 리소스 생성
try:
    memory = client.create_memory_and_wait(
        name=memory_name,
        strategies=strategies,
        description="Episodic memory for meeting notes assistant",
        event_expiry_days=180,  # 에피소드를 6개월 동안 보관
    )
    memory_id = memory["id"]
    logger.info(f"✅ Created memory: {memory_id}")
except ClientError as e:
    if e.response["Error"]["Code"] == "ValidationException" and "already exists" in str(e):
        memories = client.list_memories()
        memory_id = next((m["id"] for m in memories if m["id"].startswith(memory_name)), None)
        logger.info(f"Memory already exists. Using: {memory_id}")
    else:
        raise
except Exception as e:
    logger.error(f"❌ ERROR: {e}")
    raise

# %%
# Episodic Strategy 구성 확인
strategies = client.get_memory_strategies(memory_id)
print(json.dumps(strategies, indent=2, default=str))

# %% [markdown]
# ## 3단계: 회의 관리 도구 생성


# %%
@tool
def capture_action_item(task: str, owner: str, due_date: str) -> str:
    """Capture an action item from the meeting discussion.

    Args:
        task: Description of the task to be completed
        owner: Person responsible for completing the task
        due_date: When the task should be completed

    Returns:
        Confirmation of action item capture with details
    """
    action_items = {
        "website": "Website redesign - assigned to Sarah, due next Friday",
        "budget": "Review Q3 budget allocation - assigned to Mike, due this week",
        "presentation": "Prepare stakeholder presentation - assigned to Alex, due Monday",
        "testing": "Complete user testing for new feature - assigned to QA team, due end of sprint",
    }

    # 작업 항목 저장 시뮬레이션
    for keyword, stored_item in action_items.items():
        if keyword in task.lower():
            return f"✅ ACTION ITEM CAPTURED:\n{stored_item}\n\nNote: {task}"

    return f"✅ ACTION ITEM CAPTURED:\nTask: {task}\nOwner: {owner}\nDue: {due_date}"


@tool
def identify_decision(decision: str, context: str) -> str:
    """Identify and record a key decision made during the meeting.

    Args:
        decision: The decision that was made
        context: Context or reasoning behind the decision

    Returns:
        Confirmation of decision recording with summary
    """
    decisions = {
        "budget": "Approved Q3 marketing budget increase of 15%",
        "launch": "Product launch date set for November 15th",
        "vendor": "Selected AWS as cloud infrastructure provider",
        "process": "Adopted agile sprint methodology for project management",
    }

    # 결정 사항 기록 시뮬레이션
    for keyword, stored_decision in decisions.items():
        if keyword in decision.lower():
            return f"📌 DECISION RECORDED:\n{stored_decision}\n\nRationale: {context}"

    return f"📌 DECISION RECORDED:\n{decision}\n\nContext: {context}"


@tool
def summarize_discussion(topic: str, key_points: str) -> str:
    """Summarize a discussion topic with key points.

    Args:
        topic: The discussion topic
        key_points: Main points covered in the discussion

    Returns:
        Structured summary of the discussion
    """
    # 토론 요약 시뮬레이션
    return f"""📝 DISCUSSION SUMMARY:

Topic: {topic}

Key Points:
{key_points}

Next Steps: Review in next meeting"""


@tool
def track_followup(previous_item: str, status: str) -> str:
    """Track follow-up status of previous action items or decisions.

    Args:
        previous_item: Description of the item to follow up on
        status: Current status (completed, in-progress, blocked, pending)

    Returns:
        Follow-up status with details
    """
    # 후속 조치 추적 시뮬레이션
    statuses = {
        "completed": "✅ COMPLETED",
        "in-progress": "🔄 IN PROGRESS",
        "blocked": "🚫 BLOCKED",
        "pending": "⏳ PENDING",
    }

    status_emoji = statuses.get(status.lower(), "❓ UNKNOWN")

    return f"""{status_emoji}
Item: {previous_item}
Status: {status}
Last Updated: {datetime.now().strftime("%Y-%m-%d")}"""


logger.info("✅ Meeting management tools ready")

# %% [markdown]
# ## 4단계: Episodic Memory Hook Provider 생성
#
# Hook Provider는 다음을 수행합니다.
# - 쿼리를 처리하기 전에 관련된 과거 회의 에피소드와 Reflection 검색
# - 에피소드 추출을 위해 회의 상호 작용을 이벤트로 저장
# - AgentCore가 에피소드를 자동으로 감지하고 추출


# %%
def get_namespaces(mem_client: MemoryClient, memory_id: str) -> Dict:
    """Memory Strategy의 네임스페이스 매핑을 가져옵니다."""
    strategies = mem_client.get_memory_strategies(memory_id)
    result = {}
    for strategy in strategies:
        reflection_config = strategy.get("reflectionConfiguration", {})
        result[strategy["type"]] = {
            "namespaces": strategy.get("namespaces", []),
            "reflectionNamespaces": reflection_config.get("namespaces", []),
        }
    return result


class EpisodicMemoryHooks(HookProvider):
    """Reflection이 포함된 Episodic Memory용 Memory hook입니다."""

    def __init__(self, memory_id: str, client: MemoryClient):
        self.memory_id = memory_id
        self.client = client
        self.namespaces = get_namespaces(self.client, self.memory_id)

    def retrieve_episodes_and_reflections(self, event: MessageAddedEvent):
        """처리 전에 관련 에피소드와 Reflection을 검색합니다."""
        messages = event.agent.messages
        if messages[-1]["role"] != "user" or "toolResult" in messages[-1]["content"][0]:
            return

        user_query = messages[-1]["content"][0]["text"]
        actor_id = event.agent.state.get("actor_id")

        if not actor_id:
            logger.warning("Missing actor_id in agent state")
            return

        try:
            all_context = []
            episodic_config = self.namespaces.get("EPISODIC", {})

            # 관련 에피소드 검색("intent"로 인덱싱됨)
            for namespace_template in episodic_config.get("namespaces", []):
                namespace = namespace_template.format(actorId=actor_id)
                episodes = self.client.retrieve_memories(
                    memory_id=self.memory_id,
                    namespace=namespace,
                    query=user_query,  # 에피소드는 intent로 인덱싱됨
                    top_k=3,
                )

                for episode in episodes:
                    if isinstance(episode, dict):
                        content = episode.get("content", {})
                        if isinstance(content, dict):
                            text = content.get("text", "").strip()
                            if text:
                                all_context.append(f"[PAST EPISODE] {text}")

            # Reflection 검색("use case"로 인덱싱됨)
            for namespace_template in episodic_config.get("reflectionNamespaces", []):
                namespace = namespace_template.format(actorId=actor_id)
                reflections = self.client.retrieve_memories(
                    memory_id=self.memory_id,
                    namespace=namespace,
                    query=user_query,  # Reflection은 use case로 인덱싱됨
                    top_k=2,
                )

                for reflection in reflections:
                    if isinstance(reflection, dict):
                        content = reflection.get("content", {})
                        if isinstance(content, dict):
                            text = content.get("text", "").strip()
                            if text:
                                all_context.append(f"[REFLECTION] {text}")

            # 쿼리에 컨텍스트 주입
            if all_context:
                context_text = "\n".join(all_context)
                original_text = messages[-1]["content"][0]["text"]
                messages[-1]["content"][0]["text"] = (
                    f"Past Experience:\n{context_text}\n\nCurrent Query: {original_text}"
                )
                logger.info(f"Retrieved {len(all_context)} episodes/reflections")

        except Exception as e:
            logger.error(f"Failed to retrieve episodes: {e}")

    def save_meeting_interaction(self, event: AfterInvocationEvent):
        """에피소드 추출을 위해 회의 상호 작용을 저장합니다."""
        try:
            messages = event.agent.messages
            if len(messages) < 2 or messages[-1]["role"] != "assistant":
                return

            # 도구 사용을 포함한 전체 상호 작용 수집
            interaction_messages = []
            for msg in messages:
                role = msg["role"].upper()
                content = msg["content"]

                if isinstance(content, list):
                    for item in content:
                        if "text" in item:
                            interaction_messages.append((item["text"], role))
                        elif "toolUse" in item:
                            # 더 나은 에피소드 추출을 위해 도구 사용 내역 포함
                            tool_info = item["toolUse"]
                            tool_text = f"[TOOL: {tool_info.get('name', 'unknown')}]"
                            interaction_messages.append((tool_text, "TOOL"))
                        elif "toolResult" in item:
                            result = item["toolResult"].get("content", [{}])[0].get("text", "")
                            interaction_messages.append((f"[RESULT: {result[:200]}]", "TOOL"))

            if interaction_messages:
                actor_id = event.agent.state.get("actor_id")
                session_id = event.agent.state.get("session_id")

                if not actor_id or not session_id:
                    logger.warning("Missing actor_id or session_id")
                    return

                # 이벤트 저장 - AgentCore가 에피소드 완료를 자동으로 감지
                self.client.create_event(
                    memory_id=self.memory_id,
                    actor_id=actor_id,
                    session_id=session_id,
                    messages=interaction_messages,
                )
                logger.info("Saved meeting interaction for episode extraction")

        except Exception as e:
            logger.error(f"Failed to save interaction: {e}")

    def register_hooks(self, registry: HookRegistry) -> None:
        """Episodic Memory hook을 등록합니다."""
        registry.add_callback(MessageAddedEvent, self.retrieve_episodes_and_reflections)
        registry.add_callback(AfterInvocationEvent, self.save_meeting_interaction)
        logger.info("Episodic memory hooks registered")


# %% [markdown]
# ## 5단계: 회의록 Agent 생성

# %%
episodic_hooks = EpisodicMemoryHooks(memory_id, client)

meeting_agent = Agent(
    hooks=[episodic_hooks],
    model="global.anthropic.claude-haiku-4-5-20251001-v1:0",
    tools=[
        capture_action_item,
        identify_decision,
        summarize_discussion,
        track_followup,
    ],
    state={"actor_id": PARTICIPANT_ID, "session_id": SESSION_ID},
    system_prompt="""You are an expert meeting assistant with memory of past meetings.

Your role:
- Help facilitate productive meetings by tracking decisions and action items
- Use past meeting episodes to provide relevant context and history
- Apply reflections about what works well for different teams and participants
- Remember participant preferences and communication styles

When you see [PAST EPISODE] context, use it to inform your responses.
When you see [REFLECTION] context, apply those learned patterns.

Always:
1. Listen for key decisions and action items
2. Reference relevant past meetings when helpful
3. Track follow-ups on previous action items
4. Summarize discussions clearly and concisely""",
)

print("✅ Meeting notes agent created with episodic memory")

# %% [markdown]
# ## 6단계: 과거 회의 에피소드 시드
#
# Episodic Memory를 시연하기 위해 이전 회의 세션을 추가합니다.

# %%
# 이전 회의 세션으로 시드
past_sessions = [
    # 세션 1: Sprint 계획 회의
    ("Let's plan the Q3 sprint. We need to prioritize features.", "USER"),
    ("I'll help capture the key decisions and action items.", "ASSISTANT"),
    (
        "We should focus on the user authentication feature first. It's blocking other work.",
        "USER",
    ),
    ("[TOOL: identify_decision]", "TOOL"),
    (
        "[RESULT: 📌 DECISION RECORDED: Prioritize user authentication feature for Q3 sprint]",
        "TOOL",
    ),
    (
        "Noted. User authentication is the priority. Who will lead this?",
        "ASSISTANT",
    ),
    (
        "Sarah can handle the authentication work. She has experience with OAuth.",
        "USER",
    ),
    ("[TOOL: capture_action_item]", "TOOL"),
    (
        "[RESULT: ✅ ACTION ITEM CAPTURED: Implement user authentication - Sarah - Due: End of sprint]",
        "TOOL",
    ),
    (
        "Perfect! I've captured that Sarah will implement user authentication by end of sprint.",
        "ASSISTANT",
    ),
    # 세션 2: 예산 검토 회의
    (
        "We need to discuss the Q3 marketing budget. Costs are higher than expected.",
        "USER",
    ),
    ("Let me help track this discussion.", "ASSISTANT"),
    ("[TOOL: summarize_discussion]", "TOOL"),
    (
        "[RESULT: 📝 DISCUSSION SUMMARY: Q3 marketing budget - costs exceeding projections]",
        "TOOL",
    ),
    (
        "I propose we increase the budget by 15% to account for the new campaigns.",
        "USER",
    ),
    ("[TOOL: identify_decision]", "TOOL"),
    (
        "[RESULT: 📌 DECISION RECORDED: Approved Q3 marketing budget increase of 15%]",
        "TOOL",
    ),
    (
        "Decision captured. Is there a follow-up needed?",
        "ASSISTANT",
    ),
    ("Yes, Mike needs to update the financial forecast by end of week.", "USER"),
    ("[TOOL: capture_action_item]", "TOOL"),
    (
        "[RESULT: ✅ ACTION ITEM CAPTURED: Update financial forecast - Mike - Due: End of week]",
        "TOOL",
    ),
]

try:
    client.create_event(
        memory_id=memory_id,
        actor_id=PARTICIPANT_ID,
        session_id="seed_session_001",
        messages=past_sessions,
    )
    print("✅ Seeded past meeting episodes")
    print("⏳ Note: Episode extraction happens in background (~1 minute)")
except Exception as e:
    print(f"⚠️ Error seeding history: {e}")

# %% [markdown]
# ## 7단계: 회의 시나리오 테스트
#
# 이제 Agent가 과거 에피소드와 Reflection을 활용해야 합니다.

# %%
# 테스트 1: 이전 결정에 대한 후속 조치 - 과거 에피소드를 참조해야 함
response1 = meeting_agent("Let's revisit the Q3 sprint priorities we discussed last week. What was decided?")
print(f"Agent: {response1}")

# %%
# 테스트 2: 작업 항목 확인 - 과거 작업 항목을 검색해야 함
response2 = meeting_agent("Did we assign someone to handle the user authentication feature?")
print(f"Agent: {response2}")

# %%
# 테스트 3: 예산 후속 조치 - 과거 예산 논의를 참조해야 함
response3 = meeting_agent("What was the outcome of the Q3 marketing budget discussion?")
print(f"Agent: {response3}")

# %%
# 테스트 4: 여러 작업 항목이 있는 새 회의
response4 = meeting_agent("""
We're having a product launch planning meeting. Key points:
- Launch date: November 15th
- Marketing team needs 2 weeks prep time
- Sarah will coordinate with vendors
- Mike needs to finalize pricing by next Friday

Can you capture the decisions and action items?
""")
print(f"Agent: {response4}")

# %%
# 테스트 5: 패턴 인식 - Agent가 참가자 선호도를 기억해야 함
response5 = meeting_agent("Sarah wants to discuss technical architecture for the new feature. What format works best?")
print(f"Agent: {response5}")

# %%
# 테스트 6: 완전히 새로운 주제 - 과거 컨텍스트 없음
response6 = meeting_agent(
    "We need to discuss the company's sustainability initiative for the first time. Let's brainstorm ideas."
)
print(f"Agent: {response6}")

# %% [markdown]
# ## 8단계: 에피소드 저장 확인

# %%
print("\n📚 Episodic Memory Summary:")
print("=" * 50)

episodic_config = get_namespaces(client, memory_id).get("EPISODIC", {})

# 에피소드 확인
for namespace_template in episodic_config.get("namespaces", []):
    namespace = namespace_template.format(actorId=PARTICIPANT_ID)

    try:
        episodes = client.retrieve_memories(
            memory_id=memory_id,
            namespace=namespace,
            query="meeting decisions action items",
            top_k=5,
        )

        print(f"\nEPISODES ({len(episodes)} found):")
        for i, episode in enumerate(episodes, 1):
            if isinstance(episode, dict):
                content = episode.get("content", {})
                if isinstance(content, dict):
                    text = content.get("text", "")[:200] + "..."
                    print(f"  {i}. {text}")

    except Exception as e:
        print(f"Error retrieving episodes: {e}")

# Reflection 확인
for namespace_template in episodic_config.get("reflectionNamespaces", []):
    namespace = namespace_template.format(actorId=PARTICIPANT_ID)

    try:
        reflections = client.retrieve_memories(
            memory_id=memory_id,
            namespace=namespace,
            query="meeting patterns effectiveness",
            top_k=3,
        )

        print(f"\nREFLECTIONS ({len(reflections)} found):")
        for i, reflection in enumerate(reflections, 1):
            if isinstance(reflection, dict):
                content = reflection.get("content", {})
                if isinstance(content, dict):
                    text = content.get("text", "")[:200] + "..."
                    print(f"  {i}. {text}")

    except Exception as e:
        print(f"Error retrieving reflections: {e}")

print("\n" + "=" * 50)

# %% [markdown]
# ## 핵심 요점
#
# 1. **Episodic Memory는 단순한 사실이 아니라 상호 작용 순서를 캡처합니다.**
# 2. 여러 에피소드를 분석하면 **Reflection이 자동으로 생성됩니다.**
# 3. 더 풍부한 에피소드 추출을 위해 이벤트에 **도구 결과를 포함합니다.**
# 4. 에피소드는 **intent로 쿼리**하고, Reflection은 **use case로 쿼리**합니다.
# 5. **에피소드 추출은 비동기식**입니다(대화 종료 후 약 1분).
#
# ## 정리

# %%
# Memory 리소스를 삭제하려면 주석 해제
# try:
#     client.delete_memory_and_wait(memory_id=memory_id)
#     print(f"✅ Deleted memory resource: {memory_id}")
# except Exception as e:
#     print(f"Error deleting memory: {e}")
