#!/usr/bin/env python3
"""
AgentCore Memory Dashboard Backend - Memory 레코드 목록 전용
시맨틱 검색 없이 모든 Memory 레코드를 나열하는 간단한 접근 방식
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from typing import Optional, List, Dict, Any
import os
import logging
from datetime import datetime
from bedrock_agentcore.memory import MemoryClient
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()


def get_namespaces(mem_client: MemoryClient, memory_id: str) -> Dict:
    """Memory Strategy의 네임스페이스 매핑을 가져옵니다."""
    strategies = mem_client.get_memory_strategies(memory_id)
    return {i["type"]: i["namespaces"][0] for i in strategies}


def clean_aws_error_message(error_message: str) -> str:
    """ARN과 민감한 정보를 제거하여 AWS 오류 메시지를 정리합니다."""
    import re

    # ARN 패턴 제거(arn:aws:...)
    error_message = re.sub(r"arn:aws:[^:\s]+:[^:\s]*:[^:\s]*:[^\s]+", "[AWS Resource]", error_message)

    # 계정 ID(12자리 숫자) 제거
    error_message = re.sub(r"\b\d{12}\b", "[Account]", error_message)

    # 일반적인 AWS 오류 패턴 정리
    if "AccessDeniedException" in error_message:
        if "bedrock-agentcore:GetMemory" in error_message:
            return "Access denied: Missing required permission 'bedrock-agentcore:GetMemory'. Please check your IAM permissions."
        elif "bedrock-agentcore" in error_message:
            return "Access denied: Missing required Bedrock AgentCore permissions. Please check your IAM permissions."
        else:
            return "Access denied: Insufficient permissions. Please check your AWS credentials and IAM permissions."

    if "ResourceNotFoundException" in error_message or "not found" in error_message.lower():
        return "Resource not found. Please verify the Memory ID exists and is accessible."

    if "ValidationException" in error_message:
        return "Invalid request parameters. Please check your Memory ID format."

    # 정리된 메시지 반환
    return error_message


# 로깅 구성
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AgentCore Memory Dashboard API - List Only",
    description="Simple backend to list all memory records",
    version="1.0.0",
)

# React 프런트엔드용 CORS 구성
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 구성
MEMORY_ID = os.getenv("AGENTCORE_MEMORY_ID")  # 기본값 없음 - 사용자가 제공해야 함


# AWS 리전 감지 - 여러 소스 시도
def get_aws_region():
    """환경, AWS CLI 구성 또는 기본값에서 AWS 리전을 가져옵니다."""
    # 1. 환경 변수 먼저 확인
    region = os.getenv("AWS_REGION")
    if region:
        logger.info(f"Using AWS region from environment: {region}")
        return region

    # 2. AWS CLI 구성에서 가져오기 시도
    try:
        import subprocess  # nosec B404 - subprocess 사용이 필요하며 적절하게 보호됨
        import shutil

        # 보안: PATH 하이재킹을 방지하도록 aws 실행 파일의 전체 경로 사용(B607)
        aws_path = shutil.which("aws")
        if aws_path:
            # 보안: 명령 삽입을 방지하도록 전체 경로를 포함한 목록 형식 사용(B603)
            # PATH 조작을 방지하도록 aws_path가 절대 경로인지 검증
            if not aws_path.startswith("/"):
                logger.warning(f"AWS CLI path is not absolute: {aws_path}, skipping")
            else:
                # 검증된 전체 경로와 하드코딩된 인수만 사용하며 사용자 입력은 사용하지 않음
                result = subprocess.run(  # nosec B603
                    [aws_path, "configure", "get", "region"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,  # 0이 아닌 반환 코드에서 예외를 발생시키지 않음
                )
                if result.returncode == 0 and result.stdout.strip():
                    region = result.stdout.strip()
                    logger.info(f"Using AWS region from CLI config: {region}")
                    return region
        else:
            logger.debug("AWS CLI not found in PATH")
    except Exception as e:
        logger.debug(f"Could not get region from AWS CLI: {e}")

    # 3. boto3 세션에서 가져오기 시도(AWS_DEFAULT_REGION, profile 등을 따름)
    try:
        import boto3

        session = boto3.Session()
        region = session.region_name
        if region:
            logger.info(f"Using AWS region from boto3 session: {region}")
            return region
    except Exception as e:
        logger.debug(f"Could not get region from boto3 session: {e}")

    # 4. 기본값으로 대체
    logger.warning("No AWS region configured, using default: us-east-1")
    return "us-east-1"


AWS_REGION = get_aws_region()

# AgentCore Memory 클라이언트 초기화
try:
    memory_client = MemoryClient()
    logger.info("✅ AgentCore Memory client initialized")
except Exception as e:
    logger.error(f"❌ Failed to initialize AgentCore Memory client: {e}")
    memory_client = None


class MemoryQuery(BaseModel):
    namespace: Optional[str] = None
    max_results: Optional[int] = 50
    memory_id: Optional[str] = None


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "memory_client": memory_client is not None,
        "default_memory_id": MEMORY_ID,
        "region": AWS_REGION,
        "region_source": "auto-detected from AWS configuration",
        "requires_memory_id": MEMORY_ID is None,
        "timestamp": datetime.now().isoformat() + "Z",
    }


class ShortTermMemoryQuery(BaseModel):
    actor_id: str
    session_id: str
    max_results: Optional[int] = 20
    memory_id: Optional[str] = None
    # 기존 필터
    event_type: Optional[str] = "all"
    role_filter: Optional[str] = "all"
    sort_by: Optional[str] = "timestamp"
    sort_order: Optional[str] = "desc"
    # 필수 필터만 포함
    content_search: Optional[str] = None


class LongTermMemoryQuery(BaseModel):
    namespace: str  # 필수 필드
    max_results: Optional[int] = 20
    memory_id: Optional[str] = None
    content_type: Optional[str] = "all"
    sort_by: Optional[str] = "timestamp"
    sort_order: Optional[str] = "desc"

    @field_validator("namespace")
    @classmethod
    def namespace_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Namespace cannot be empty")
        return v.strip()


def apply_short_term_filters(memories: List[Dict[str, Any]], query: ShortTermMemoryQuery) -> List[Dict[str, Any]]:
    """Short-term Memory 결과에 클라이언트 측 필터를 적용합니다."""
    filtered_memories = memories.copy()

    # 콘텐츠 검색 필터링
    if query.content_search and query.content_search.strip():
        search_term = query.content_search.strip().lower()
        filtered_memories = [m for m in filtered_memories if search_term in m.get("content", "").lower()]

    # Role 필터링(기존)
    if query.role_filter != "all":
        filtered_memories = [m for m in filtered_memories if m.get("role", "").upper() == query.role_filter.upper()]

    # 이벤트 유형 필터링(기존)
    if query.event_type != "all":
        filtered_memories = [m for m in filtered_memories if m.get("type", "") == query.event_type]

    # 일관된 문자열 변환을 사용한 단순 정렬
    reverse_order = query.sort_order == "desc"

    if query.sort_by == "timestamp":
        # 일관된 정렬을 위해 모든 타임스탬프를 문자열로 변환
        filtered_memories.sort(key=lambda x: str(x.get("timestamp", "")), reverse=reverse_order)
    elif query.sort_by == "size":
        filtered_memories.sort(key=lambda x: int(x.get("size", 0)), reverse=reverse_order)

    return filtered_memories


@app.post("/api/agentcore/getShortTermMemory")
async def get_short_term_memory(query: ShortTermMemoryQuery):
    """Get short-term memory (events and conversation turns) from AgentCore Memory"""
    try:
        if not memory_client:
            raise HTTPException(status_code=503, detail="AgentCore Memory client not available")

        # 제공된 memory_id를 사용하고, 없으면 환경 기본값으로 대체
        memory_id = query.memory_id or MEMORY_ID

        if not memory_id:
            raise HTTPException(
                status_code=400,
                detail="Memory ID is required. Please provide memory_id in request or set AGENTCORE_MEMORY_ID environment variable.",
            )

        short_term_memories = []

        logger.info(f"Fetching short-term memory for actor_id='{query.actor_id}', session_id='{query.session_id}'")
        logger.info(f"📋 Memory ID: {memory_id}")
        logger.info(f"📋 Max results: {query.max_results}")

        # 방법 1: ListEvents API 시도
        try:
            logger.info("📞 Using ListEvents API")
            events = memory_client.list_events(
                memory_id=memory_id,
                actor_id=query.actor_id,
                session_id=query.session_id,
                max_results=query.max_results,
            )

            if events:
                logger.info(f"✅ Found {len(events)} events")

                for event_idx, event in enumerate(events):
                    payload = event.get("payload", {})
                    content_text = ""

                    # MemoryClient.list_events의 실제 payload 구조 처리
                    if isinstance(payload, list) and len(payload) > 0:
                        # Payload가 목록이면 첫 번째 항목 가져오기
                        first_item = payload[0]
                        if isinstance(first_item, dict):
                            # 대화 콘텐츠 찾기
                            if "conversational" in first_item:
                                conversational = first_item["conversational"]
                                if isinstance(conversational, dict):
                                    content = conversational.get("content", {})
                                    if isinstance(content, dict) and "text" in content:
                                        content_text = content["text"]
                                    else:
                                        content_text = str(conversational)
                            else:
                                # 임의의 content 필드로 대체
                                if "content" in first_item:
                                    content = first_item["content"]
                                    if isinstance(content, dict) and "text" in content:
                                        content_text = content["text"]
                                    else:
                                        content_text = str(content)
                                else:
                                    content_text = str(first_item)
                        else:
                            content_text = str(first_item)
                    elif isinstance(payload, dict):
                        # 딕셔너리 payload 처리
                        if "content" in payload:
                            content = payload["content"]
                            if isinstance(content, dict) and "text" in content:
                                content_text = content["text"]
                            else:
                                content_text = str(content)
                        elif "message" in payload:
                            content_text = str(payload["message"])
                        else:
                            content_text = str(payload)
                    else:
                        content_text = str(payload)

                    memory_entry = {
                        "id": f"event-{event_idx}",
                        "content": content_text,
                        "type": "event",
                        "memory_type": "SHORT_TERM",
                        "actor_id": query.actor_id,
                        "session_id": query.session_id,
                        "event_id": event.get("eventId", f"event-{event_idx}"),
                        "event_type": event.get("eventType", "unknown"),
                        "timestamp": str(event.get("eventTimestamp", datetime.now().isoformat() + "Z")),
                        "size": len(content_text),
                    }
                    short_term_memories.append(memory_entry)

        except Exception as e:
            error_msg = str(e).lower()
            logger.warning(f"ListEvents failed for {query.actor_id}/{query.session_id}: {e}")
            logger.warning(f"ListEvents error type: {type(e).__name__}")

            # ARN과 민감한 정보를 제거하도록 오류 메시지 정리
            clean_error = clean_aws_error_message(str(e))

            # 특정 Memory ID를 찾을 수 없음 오류인지 확인
            if any(
                keyword in error_msg
                for keyword in [
                    "not found",
                    "does not exist",
                    "invalid memory",
                    "memory id",
                    "resourcenotfoundexception",
                ]
            ):
                logger.error(f"❌ Memory ID '{memory_id}' not found or inaccessible")
                raise HTTPException(
                    status_code=404,
                    detail=f"Memory ID '{memory_id}' not found. Please verify the Memory ID exists and you have access permissions.",
                )
            elif any(
                keyword in error_msg
                for keyword in [
                    "access denied",
                    "unauthorized",
                    "permission",
                    "accessdeniedexception",
                ]
            ):
                logger.error(f"❌ Access denied for Memory ID '{memory_id}'")
                raise HTTPException(status_code=403, detail=clean_error)

        # 방법 2: get_last_k_turns 시도
        try:
            logger.info("🔄 Using get_last_k_turns API")
            recent_turns = memory_client.get_last_k_turns(
                memory_id=memory_id,
                actor_id=query.actor_id,
                session_id=query.session_id,
                k=query.max_results or 10,
            )

            if recent_turns:
                logger.info(f"✅ Found {len(recent_turns)} conversation turns")

                for turn_idx, turn in enumerate(recent_turns):
                    for message_idx, message in enumerate(turn):
                        content = message.get("content", {})
                        if isinstance(content, dict):
                            content_text = content.get("text", str(content))
                        else:
                            content_text = str(content)

                        memory_entry = {
                            "id": f"turn-{turn_idx}-{message_idx}",
                            "content": content_text,
                            "type": "conversation",
                            "memory_type": "SHORT_TERM",
                            "actor_id": query.actor_id,
                            "session_id": query.session_id,
                            "role": message.get("role", "unknown"),
                            "turn_index": turn_idx,
                            "message_index": message_idx,
                            "timestamp": datetime.now().isoformat() + "Z",
                            "size": len(content_text),
                        }
                        short_term_memories.append(memory_entry)

        except Exception as e:
            error_msg = str(e).lower()
            logger.warning(f"get_last_k_turns failed for {query.actor_id}/{query.session_id}: {e}")
            logger.warning(f"get_last_k_turns error type: {type(e).__name__}")

            # ARN과 민감한 정보를 제거하도록 오류 메시지 정리
            clean_error = clean_aws_error_message(str(e))

            # 특정 Memory ID를 찾을 수 없음 오류인지 확인
            if any(
                keyword in error_msg
                for keyword in [
                    "not found",
                    "does not exist",
                    "invalid memory",
                    "memory id",
                    "resourcenotfoundexception",
                ]
            ):
                logger.error(f"❌ Memory ID '{memory_id}' not found or inaccessible")
                raise HTTPException(
                    status_code=404,
                    detail=f"Memory ID '{memory_id}' not found. Please verify the Memory ID exists and you have access permissions.",
                )
            elif any(
                keyword in error_msg
                for keyword in [
                    "access denied",
                    "unauthorized",
                    "permission",
                    "accessdeniedexception",
                ]
            ):
                logger.error(f"❌ Access denied for Memory ID '{memory_id}'")
                raise HTTPException(status_code=403, detail=clean_error)

        logger.info(f"✅ Total short-term memories found: {len(short_term_memories)}")

        # 필터 적용
        filtered_memories = apply_short_term_filters(short_term_memories, query)
        logger.info(f"🔍 After filtering: {len(filtered_memories)} memories remain")

        return {
            "memories": filtered_memories,
            "total_count": len(filtered_memories),
            "raw_count": len(short_term_memories),
            "source": "short_term_memory",
            "actor_id": query.actor_id,
            "session_id": query.session_id,
            "memory_id": memory_id,
            "filters_applied": {
                "content_search": bool(query.content_search),
                "role_filter": query.role_filter,
                "event_type": query.event_type,
            },
        }

    except Exception as e:
        logger.error(f"Error getting short-term memory: {e}")
        clean_error = clean_aws_error_message(str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get short-term memory: {clean_error}")


class EventQuery(BaseModel):
    event_id: str
    memory_id: Optional[str] = None
    # 선택 사항: 다음 값이 있으면 더 효율적으로 검색할 수 있음
    actor_id: Optional[str] = None
    session_id: Optional[str] = None


class EventSearchQuery(BaseModel):
    event_id: str
    memory_id: Optional[str] = None
    # 이벤트를 찾기 위한 검색 매개변수
    search_all_sessions: bool = False
    known_actor_ids: Optional[List[str]] = None


@app.post("/api/agentcore/searchEventById")
async def search_event_by_id(query: EventSearchQuery):
    """Search for an event by ID across multiple sessions"""
    try:
        if not memory_client:
            raise HTTPException(status_code=503, detail="AgentCore Memory client not available")

        memory_id = query.memory_id or MEMORY_ID

        logger.info(f"🔍 Searching for event ID: {query.event_id}")
        logger.info(f"📋 Memory ID: {memory_id}")

        # 시도할 일반적인 Actor ID(사용자가 제공한 경우에만)
        actor_ids_to_try = query.known_actor_ids or []

        # Session ID는 사용자가 제공해야 하며 하드코딩된 기본값은 없음
        session_ids_to_try = []

        for actor_id in actor_ids_to_try:
            for session_id in session_ids_to_try:
                try:
                    logger.info(f"🔍 Searching in actor_id={actor_id}, session_id={session_id}")

                    events = memory_client.list_events(
                        memory_id=memory_id,
                        actor_id=actor_id,
                        session_id=session_id,
                        max_results=100,  # 더 많은 이벤트 검색
                    )

                    # 특정 Event ID 찾기
                    for event in events:
                        if event.get("eventId") == query.event_id:
                            logger.info(f"✅ Found event {query.event_id} in {actor_id}/{session_id}")

                            # 이벤트 처리(이전과 동일한 로직)
                            payload = event.get("payload", {})
                            content_text = str(payload)  # 현재는 단순화하여 처리

                            event_data = {
                                "id": query.event_id,
                                "content": content_text,
                                "type": "event",
                                "memory_type": "SHORT_TERM",
                                "event_id": event.get("eventId", query.event_id),
                                "event_type": event.get("eventType", "unknown"),
                                "actor_id": actor_id,
                                "session_id": session_id,
                                "timestamp": str(
                                    event.get(
                                        "eventTimestamp",
                                        datetime.now().isoformat() + "Z",
                                    )
                                ),
                                "size": len(content_text),
                                "found_in": f"{actor_id}/{session_id}",
                            }

                            return {
                                "event": event_data,
                                "found": True,
                                "memory_id": memory_id,
                                "event_id": query.event_id,
                                "search_location": f"{actor_id}/{session_id}",
                            }

                except Exception as e:
                    logger.warning(f"Search failed for {actor_id}/{session_id}: {e}")
                    continue

        return {
            "event": None,
            "found": False,
            "event_id": query.event_id,
            "error": f"Event {query.event_id} not found in searched sessions",
            "searched_combinations": len(actor_ids_to_try) * len(session_ids_to_try),
        }

    except Exception as e:
        logger.error(f"Error searching for event: {e}")
        clean_error = clean_aws_error_message(str(e))
        raise HTTPException(status_code=500, detail=f"Failed to search for event: {clean_error}")


@app.post("/api/agentcore/getEventById")
async def get_event_by_id(query: EventQuery):
    """Get a specific event by event ID"""
    try:
        if not memory_client:
            raise HTTPException(status_code=503, detail="AgentCore Memory client not available")

        memory_id = query.memory_id or MEMORY_ID

        logger.info(f"🔍 Fetching event by ID: {query.event_id}")
        logger.info(f"📋 Memory ID: {memory_id}")

        # 특정 이벤트 가져오기 시도
        try:
            # 참고: Memory 클라이언트에 get_event 메서드가 있다고 가정함
            # 실제 AgentCore Memory 클라이언트 API를 확인해야 할 수 있음
            event = memory_client.get_event(memory_id=memory_id, event_id=query.event_id)

            if event:
                payload = event.get("payload", {})
                content_text = ""

                # Payload 구조 처리(list_events와 동일한 로직)
                if isinstance(payload, list) and len(payload) > 0:
                    first_item = payload[0]
                    if isinstance(first_item, dict):
                        if "conversational" in first_item:
                            conversational = first_item["conversational"]
                            if isinstance(conversational, dict):
                                content = conversational.get("content", {})
                                if isinstance(content, dict) and "text" in content:
                                    content_text = content["text"]
                                else:
                                    content_text = str(conversational)
                        else:
                            if "content" in first_item:
                                content = first_item["content"]
                                if isinstance(content, dict) and "text" in content:
                                    content_text = content["text"]
                                else:
                                    content_text = str(content)
                            else:
                                content_text = str(first_item)
                    else:
                        content_text = str(first_item)
                elif isinstance(payload, dict):
                    if "content" in payload:
                        content = payload["content"]
                        if isinstance(content, dict) and "text" in content:
                            content_text = content["text"]
                        else:
                            content_text = str(content)
                    elif "message" in payload:
                        content_text = str(payload["message"])
                    else:
                        content_text = str(payload)
                else:
                    content_text = str(payload)

                event_data = {
                    "id": query.event_id,
                    "content": content_text,
                    "type": "event",
                    "memory_type": "SHORT_TERM",
                    "event_id": event.get("eventId", query.event_id),
                    "event_type": event.get("eventType", "unknown"),
                    "actor_id": event.get("actorId", "unknown"),
                    "session_id": event.get("sessionId", "unknown"),
                    "timestamp": str(event.get("eventTimestamp", datetime.now().isoformat() + "Z")),
                    "size": len(content_text),
                    "raw_event": event,  # 디버깅을 위해 전체 이벤트 데이터 포함
                }

                return {
                    "event": event_data,
                    "found": True,
                    "memory_id": memory_id,
                    "event_id": query.event_id,
                }
            else:
                return {
                    "event": None,
                    "found": False,
                    "event_id": query.event_id,
                    "error": "Event not found",
                }

        except AttributeError:
            # get_event 메서드가 없으면 대체 접근 방식 시도
            logger.warning("get_event method not available, trying alternative approach")

            # 대안: 모든 이벤트를 검색하여 특정 이벤트 찾기
            # 효율성은 떨어지지만 직접 이벤트를 검색할 수 없을 때 사용할 수 있음
            try:
                # 이 접근 방식에는 actor_id와 session_id가 필요함
                # 현재 API의 제약 사항임
                return {
                    "event": None,
                    "found": False,
                    "event_id": query.event_id,
                    "error": "Direct event retrieval not supported. Need actor_id and session_id to search events.",
                }
            except Exception as e:
                logger.error(f"Alternative event search failed: {e}")
                clean_error = clean_aws_error_message(str(e))
                raise HTTPException(status_code=500, detail=f"Failed to retrieve event: {clean_error}")

    except Exception as e:
        logger.error(f"Error getting event by ID: {e}")
        clean_error = clean_aws_error_message(str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get event: {clean_error}")


@app.post("/api/agentcore/listNamespacesOld")
async def list_namespaces_old(query: MemoryQuery):
    """List available namespaces from AgentCore Memory strategies (deprecated)"""
    try:
        if not memory_client:
            raise HTTPException(status_code=503, detail="AgentCore Memory client not available")

        # 제공된 memory_id를 사용하고, 없으면 환경 기본값으로 대체
        memory_id = query.memory_id or MEMORY_ID

        if not memory_id:
            raise HTTPException(
                status_code=400,
                detail="Memory ID is required. Please provide memory_id in request or set AGENTCORE_MEMORY_ID environment variable.",
            )

        logger.info(f"🔍 Listing namespaces for memory ID: {memory_id}")

        # 네임스페이스 검색을 위해 Memory Strategy 가져오기
        try:
            strategies = memory_client.get_memory_strategies(memory_id)
            logger.info(f"✅ Found {len(strategies)} memory strategies")

            namespaces = []
            for strategy in strategies:
                strategy_namespaces = strategy.get("namespaces", [])
                strategy_type = strategy.get("type", "UNKNOWN")

                for namespace in strategy_namespaces:
                    namespaces.append(
                        {
                            "namespace": namespace,
                            "type": strategy_type,
                            "count": 0,  # 필요한 경우 여기에 개수 쿼리를 추가할 수 있음
                            "sample_content": "",  # 필요한 경우 샘플 콘텐츠를 추가할 수 있음
                        }
                    )

            logger.info(f"✅ Discovered {len(namespaces)} namespaces")

            return {
                "namespaces": namespaces,
                "total_count": len(namespaces),
                "memory_id": memory_id,
            }

        except Exception as e:
            error_msg = str(e).lower()
            logger.error(f"Failed to get memory strategies: {e}")

            # ARN과 민감한 정보를 제거하도록 오류 메시지 정리
            clean_error = clean_aws_error_message(str(e))

            # 특정 Memory ID를 찾을 수 없음 오류인지 확인
            if any(
                keyword in error_msg
                for keyword in [
                    "not found",
                    "does not exist",
                    "invalid memory",
                    "memory id",
                    "resourcenotfoundexception",
                ]
            ):
                logger.error(f"❌ Memory ID '{memory_id}' not found or inaccessible")
                raise HTTPException(
                    status_code=404,
                    detail=f"Memory ID '{memory_id}' not found. Please verify the Memory ID exists and you have access permissions.",
                )
            elif any(
                keyword in error_msg
                for keyword in [
                    "access denied",
                    "unauthorized",
                    "permission",
                    "accessdeniedexception",
                ]
            ):
                logger.error(f"❌ Access denied for Memory ID '{memory_id}'")
                raise HTTPException(status_code=403, detail=clean_error)
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to get memory strategies: {clean_error}",
                )

    except Exception as e:
        logger.error(f"Error listing namespaces: {e}")
        clean_error = clean_aws_error_message(str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list namespaces: {clean_error}")


@app.post("/api/agentcore/getLongTermMemory")
async def get_long_term_memory(query: LongTermMemoryQuery):
    """Get long-term memory (facts, preferences, summaries) from AgentCore Memory"""
    try:
        if not memory_client:
            raise HTTPException(status_code=503, detail="AgentCore Memory client not available")

        # 제공된 memory_id를 사용하고, 없으면 환경 기본값으로 대체
        memory_id = query.memory_id or MEMORY_ID

        if not memory_id:
            raise HTTPException(
                status_code=400,
                detail="Memory ID is required. Please provide memory_id in request or set AGENTCORE_MEMORY_ID environment variable.",
            )

        long_term_memories = []

        logger.info(f"Fetching long-term memory with namespace='{query.namespace}', max_results={query.max_results}")
        logger.info(f"📋 Memory ID: {memory_id}")
        logger.info(
            f"📋 Filters: content_type={query.content_type}, sort_by={query.sort_by}, sort_order={query.sort_order}"
        )

        # retrieve_memories를 사용하여 AgentCore에서 Long-term Memory를 직접 가져오기
        try:
            logger.info("📚 Using retrieve_memories API")

            # 시맨틱 검색에 retrieve_memories 사용
            memory_results = memory_client.retrieve_memories(
                memory_id=memory_id,
                namespace=query.namespace,
                query="*",  # 모든 콘텐츠 가져오기 - 구성 가능하도록 만들 수 있음
                top_k=query.max_results,
            )

            if isinstance(memory_results, dict) and "memoryRecordSummaries" in memory_results:
                memory_records = memory_results["memoryRecordSummaries"]
            else:
                memory_records = memory_results if isinstance(memory_results, list) else []

            if memory_records:
                logger.info(f"✅ Found {len(memory_records)} memory records")

                for memory_idx, memory in enumerate(memory_records):
                    # 디버그: 원시 Memory 구조 기록
                    logger.info(f"📋 Raw memory record {memory_idx}: {memory}")

                    content = memory.get("content", {})
                    if isinstance(content, dict):
                        content_text = content.get("text", str(content))
                    else:
                        content_text = str(content)

                    # 콘텐츠 유형 필터 적용
                    memory_namespaces = memory.get("namespaces", [])
                    namespace_str = memory_namespaces[0] if memory_namespaces else query.namespace

                    if query.content_type != "all":
                        if query.content_type == "facts" and "facts" not in namespace_str:
                            continue
                        elif query.content_type == "preferences" and "preferences" not in namespace_str:
                            continue
                        elif query.content_type == "summaries" and not any(
                            word in content_text.lower() for word in ["summary", "topic", "conversation"]
                        ):
                            continue
                        elif query.content_type == "context" and "context" not in namespace_str:
                            continue

                    memory_entry = {
                        "id": memory.get("memoryRecordId", f"memory-{memory_idx}"),
                        "content": content_text,
                        "type": "record",
                        "memory_type": "LONG_TERM",
                        "namespace": namespace_str,
                        "strategyId": memory.get("memoryStrategyId", ""),
                        "score": memory.get("score", 0),
                        "timestamp": str(memory.get("createdAt", datetime.now().isoformat() + "Z")),
                        "size": len(content_text),
                    }
                    long_term_memories.append(memory_entry)
            else:
                logger.info("❌ No memory records found")

        except Exception as e:
            error_msg = str(e).lower()
            logger.error(f"retrieve_memories failed: {e}")

            # ARN과 민감한 정보를 제거하도록 오류 메시지 정리
            clean_error = clean_aws_error_message(str(e))

            # 특정 Memory ID를 찾을 수 없음 오류인지 확인
            if any(
                keyword in error_msg
                for keyword in [
                    "not found",
                    "does not exist",
                    "invalid memory",
                    "memory id",
                    "resourcenotfoundexception",
                ]
            ):
                logger.error(f"❌ Memory ID '{memory_id}' not found or inaccessible")
                raise HTTPException(
                    status_code=404,
                    detail=f"Memory ID '{memory_id}' not found. Please verify the Memory ID exists and you have access permissions.",
                )
            elif any(
                keyword in error_msg
                for keyword in [
                    "access denied",
                    "unauthorized",
                    "permission",
                    "accessdeniedexception",
                ]
            ):
                logger.error(f"❌ Access denied for Memory ID '{memory_id}'")
                raise HTTPException(status_code=403, detail=clean_error)
            elif "namespace" in error_msg and ("not found" in error_msg or "invalid" in error_msg):
                logger.error(f"❌ Namespace '{query.namespace}' not found in Memory ID '{memory_id}'")
                raise HTTPException(
                    status_code=404,
                    detail=f"Namespace '{query.namespace}' not found in Memory ID '{memory_id}'. Please verify the namespace exists.",
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to retrieve memories from AgentCore: {clean_error}",
                )

        # 정렬 적용
        if query.sort_by == "timestamp":
            long_term_memories.sort(key=lambda x: x["timestamp"], reverse=(query.sort_order == "desc"))
        elif query.sort_by == "namespace":
            long_term_memories.sort(key=lambda x: x["namespace"], reverse=(query.sort_order == "desc"))
        elif query.sort_by == "size":
            long_term_memories.sort(key=lambda x: x["size"], reverse=(query.sort_order == "desc"))

        logger.info(f"✅ Total long-term memories found: {len(long_term_memories)}")

        return {
            "memories": long_term_memories,
            "total_count": len(long_term_memories),
            "source": "long_term_memory",
            "namespace": query.namespace,
            "memory_id": memory_id,
        }

    except Exception as e:
        logger.error(f"Error getting long-term memory: {e}")
        clean_error = clean_aws_error_message(str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get long-term memory: {clean_error}")


@app.post("/api/agentcore/getMemoryEntries")
async def get_memory_entries(query: MemoryQuery):
    """List all memory records from AgentCore Memory"""
    try:
        if not memory_client:
            raise HTTPException(status_code=503, detail="AgentCore Memory client not available")

        # 제공된 memory_id를 사용하고, 없으면 환경 기본값으로 대체
        memory_id = query.memory_id or MEMORY_ID

        if not memory_id:
            raise HTTPException(
                status_code=400,
                detail="Memory ID is required. Please provide memory_id in request or set AGENTCORE_MEMORY_ID environment variable.",
            )

        all_memories = []

        # 시맨틱 검색 없이 모든 레코드를 탐색하도록 ListMemoryRecords 작업 사용
        logger.info("🔍 Listing memory records using ListMemoryRecords operation")
        logger.info(f"📋 Memory ID: {memory_id}")

        # AgentCore Memory의 효율적인 쿼리에는 일반적으로 네임스페이스가 필요함
        # 네임스페이스가 제공되지 않으면 안내 메시지 반환
        if not query.namespace:
            logger.info("📋 No namespace provided - AgentCore Memory requires namespace for queries")
            return {
                "memories": [],
                "total_count": 0,
                "source": "list_memory_records",
                "memory_id": memory_id,
                "message": "No namespace provided. AgentCore Memory requires a namespace to query data efficiently. Please provide a namespace in your request.",
            }

        # 제공된 네임스페이스로 Memory 레코드 나열 시도
        try:
            logger.info(f"📋 Listing memory records from namespace: {query.namespace}")

            memories = memory_client.list_memory_records(
                memoryId=memory_id,
                namespace=query.namespace,
                maxResults=query.max_results or 50,
            )

            # 실제 응답 구조 처리
            if isinstance(memories, dict) and "memoryRecordSummaries" in memories:
                memory_records = memories["memoryRecordSummaries"]
                logger.info(f"📋 Processing {len(memory_records)} actual memory records")
            else:
                memory_records = memories if isinstance(memories, list) else [memories]

            logger.info(f"✅ Found {len(memory_records)} memory records")

            # Memory를 자체 형식으로 변환
            for memory in memory_records:
                # 딕셔너리 형식과 문자열 형식 모두 처리
                if isinstance(memory, dict):
                    content = memory.get("content", {})
                    if isinstance(content, dict):
                        content_text = content.get("text", str(content))
                    else:
                        content_text = str(content)

                    memory_entry = {
                        "id": memory.get("memoryId", f"memory-{len(all_memories)}"),
                        "content": content_text,
                        "memory_type": "LONG_TERM_MEMORY",
                        "namespace": query.namespace,
                        "score": memory.get("score", 0),
                        "timestamp": memory.get("createdAt", datetime.now().isoformat() + "Z"),
                        "size": len(content_text),
                    }
                else:
                    # 문자열 형식 처리
                    content_text = str(memory)
                    memory_entry = {
                        "id": f"memory-{len(all_memories)}",
                        "content": content_text,
                        "memory_type": "LONG_TERM_MEMORY",
                        "namespace": query.namespace,
                        "score": 0,
                        "timestamp": datetime.now().isoformat() + "Z",
                        "size": len(content_text),
                    }

                all_memories.append(memory_entry)

        except Exception as e:
            logger.warning(f"Could not list memory records from namespace '{query.namespace}': {e}")
            # 내부 세부 정보가 노출되지 않도록 오류 메시지 정리
            clean_error = clean_aws_error_message(str(e))
            return {
                "memories": [],
                "total_count": 0,
                "source": "list_memory_records",
                "error": f"Failed to access namespace '{query.namespace}': {clean_error}",
            }

        logger.info(f"✅ Total memory records found: {len(all_memories)}")

        return {
            "memories": all_memories,
            "total_count": len(all_memories),
            "source": "list_memory_records",
            "memory_id": memory_id,
        }

    except Exception as e:
        logger.error(f"Error listing memory records: {e}")
        clean_error = clean_aws_error_message(str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list memory records: {clean_error}")


class MemoryIdValidationQuery(BaseModel):
    memory_id: str


class ListNamespacesQuery(BaseModel):
    memory_id: str
    max_results: Optional[int] = 100


@app.post("/api/agentcore/listNamespacesV2")
async def list_namespaces_v2(query: ListNamespacesQuery):
    """List available namespaces for a given memory ID (v2)"""
    try:
        if not memory_client:
            raise HTTPException(status_code=503, detail="AgentCore Memory client not available")

        memory_id = query.memory_id or MEMORY_ID
        if not memory_id:
            raise HTTPException(status_code=400, detail="Memory ID is required")

        logger.info(f"🔍 Listing namespaces for memory ID: {memory_id}")

        # 올바른 AgentCore Memory SDK 접근 방식으로 네임스페이스 가져오기
        try:
            logger.info("📋 Getting memory strategies to discover namespaces...")

            # 네임스페이스 정보가 포함된 Memory Strategy 가져오기
            strategies = memory_client.get_memory_strategies(memory_id)
            logger.info(f"✅ Found {len(strategies)} memory strategies")

            found_namespaces = []

            # Strategy에서 네임스페이스 추출
            for strategy in strategies:
                strategy_type = strategy.get("type", "unknown")
                namespaces = strategy.get("namespaces", [])

                logger.info(f"📋 Strategy '{strategy_type}' has namespaces: {namespaces}")

                for namespace in namespaces:
                    # 개수를 확인하기 위해 이 네임스페이스의 레코드 샘플 가져오기 시도
                    try:
                        # retrieve_memories를 사용하여 샘플 콘텐츠 가져오기
                        sample_memories = memory_client.retrieve_memories(
                            memory_id=memory_id,
                            namespace=namespace,
                            query="*",  # 임의의 콘텐츠를 가져오는 일반 쿼리
                            top_k=3,  # 샘플 몇 개 가져오기
                        )

                        sample_content = ""
                        if sample_memories and len(sample_memories) > 0:
                            first_memory = sample_memories[0]
                            content = first_memory.get("content", {})
                            if isinstance(content, dict):
                                sample_content = content.get("text", str(content))[:100] + "..."
                            else:
                                sample_content = str(content)[:100] + "..."

                        found_namespaces.append(
                            {
                                "namespace": namespace,
                                "type": strategy_type,
                                "count": len(sample_memories) if sample_memories else 0,
                                "sample_content": sample_content,
                            }
                        )

                        logger.info(
                            f"✅ Found namespace: {namespace} (type: {strategy_type}) with {len(sample_memories) if sample_memories else 0} sample records"
                        )

                    except Exception as e:
                        # 샘플을 가져올 수 없어도 네임스페이스 추가
                        found_namespaces.append(
                            {
                                "namespace": namespace,
                                "type": strategy_type,
                                "count": 0,
                                "sample_content": f"Unable to retrieve sample: {clean_aws_error_message(str(e))}",
                            }
                        )
                        logger.warning(
                            f"⚠️ Found namespace: {namespace} (type: {strategy_type}) but couldn't retrieve samples: {e}"
                        )

            # 네임스페이스를 기준으로 중복 제거
            unique_namespaces = []
            seen_namespaces = set()
            for ns in found_namespaces:
                if ns["namespace"] not in seen_namespaces:
                    unique_namespaces.append(ns)
                    seen_namespaces.add(ns["namespace"])

            return {
                "memory_id": memory_id,
                "namespaces": unique_namespaces,
                "total_found": len(unique_namespaces),
                "strategies_found": len(strategies),
                "message": f"Found {len(unique_namespaces)} namespaces from {len(strategies)} memory strategies"
                if unique_namespaces
                else "No namespaces found in memory strategies",
            }

        except Exception as e:
            logger.warning(f"Failed to get memory strategies: {e}")

            # 이전 패턴 기반 접근 방식으로 대체
            logger.info("🔄 Falling back to pattern-based namespace discovery...")

            try:
                # AgentCore Memory의 일반적인 네임스페이스 패턴
                namespace_patterns = [
                    "support/user/DEFAULT/",
                    "support/user/DEFAULT/facts/",
                    "support/user/DEFAULT/preferences/",
                    "support/user/DEFAULT/context/",
                    "support/user/DEFAULT/summaries/",
                    "facts/",
                    "preferences/",
                    "context/",
                    "summaries/",
                ]

                found_namespaces = []

                for pattern in namespace_patterns:
                    try:
                        # list_memory_records를 사용하여 네임스페이스 존재 여부 테스트
                        memories = memory_client.list_memory_records(
                            memoryId=memory_id, namespace=pattern, maxResults=1
                        )

                        if memories and len(memories) > 0:
                            sample_content = ""
                            if memories[0].get("content"):
                                content = memories[0]["content"]
                                if isinstance(content, dict):
                                    sample_content = content.get("text", str(content))[:100] + "..."
                                else:
                                    sample_content = str(content)[:100] + "..."

                            found_namespaces.append(
                                {
                                    "namespace": pattern,
                                    "type": "unknown",
                                    "count": 1,  # 레코드 1개만 쿼리함
                                    "sample_content": sample_content,
                                }
                            )
                            logger.info(f"✅ Found namespace: {pattern} (fallback method)")

                    except Exception as e2:
                        logger.debug(f"❌ Namespace {pattern} not accessible: {e2}")
                        continue

                return {
                    "memory_id": memory_id,
                    "namespaces": found_namespaces,
                    "total_found": len(found_namespaces),
                    "method": "fallback_pattern_based",
                    "message": f"Found {len(found_namespaces)} namespaces using fallback method (get_memory_strategies failed: {clean_aws_error_message(str(e))})",
                }

            except Exception as e2:
                logger.warning(f"Fallback method also failed: {e2}")
                return {
                    "namespaces": [],
                    "total_found": 0,
                    "error": f"Both get_memory_strategies and fallback failed: {clean_aws_error_message(str(e))} / {clean_aws_error_message(str(e2))}",
                }

    except Exception as e:
        logger.error(f"Error listing namespaces: {e}")
        clean_error = clean_aws_error_message(str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list namespaces: {clean_error}")


@app.post("/api/agentcore/validateMemoryId")
async def validate_memory_id(query: MemoryIdValidationQuery):
    """Validate if a memory ID is accessible"""
    try:
        if not memory_client:
            raise HTTPException(status_code=503, detail="AgentCore Memory client not available")

        logger.info(f"🔍 Validating memory ID: {query.memory_id}")

        # Memory ID를 검증하기 위해 Memory 레코드 나열 시도
        try:
            _ = memory_client.list_memory_records(
                memoryId=query.memory_id,
                maxResults=1,  # 액세스 가능 여부만 확인
            )

            return {
                "valid": True,
                "memory_id": query.memory_id,
                "accessible": True,
                "message": "Memory ID is valid and accessible",
            }

        except Exception as e:
            logger.warning(f"Memory ID validation failed: {e}")
            return {
                "valid": False,
                "memory_id": query.memory_id,
                "accessible": False,
                "message": f"Memory ID validation failed: {clean_aws_error_message(str(e))}",
            }

    except Exception as e:
        logger.error(f"Error validating memory ID: {e}")
        clean_error = clean_aws_error_message(str(e))
        raise HTTPException(status_code=500, detail=f"Failed to validate memory ID: {clean_error}")


class AddMemoryEntryQuery(BaseModel):
    session_id: str
    memory_type: str
    content: str


class DeleteMemoryEntriesQuery(BaseModel):
    session_id: str
    memory_type: Optional[str] = None


class SearchMemoryEntriesQuery(BaseModel):
    query: str
    session_id: Optional[str] = None
    memory_type: Optional[str] = None
    max_results: Optional[int] = 50


@app.post("/api/agentcore/addMemoryEntry")
async def add_memory_entry(query: AddMemoryEntryQuery):
    """Add a memory entry (not implemented for AgentCore Memory)"""
    return {
        "success": False,
        "message": "Adding memory entries is not supported in this dashboard. AgentCore Memory entries are created by your application.",
    }


@app.post("/api/agentcore/deleteMemoryEntries")
async def delete_memory_entries(query: DeleteMemoryEntriesQuery):
    """Delete memory entries (not implemented for AgentCore Memory)"""
    return {
        "success": False,
        "message": "Deleting memory entries is not supported in this dashboard. AgentCore Memory manages its own lifecycle.",
    }


@app.post("/api/agentcore/searchMemoryEntries")
async def search_memory_entries(query: SearchMemoryEntriesQuery):
    """Search memory entries (simplified implementation)"""
    try:
        # 단순화된 검색임 - 실제 구현에서는 시맨틱 검색이나
        # 다른 AgentCore Memory 검색 기능을 사용할 수 있음
        return {
            "memories": [],
            "total_count": 0,
            "message": "Search functionality not fully implemented. Use the Long-Term Memory tab with specific namespaces for better results.",
        }
    except Exception as e:
        logger.error(f"Error searching memory entries: {e}")
        clean_error = clean_aws_error_message(str(e))
        raise HTTPException(status_code=500, detail=f"Failed to search memory entries: {clean_error}")


@app.post("/api/agentcore/listNamespaces")
async def list_namespaces(request: dict):
    """List available namespaces for long-term memory"""
    try:
        if not memory_client:
            raise HTTPException(status_code=503, detail="AgentCore Memory client not available")

        memory_id = request.get("memory_id") or MEMORY_ID
        _ = request.get("max_results", 100)  # 향후 사용을 위해 예약

        if not memory_id:
            raise HTTPException(
                status_code=400,
                detail="Memory ID is required. Please provide memory_id in request or set AGENTCORE_MEMORY_ID environment variable.",
            )

        logger.info(f"🔍 Listing namespaces for memory_id: {memory_id}")

        try:
            # 네임스페이스 검색을 위해 Memory Strategy 가져오기
            strategies = memory_client.get_memory_strategies(memory_id)
            logger.info(f"✅ Found {len(strategies)} memory strategies")

            namespaces = []
            for strategy in strategies:
                strategy_type = strategy.get("type", "UNKNOWN")
                strategy_namespaces = strategy.get("namespaces", [])

                for namespace in strategy_namespaces:
                    # 이 네임스페이스의 레코드 개수 가져오기 시도
                    try:
                        # 개수와 샘플 콘텐츠를 얻기 위해 레코드 몇 개 샘플링
                        sample_memories = memory_client.retrieve_memories(
                            memory_id=memory_id, namespace=namespace, query="*", top_k=5
                        )

                        if isinstance(sample_memories, dict) and "memoryRecordSummaries" in sample_memories:
                            memory_records = sample_memories["memoryRecordSummaries"]
                        else:
                            memory_records = sample_memories if isinstance(sample_memories, list) else []

                        count = len(memory_records)
                        sample_content = ""
                        if memory_records:
                            first_record = memory_records[0]
                            content = first_record.get("content", {})
                            if isinstance(content, dict):
                                sample_content = content.get("text", str(content))
                            else:
                                sample_content = str(content)

                    except Exception as e:
                        logger.warning(f"Failed to get count for namespace {namespace}: {e}")
                        count = 0
                        sample_content = ""

                    namespace_info = {
                        "namespace": namespace,
                        "type": strategy_type,
                        "count": count,
                        "sample_content": sample_content[:200] if sample_content else "",
                    }
                    namespaces.append(namespace_info)

            logger.info(f"✅ Found {len(namespaces)} total namespaces")

            return {
                "namespaces": namespaces,
                "total_count": len(namespaces),
                "memory_id": memory_id,
                "strategies_count": len(strategies),
            }

        except Exception as e:
            logger.error(f"Failed to get memory strategies: {e}")
            clean_error = clean_aws_error_message(str(e))
            raise HTTPException(status_code=500, detail=f"Failed to get namespaces: {clean_error}")

    except Exception as e:
        logger.error(f"Error listing namespaces: {e}")
        clean_error = clean_aws_error_message(str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list namespaces: {clean_error}")


@app.get("/api/agentcore/listSessions")
async def list_sessions():
    """List available sessions (simplified)"""
    try:
        return {
            "sessions": [
                {
                    "session_id": "memory-records",
                    "type": "MEMORY_RECORDS",
                    "active": True,
                }
            ],
            "total_sessions": 1,
            "source": "list_records_focus",
        }

    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return {
            "sessions": [],
            "total_sessions": 0,
            "error": clean_aws_error_message(str(e)),
        }


if __name__ == "__main__":
    import uvicorn

    # 보안: 모든 네트워크 인터페이스에 노출되지 않도록 기본적으로 localhost에만 바인딩(B104)
    # 프로덕션 배포에서는 reverse proxy(nginx, ALB)를 사용하고 환경 변수로 host 구성
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", "8000"))

    if host == "0.0.0.0":  # nosec B104 - 보안 검사이며 취약점이 아님
        logger.warning("⚠️  WARNING: Binding to 0.0.0.0 exposes the service to all network interfaces!")
        logger.warning("⚠️  For production, use a reverse proxy and bind to 127.0.0.1")

    uvicorn.run(app, host=host, port=port)
