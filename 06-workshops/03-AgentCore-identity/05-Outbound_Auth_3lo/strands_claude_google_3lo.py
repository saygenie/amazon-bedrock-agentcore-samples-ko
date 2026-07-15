import os
import datetime
import json
import asyncio

from typing import Optional

from strands import Agent, tool
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_access_token
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# 환경 설정
os.environ["STRANDS_OTEL_ENABLE_CONSOLE_EXPORT"] = "true"
os.environ["OTEL_PYTHON_EXCLUDED_URLS"] = "/ping,/invocations"

# Google Calendar API에 필요한 OAuth2 범위
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# 애플리케이션 초기화
app = BedrockAgentCoreApp()


class StreamingQueue:
    def __init__(self):
        self.finished = False
        self.queue = asyncio.Queue()

    async def put(self, item):
        await self.queue.put(item)

    async def finish(self):
        self.finished = True
        await self.queue.put(None)

    async def stream(self):
        while True:
            item = await self.queue.get()
            if item is None and self.finished:
                break
            yield item


queue = StreamingQueue()


async def on_auth_url(url: str):
    app.logger.info(f"Authorization url: {url}")
    await queue.put(f"Authorization url: {url}")


@tool(
    name="Get_calendar_events_today",
    description="Retrieves the calendar events for the day from your Google Calendar",
)
async def get_calendar():
    @requires_access_token(
        provider_name="google-cal-provider",
        scopes=SCOPES,
        auth_flow="USER_FEDERATION",
        on_auth_url=on_auth_url,
        force_authentication=True,
        callback_url=os.environ["CALLBACK_URL"],
    )
    async def get_calendar_events_today(access_token: Optional[str] = "") -> str:
        google_access_token = access_token
        # 토큰이 이미 있는지 확인
        if not google_access_token:
            app.logger.info("Missing access token")
            return json.dumps(
                {
                    "auth_required": True,
                    "message": "Google Calendar authentication is required. Please wait while we set up the authorization.",
                    "events": [],
                }
            )

        # 제공된 액세스 토큰으로 자격 증명 생성
        creds = Credentials(token=google_access_token, scopes=SCOPES)
        try:
            service = build("calendar", "v3", credentials=creds)
            # Calendar API 호출
            today_start = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            # 고정된 시간대를 사용함. 실제 애플리케이션에서는 에이전트와 상호 작용하는
            # 사용자를 기준으로 시간대를 결정
            tz = "00:00"
            today_end = today_start.replace(hour=23, minute=59, second=59)
            time_min = today_start.strftime(f"%Y-%m-%dT00:00:00-{tz}")
            time_max = today_end.strftime(f"%Y-%m-%dT23:59:59-{tz}")

            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = events_result.get("items", [])

            if not events:
                return json.dumps({"events": []})  # 빈 이벤트 배열을 JSON으로 반환

            return json.dumps({"events": events})  # 이벤트를 객체로 감싸서 반환
        except HttpError as error:
            error_message = str(error)
            return json.dumps({"error": error_message, "events": []})
        except Exception as e:
            error_message = str(e)
            return json.dumps({"error": error_message, "events": []})

    app.logger.info("Run tool")
    try:
        return await get_calendar_events_today()
    except Exception as e:
        app.logger.info(e)


# 도구와 원하는 모델을 사용하여 에이전트 초기화
agent = Agent(
    model="global.anthropic.claude-haiku-4-5-20251001-v1:0",
    tools=[get_calendar],
)


async def agent_task(user_message: str):
    try:
        await queue.put("Begin agent execution")

        # 먼저 에이전트를 호출하여 인증이 필요한지 확인
        response = await agent.invoke_async(user_message)

        await queue.put(response.message)
        await queue.put("End agent execution")
    except Exception as e:
        await queue.put(f"Error: {str(e)}")
    finally:
        await queue.finish()


@app.entrypoint
async def agent_invocation(payload):
    user_message = payload.get(
        "prompt",
        "No prompt found in input, please guide customer to create a json payload with prompt key",
    )

    # 에이전트 태스크를 생성하고 시작
    task = asyncio.create_task(agent_task(user_message))
    app.logger.info(os.environ["CALLBACK_URL"])

    # 태스크가 동시에 실행되도록 보장하면서 스트림 반환
    async def stream_with_task():
        # 결과가 도착하는 대로 스트리밍
        async for item in queue.stream():
            yield item

        # 태스크 완료 보장
        await task

    return stream_with_task()


if __name__ == "__main__":
    app.logger.info("Starting")
    app.run()
