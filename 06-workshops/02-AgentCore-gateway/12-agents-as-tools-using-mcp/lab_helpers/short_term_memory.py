"""
AgentCore Memory 통합용 ShortTermMemoryHook

이 모듈은 Amazon Bedrock AgentCore Memory를 사용해 Strands 에이전트의
단기 Memory를 자동 관리하는 재사용 가능한 hook provider를 제공합니다.

기능:
- 에이전트 초기화 시 대화 기록 자동 로드
- 메시지 추가 시 자동 저장
- 애플리케이션 context 삽입 지원
- 오류 처리 및 로깅
"""

import logging
from typing import Optional, List, Dict, Any

from strands.hooks import (
    AgentInitializedEvent,
    HookProvider,
    HookRegistry,
    MessageAddedEvent,
)
from bedrock_agentcore.memory import MemoryClient

# logger 구성
logger = logging.getLogger(__name__)


class ShortTermMemoryHook(HookProvider):
    """
    Strands 에이전트용 자동 Memory 관리 hook입니다.

    Amazon Bedrock AgentCore Memory를 Strands 에이전트와 통합하여 수동 개입 없이
    대화 기록을 불러오고 저장합니다.

    주요 기능:
    - 에이전트 초기화 시 최근 대화 turn 로드
    - 각 에이전트 호출 후 메시지 자동 저장
    - context 삽입을 위한 애플리케이션별 정보 추출
    - Memory 조회 및 오류 상황 처리

    인자:
        memory_client: AgentCore Memory 작업용 MemoryClient 인스턴스
        memory_id: AgentCore Memory 리소스 ID
        context_keywords: 애플리케이션 context 식별용 선택적 키워드 목록
        max_context_turns: 불러올 최근 turn의 최대 개수(기본값: 5)
        branch_name: 사용할 Memory branch 이름(기본값: "main")

    예:
        >>> memory_client = MemoryClient(region_name='us-west-2')
        >>> memory_hook = ShortTermMemoryHook(memory_client, memory_id="xyz-123")
        >>> agent = Agent(
        ...     hooks=[memory_hook],
        ...     model="global.anthropic.claude-sonnet-4-20250514-v1:0",
        ...     state={"actor_id": "user-123", "session_id": "session-456"}
        ... )
    """

    def __init__(
        self,
        memory_client: MemoryClient,
        memory_id: str,
        context_keywords: Optional[List[str]] = None,
        max_context_turns: int = 5,
        branch_name: str = "main",
    ):
        """ShortTermMemoryHook을 초기화합니다."""
        self.memory_client = memory_client
        self.memory_id = memory_id
        self.max_context_turns = max_context_turns
        self.branch_name = branch_name

        # 애플리케이션 context 식별용 기본 키워드
        self.context_keywords = context_keywords or [
            "Stack Name:",
            "EC2 Instance:",
            "Database:",
            "Application:",
            "Service:",
            "Configuration:",
            "Error:",
            "Status:",
            "Memory:",
            "CPU:",
        ]

        logger.debug(
            f"ShortTermMemoryHook initialized with memory_id={memory_id}, max_context_turns={max_context_turns}"
        )

    def on_agent_initialized(self, event: AgentInitializedEvent) -> None:
        """
        에이전트 초기화 시 최근 대화 기록을 불러옵니다.

        Strands 에이전트 초기화 시 호출됩니다. Memory에서 최근 대화 turn을 가져와
        애플리케이션별 정보를 우선하는 context로 에이전트의 system prompt에 삽입합니다.

        인자:
            event: 에이전트 인스턴스가 포함된 AgentInitializedEvent
        """
        try:
            # 에이전트 상태에서 actor 및 세션 식별자 추출
            actor_id = event.agent.state.get("actor_id")
            session_id = event.agent.state.get("session_id")

            if not actor_id or not session_id:
                logger.warning(
                    "Cannot load memory: Missing actor_id or session_id in agent state. "
                    f"actor_id={actor_id}, session_id={session_id}"
                )
                return

            logger.debug(f"Loading memory for actor_id={actor_id}, session_id={session_id}")

            # Memory에서 최근 대화 turn 가져오기
            recent_turns = self.memory_client.get_last_k_turns(
                memory_id=self.memory_id,
                actor_id=actor_id,
                session_id=session_id,
                k=self.max_context_turns,
                branch_name=self.branch_name,
            )

            if recent_turns:
                context = self._build_context_from_turns(recent_turns)
                event.agent.system_prompt += f"\n\n{context}\n\nUse this information for additional background context."
                logger.info(
                    f"✅ Loaded {len(recent_turns)} conversation turns into agent context (actor_id={actor_id})"
                )
            else:
                logger.info(f"No previous conversation history found for actor_id={actor_id}")

        except Exception as e:
            logger.error(
                f"Failed to load conversation history: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )

    def on_message_added(self, event: MessageAddedEvent) -> None:
        """
        메시지를 Memory에 자동 저장합니다.

        에이전트 메시지 기록에 사용자 입력이나 에이전트 응답이 추가될 때마다 호출됩니다.
        나중에 가져올 수 있도록 메시지를 AgentCore Memory에 저장합니다.

        인자:
            event: 에이전트와 새 메시지가 포함된 MessageAddedEvent
        """
        try:
            # 에이전트 상태 추출
            actor_id = event.agent.state.get("actor_id")
            session_id = event.agent.state.get("session_id")

            if not actor_id or not session_id:
                logger.warning("Cannot save message: Missing actor_id or session_id in agent state")
                return

            # 가장 최근 메시지 가져오기
            messages = event.agent.messages
            if not messages:
                logger.warning("No messages found to persist")
                return

            latest_message = messages[-1]
            message_role = latest_message.get("role", "unknown")

            # 메시지에서 텍스트 콘텐츠 추출
            message_content = latest_message.get("content", [])
            if isinstance(message_content, list) and message_content:
                message_text = message_content[0].get("text", "")
            else:
                message_text = str(message_content)

            # 빈 메시지는 건너뜀(텍스트가 비어 있으면 Memory에 저장하지 않음)
            if not message_text or not message_text.strip():
                logger.debug(f"Skipping empty message (role={message_role}) - no content to persist")
                return

            # Memory에 저장
            self.memory_client.create_event(
                memory_id=self.memory_id,
                actor_id=actor_id,
                session_id=session_id,
                messages=[(message_text, message_role)],
            )

            logger.debug(
                f"✅ Persisted message (role={message_role}, length={len(message_text)}) for actor_id={actor_id}"
            )

        except Exception as e:
            logger.error(
                f"Failed to persist message to memory: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )

    def register_hooks(self, registry: HookRegistry) -> None:
        """
        Strands 에이전트 hook 레지스트리에 hook을 등록합니다.

        Strands 프레임워크가 이 hook provider의 콜백을 에이전트 이벤트 시스템에
        등록할 때 호출합니다.

        인자:
            registry: 콜백을 등록할 HookRegistry 인스턴스
        """
        registry.add_callback(MessageAddedEvent, self.on_message_added)
        registry.add_callback(AgentInitializedEvent, self.on_agent_initialized)
        logger.debug("ShortTermMemoryHook callbacks registered with HookRegistry")

    def _build_context_from_turns(self, turns: List[List[Dict[str, Any]]]) -> str:
        """
        대화 turn에서 context 문자열을 생성합니다.

        더 나은 context를 위해 구조화된 애플리케이션 세부 정보를 우선하여
        애플리케이션별 정보와 최근 대화 기록을 추출합니다.

        인자:
            turns: 각각 메시지 목록이 포함된 대화 turn 목록

        반환:
            system prompt에 삽입할 형식화된 context 문자열
        """
        context_messages = []
        application_info = []

        # 각 turn을 처리하고 정보 추출
        for turn in turns:
            for message in turn:
                role = message.get("role", "").lower()
                content = message.get("content", {})

                # 다양한 콘텐츠 형식 처리
                if isinstance(content, dict):
                    text = content.get("text", "")
                elif isinstance(content, str):
                    text = content
                else:
                    text = str(content)

                # 키워드를 기반으로 애플리케이션 정보 추출
                is_application_info = any(keyword in text for keyword in self.context_keywords)

                if is_application_info and role == "assistant":
                    application_info.append(text)
                else:
                    context_messages.append(f"{role.title()}: {text}")

        # 애플리케이션 정보를 우선하여 최종 context 구성
        context_parts = []

        if application_info:
            context_parts.append("APPLICATION INFORMATION:")
            context_parts.extend(application_info)

        if context_messages:
            if application_info:
                context_parts.append("\nRECENT CONVERSATION:")
            # 최근 대화 메시지만 포함(마지막 6개)
            context_parts.extend(context_messages[-6:])

        return "\n".join(context_parts)
