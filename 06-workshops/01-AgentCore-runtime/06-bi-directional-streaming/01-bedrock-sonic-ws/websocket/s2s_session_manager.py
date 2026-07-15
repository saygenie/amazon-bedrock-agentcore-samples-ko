import asyncio
import json
import warnings
import uuid
import logging
from s2s_events import S2sEvent
import time
from aws_sdk_bedrock_runtime.client import (
    BedrockRuntimeClient,
    InvokeModelWithBidirectionalStreamOperationInput,
)
from aws_sdk_bedrock_runtime.models import (
    InvokeModelWithBidirectionalStreamInputChunk,
    BidirectionalInputPayloadPart,
)
from aws_sdk_bedrock_runtime.config import Config
from smithy_aws_core.identity.environment import EnvironmentCredentialsResolver

# 경고 억제
warnings.filterwarnings("ignore")

# 로깅 구성
logger = logging.getLogger(__name__)


class S2sSessionManager:
    """asyncio를 사용해 Amazon Bedrock과의 양방향 스트리밍을 관리합니다."""

    def __init__(self, region, model_id):
        """Stream Manager를 초기화합니다."""
        self.model_id = model_id
        self.region = region

        # 메모리 문제 방지를 위해 크기를 제한한 오디오 및 출력 큐
        self.audio_input_queue = asyncio.Queue(maxsize=100)  # 오디오 청크 100개로 제한(약 2~3초 분량)
        self.output_queue = asyncio.Queue(maxsize=200)  # 응답용으로 더 큰 출력 큐

        self.response_task = None
        self.stream = None
        self.is_active = False
        self.bedrock_client = None

        # 세션 정보
        self.prompt_name = None  # Frontend에서 설정
        self.content_name = None  # Frontend에서 설정
        self.audio_content_name = None  # Frontend에서 설정
        self.toolUseContent = ""
        self.toolUseId = ""
        self.toolName = ""

        # 활성 tool 처리 작업 추적
        self.tool_processing_tasks = set()

    def _initialize_client(self):
        """
        EnvironmentCredentialsResolver를 사용해 Amazon Bedrock Client를 초기화합니다.

        자격 증명은 server.py에서 다음 방식으로 관리합니다.
        - 기존 환경 변수 사용(로컬 모드)
        - IMDS에서 자격 증명을 가져와 갱신(EC2 모드)
        """
        logger.info("Initializing Bedrock client with EnvironmentCredentialsResolver")

        config = Config(
            endpoint_uri=f"https://bedrock-runtime.{self.region}.amazonaws.com",
            region=self.region,
            aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
        )
        self.bedrock_client = BedrockRuntimeClient(config=config)
        logger.info("Bedrock client initialized successfully")

    def reset_session_state(self):
        """새 세션을 위해 세션 상태를 재설정합니다."""
        # 진행 중인 tool 처리 작업 취소
        for task in list(self.tool_processing_tasks):
            if not task.done():
                task.cancel()
        self.tool_processing_tasks.clear()

        # 큐 비우기
        while not self.audio_input_queue.empty():
            try:
                self.audio_input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # tool 사용 상태 재설정
        self.toolUseContent = ""
        self.toolUseId = ""
        self.toolName = ""

        # 세션 정보 재설정
        self.prompt_name = None
        self.content_name = None
        self.audio_content_name = None

    async def initialize_stream(self):
        """Amazon Bedrock과의 양방향 스트림을 초기화합니다."""
        try:
            if not self.bedrock_client:
                self._initialize_client()
        except Exception:
            self.is_active = False
            logger.error("Failed to initialize Bedrock client")
            raise

        try:
            # 스트림 초기화
            self.stream = await self.bedrock_client.invoke_model_with_bidirectional_stream(
                InvokeModelWithBidirectionalStreamOperationInput(model_id=self.model_id)
            )
            self.is_active = True

            # 응답 수신 시작
            self.response_task = asyncio.create_task(self._process_responses())

            # 오디오 입력 처리 시작
            asyncio.create_task(self._process_audio_input())

            # 모든 설정이 완료되도록 잠시 대기
            await asyncio.sleep(0.1)

            logger.info("Stream initialized successfully")
            return self
        except Exception:
            self.is_active = False
            logger.error("Failed to initialize stream.")
            raise

    async def send_raw_event(self, event_data):
        """Amazon Bedrock 스트림에 원시 이벤트를 전송합니다."""
        try:
            if not self.stream or not self.is_active:
                logger.warning("Stream not initialized or closed")
                return

            event_json = json.dumps(event_data)
            # if "audioInput" not in event_data["event"]:
            #    print(event_json)
            event = InvokeModelWithBidirectionalStreamInputChunk(
                value=BidirectionalInputPayloadPart(bytes_=event_json.encode("utf-8"))
            )
            await self.stream.input_stream.send(event)

            # 세션 닫기
            if "sessionEnd" in event_data["event"]:
                await self.close()

        except Exception:
            logger.error("Error sending event to Bedrock")
            # 전송 오류가 발생해도 스트림을 닫지 않고 Amazon Bedrock에서 처리하도록 함
            # 응답 처리 루프에서 스트림 중단 여부를 감지함

    async def _process_audio_input(self):
        """큐의 오디오 입력을 처리해 Amazon Bedrock으로 전송합니다."""
        while self.is_active:
            try:
                # 큐에서 오디오 데이터 가져오기
                data = await self.audio_input_queue.get()

                # 큐 항목에서 데이터 추출
                prompt_name = data.get("prompt_name")
                content_name = data.get("content_name")
                audio_bytes = data.get("audio_bytes")

                if not audio_bytes or not prompt_name or not content_name:
                    logger.warning("Missing required audio data properties")
                    continue

                # 오디오 입력 이벤트 생성
                audio_event = S2sEvent.audio_input(
                    prompt_name,
                    content_name,
                    (audio_bytes.decode("utf-8") if isinstance(audio_bytes, bytes) else audio_bytes),
                )

                # 이벤트 전송
                await self.send_raw_event(audio_event)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.error("Error processing audio.")

    def add_audio_chunk(self, prompt_name, content_name, audio_data):
        """큐에 오디오 청크를 추가합니다."""
        # audio_data는 Frontend에서 전달된 base64 문자열임
        try:
            self.audio_input_queue.put_nowait(
                {
                    "prompt_name": prompt_name,
                    "content_name": content_name,
                    "audio_bytes": audio_data,
                }
            )
        except asyncio.QueueFull:
            # 큐가 가득 차면 backpressure 방지를 위해 이 청크를 폐기
            # 실시간 오디오 스트리밍에서는 허용되는 동작임
            logger.warning("Audio input queue full, dropping audio chunk to prevent backpressure")
            pass

    async def _process_responses(self):
        """Amazon Bedrock에서 들어오는 응답을 처리합니다."""
        while self.is_active:
            try:
                output = await self.stream.await_output()
                result = await output[1].receive()

                if result.value and result.value.bytes_:
                    response_data = result.value.bytes_.decode("utf-8")
                    logger.debug(f"Received event: {response_data}")

                    json_data = json.loads(response_data)
                    json_data["timestamp"] = int(time.time() * 1000)  # Epoch 이후 밀리초

                    event_name = None
                    if "event" in json_data:
                        event_name = list(json_data["event"].keys())[0]

                        # 디버깅을 위해 contentEnd 이벤트 기록
                        if event_name == "contentEnd":
                            content_end_data = json_data["event"]["contentEnd"]
                            logger.debug(
                                f"Received contentEnd: type={content_end_data.get('type')}, stopReason={content_end_data.get('stopReason')}, role={content_end_data.get('role', 'N/A')}"
                            )

                        # tool 사용 감지 처리
                        if event_name == "toolUse":
                            self.toolUseContent = json_data["event"]["toolUse"]
                            self.toolName = json_data["event"]["toolUse"]["toolName"]
                            self.toolUseId = json_data["event"]["toolUse"]["toolUseId"]
                            logger.info(f"Tool use detected: {self.toolName}, ID: {self.toolUseId}")

                        # 콘텐츠가 끝나면 tool 사용 처리
                        elif event_name == "contentEnd" and json_data["event"][event_name].get("type") == "TOOL":
                            prompt_name = json_data["event"]["contentEnd"].get("promptName")
                            logger.debug("Starting tool processing in background")
                            # 차단을 피하도록 백그라운드 작업에서 tool 처리
                            task = asyncio.create_task(
                                self._handle_tool_processing(
                                    prompt_name,
                                    self.toolName,
                                    self.toolUseContent,
                                    self.toolUseId,
                                )
                            )
                            self.tool_processing_tasks.add(task)
                            task.add_done_callback(self.tool_processing_tasks.discard)

                    # Frontend로 전달할 응답을 출력 큐에 추가
                    try:
                        # 차단을 피하기 위해 put_nowait을 사용하고 큐가 가득 찬 경우 적절히 처리
                        self.output_queue.put_nowait(json_data)
                    except asyncio.QueueFull:
                        # 큐가 가득 차면 경고를 기록하되 스트림을 중단하지 않음
                        # 처리량이 많은 오디오 응답에서 발생할 수 있음
                        logger.warning("Output queue full, dropping response to prevent backpressure")
                        # 스트림을 중단하지 않고 처리 계속

            except json.JSONDecodeError as ex:
                logger.error(f"JSON decode error in _process_responses: {ex}")
                await self.output_queue.put({"raw_data": response_data})
                # JSON 오류에서도 중단하지 않고 처리 계속
                continue
            except StopAsyncIteration:
                # 스트림이 정상적으로 종료됨
                logger.info("Bedrock stream has ended (StopAsyncIteration)")
                break
            except Exception as e:
                # ValidationException 및 기타 오류 처리
                error_str = str(e)
                if "ValidationException" in error_str:
                    logger.error(f"Bedrock validation error: {error_str}")
                    # 클라이언트에 오류를 전송하되 스트림은 중단하지 않음
                    await self.output_queue.put({"event": {"error": {"message": f"Validation error: {error_str}"}}})
                    continue
                else:
                    logger.error(f"Error receiving response from Bedrock: {e}", exc_info=True)
                    # 심각한 오류에서만 중단
                    break

        logger.info("Bedrock response processing loop ended, closing stream")
        self.is_active = False
        await self.close()

    async def _handle_tool_processing(self, prompt_name, tool_name, tool_use_content, tool_use_id):
        """이벤트 처리를 차단하지 않고 백그라운드에서 tool을 처리합니다."""
        try:
            logger.info(f"[Tool Processing] Starting: {tool_name} with ID: {tool_use_id}")
            toolResult = await self.processToolUse(tool_name, tool_use_content)
            logger.info(f"[Tool Processing] Completed: {tool_name}")

            # tool 시작 이벤트 전송
            toolContent = str(uuid.uuid4())
            tool_start_event = S2sEvent.content_start_tool(prompt_name, toolContent, tool_use_id)
            await self.send_raw_event(tool_start_event)

            # WebSocket Client에도 tool 시작 이벤트 전송
            tool_start_event_copy = tool_start_event.copy()
            tool_start_event_copy["timestamp"] = int(time.time() * 1000)
            await self.output_queue.put(tool_start_event_copy)

            # tool 결과 이벤트 전송
            if isinstance(toolResult, dict):
                content_json_string = json.dumps(toolResult)
            else:
                content_json_string = toolResult

            tool_result_event = S2sEvent.text_input_tool(prompt_name, toolContent, content_json_string)
            logger.debug(f"Tool result: {tool_result_event}")
            await self.send_raw_event(tool_result_event)

            # WebSocket Client에도 tool 결과 이벤트 전송
            tool_result_event_copy = tool_result_event.copy()
            tool_result_event_copy["timestamp"] = int(time.time() * 1000)
            await self.output_queue.put(tool_result_event_copy)

            # tool 콘텐츠 종료 이벤트 전송
            tool_content_end_event = S2sEvent.content_end(prompt_name, toolContent)
            await self.send_raw_event(tool_content_end_event)

            # WebSocket Client에도 tool 콘텐츠 종료 이벤트 전송
            tool_content_end_event_copy = tool_content_end_event.copy()
            tool_content_end_event_copy["timestamp"] = int(time.time() * 1000)
            await self.output_queue.put(tool_content_end_event_copy)

        except Exception as e:
            logger.error(f"Error in tool processing: {e}", exc_info=True)

    async def processToolUse(self, toolName, toolUseContent):
        """tool 결과를 반환합니다."""
        logger.debug(f"Tool Use Content: {toolUseContent}")

        toolName = toolName.lower()
        content, result = None, None
        try:
            if toolUseContent.get("content"):
                # content 필드의 JSON 문자열 파싱
                content = toolUseContent.get("content")  # JSON 문자열을 Agent에 직접 전달
                logger.debug(f"Extracted query: {content}")

            # UTC 시스템 시간을 가져오는 간단한 toolUse
            if toolName == "getdatetool":
                from datetime import datetime, timezone

                result = datetime.now(timezone.utc).strftime("%A, %Y-%m-%d %H:%M:%S") + " in UTC"

            if not result:
                result = "no result found"

            return {"result": result}
        except Exception as ex:
            logger.error(
                f"[Tool Error] Exception in processToolUse for {toolName}: {ex}",
                exc_info=True,
            )
            return {
                "result": "An error occurred while attempting to retrieve information related to the toolUse event."
            }

    async def close(self):
        """스트림을 올바르게 닫습니다."""
        if not self.is_active:
            logger.debug("Stream already closed, skipping cleanup")
            return

        logger.info("Closing Bedrock stream and cleaning up resources")
        self.is_active = False

        # 진행 중인 tool 처리 작업 취소
        for task in list(self.tool_processing_tasks):
            if not task.done():
                task.cancel()

        # 모든 tool 작업이 완료되거나 취소될 때까지 대기
        if self.tool_processing_tasks:
            await asyncio.gather(*self.tool_processing_tasks, return_exceptions=True)
        self.tool_processing_tasks.clear()

        # 이전 오디오 데이터 처리를 방지하도록 오디오 큐 비우기
        while not self.audio_input_queue.empty():
            try:
                self.audio_input_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # 출력 큐 비우기
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        # tool 사용 상태 재설정
        self.toolUseContent = ""
        self.toolUseId = ""
        self.toolName = ""

        # 세션 정보 재설정
        self.prompt_name = None
        self.content_name = None
        self.audio_content_name = None

        if self.stream:
            try:
                await self.stream.input_stream.close()
            except Exception as e:
                logger.debug(f"Error closing stream: {e}")

        if self.response_task and not self.response_task.done():
            self.response_task.cancel()
            try:
                await self.response_task
            except asyncio.CancelledError:
                pass

        # 올바르게 정리되도록 스트림을 None으로 설정
        self.stream = None
        self.response_task = None

        logger.info("Bedrock stream closed successfully")
