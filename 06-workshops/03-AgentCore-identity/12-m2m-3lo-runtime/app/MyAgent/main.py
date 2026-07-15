"""
세 가지 아웃바운드 인증 흐름을 보여주는 AgentCore Runtime 에이전트입니다.

  1. M2M (machine-to-machine / client credentials):
     에이전트가 사용자 상호 작용 없이 서비스 계정으로 내부 API를 호출합니다.
     auth_flow="M2M"으로 @requires_access_token을 사용합니다.

  2. GitHub Auth Code (3LO / USER_FEDERATION):
     에이전트가 사용자의 GitHub 리포지터리를 나열합니다.
     첫 호출은 동의 URL을 반환하고, 이후 호출은 저장된 토큰을 사용합니다.

  3. Google Auth Code (3LO / USER_FEDERATION):
     에이전트가 사용자의 Google Calendar 이벤트를 읽습니다.
     첫 호출은 동의 URL을 반환하고, 이후 호출은 저장된 토큰을 사용합니다.

인바운드 인증: Cognito JWT(agentcore/agentcore.json에서 구성)
"""

import json
import os
from datetime import datetime, timezone

import httpx
from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity.auth import requires_access_token, requires_api_key
from bedrock_agentcore.services.identity import TokenPoller


class _NonBlockingPoller(TokenPoller):
    """동의 URL을 사용자에게 전달할 수 있도록 즉시 반환합니다.

    첫 호출(아직 토큰 없음)에서는 URL로 on_auth_url을 호출한 후 이 폴러가
    차단하지 않고 즉시 ""을 반환합니다. 도구는 에이전트에 동의 URL을 반환합니다.
    사용자가 동의를 완료한 뒤 두 번째로 호출하면 GetResourceOauth2Token이
    토큰을 직접 반환합니다.
    """

    async def poll_for_token(self) -> str:
        return ""


app = BedrockAgentCoreApp()
_model = BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")

# ---------------------------------------------------------------------------
# M2M: client credentials 권한 부여(Cognito 머신 클라이언트)
# 에이전트가 사용자 개입 없이 서비스 계정으로 인증
# ---------------------------------------------------------------------------

_m2m_token_cache: dict = {}
_api_key_cache: dict = {}


@requires_api_key(provider_name="OutboundApiKey")
async def _fetch_api_key(*, api_key: str) -> None:
    _api_key_cache["key"] = api_key


@requires_access_token(
    provider_name="M2MProvider",
    auth_flow="M2M",
    scopes=["https://api.m2m-demo.internal/read"],
)
async def _fetch_m2m_token(*, access_token: str) -> None:
    _m2m_token_cache["token"] = access_token


@tool
async def get_weather_m2m(location: str) -> str:
    """Get weather using M2M (client credentials) authentication.

    Demonstrates the client_credentials OAuth2 grant: the agent authenticates
    as a service account (no user interaction), obtains an access token, and
    uses it to call the OpenWeatherMap API.

    The M2M token proves the agent's identity. The API key is passed separately.
    This shows two auth mechanisms working together.

    Args:
        location: City name (e.g. "Seattle", "London", "New York")
    """
    if "token" not in _m2m_token_cache:
        await _fetch_m2m_token(access_token="")

    token = _m2m_token_cache.get("token", "")
    if not token:
        return "Failed to obtain M2M token. Check the M2MProvider credential configuration."

    # AgentCore Identity에서 API 키 가져오기(Sample 10과 동일)
    if "key" not in _api_key_cache:
        await _fetch_api_key(api_key="")
    api_key = _api_key_cache.get("key", "")
    if not api_key:
        return "OpenWeatherMap API key not found. Add an OutboundApiKey credential."

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": location, "appid": api_key, "units": "imperial"},
            )
            resp.raise_for_status()
            data = resp.json()

        return json.dumps(
            {
                "m2m_auth": "success (client_credentials token obtained)",
                "location": f"{data.get('name', location)}, {data.get('sys', {}).get('country', '')}",
                "temperature_f": round(data["main"]["temp"]),
                "feels_like_f": round(data["main"]["feels_like"]),
                "condition": data["weather"][0]["description"],
                "humidity": f"{data['main']['humidity']}%",
                "wind_mph": round(data["wind"]["speed"]),
            },
            indent=2,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            return "Invalid OpenWeatherMap API key."
        return f"Weather API error: {exc.response.status_code}"
    except Exception as exc:
        return f"Error: {exc}"


# ---------------------------------------------------------------------------
# GitHub 3LO: authorization code 권한 부여
# 에이전트가 사용자의 GitHub 리포지터리를 나열
# ---------------------------------------------------------------------------

_github_auth_url_cache: dict = {}


def _on_github_auth_url(url: str) -> None:
    _github_auth_url_cache["url"] = url


@tool
def get_github_repos() -> str:
    """List the authenticated user's GitHub repositories.

    On first call, returns an authorization URL if consent is needed.
    After the user grants access, call this tool again to retrieve repos.
    """
    callback_url = os.environ.get("CALLBACK_URL", "http://localhost:9090/oauth2/callback")

    @requires_access_token(
        provider_name="GitHub3LOProvider",
        auth_flow="USER_FEDERATION",
        scopes=["repo", "read:user"],
        on_auth_url=_on_github_auth_url,
        callback_url=callback_url,
        token_poller=_NonBlockingPoller(),
    )
    def _fetch_and_list(access_token: str = "") -> str:
        if not access_token:
            auth_url = _github_auth_url_cache.get("url", "")
            if auth_url:
                return (
                    f"GitHub authorization required. Please visit this URL and grant access:\n"
                    f"{auth_url}\n\n"
                    "After authorizing, invoke the agent again to retrieve your repositories."
                )
            return "GitHub authorization required. Please try again in a moment."

        with httpx.Client() as client:
            user_resp = client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_resp.raise_for_status()
            username = user_resp.json().get("login", "Unknown")

            repos_resp = client.get(
                f"https://api.github.com/search/repositories?q=user:{username}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            repos_resp.raise_for_status()
            repos = repos_resp.json().get("items", [])

        if not repos:
            return f"No repositories found for GitHub user '{username}'."

        lines = [f"GitHub repositories for {username}:"]
        for repo in repos:
            line = f"  - {repo['name']}"
            if repo.get("language"):
                line += f" ({repo['language']})"
            if repo.get("description"):
                line += f": {repo['description']}"
            lines.append(line)
        return "\n".join(lines)

    return _fetch_and_list()


# ---------------------------------------------------------------------------
# Google 3LO: authorization code 권한 부여
# 에이전트가 사용자의 Google Calendar 이벤트를 읽음
# ---------------------------------------------------------------------------

_google_auth_url_cache: dict = {}


def _on_google_auth_url(url: str) -> None:
    _google_auth_url_cache["url"] = url


@tool
def get_calendar_events() -> str:
    """Get today's Google Calendar events for the authenticated user.

    On first call, returns an authorization URL if consent is needed.
    After the user grants access, call this tool again to retrieve events.
    """
    callback_url = os.environ.get("CALLBACK_URL", "http://localhost:9090/oauth2/callback")
    today = datetime.now(timezone.utc).date().isoformat()

    @requires_access_token(
        provider_name="Google3LOProvider",
        auth_flow="USER_FEDERATION",
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        on_auth_url=_on_google_auth_url,
        callback_url=callback_url,
        token_poller=_NonBlockingPoller(),
    )
    def _fetch_and_list(access_token: str = "") -> str:
        if not access_token:
            auth_url = _google_auth_url_cache.get("url", "")
            if auth_url:
                return (
                    f"Google authorization required. Please visit this URL and grant access:\n"
                    f"{auth_url}\n\n"
                    "After authorizing, invoke the agent again to retrieve your calendar events."
                )
            return "Google authorization required. Please try again in a moment."

        with httpx.Client() as client:
            resp = client.get(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers={"Authorization": f"Bearer {access_token}"},
                params={
                    "timeMin": f"{today}T00:00:00Z",
                    "timeMax": f"{today}T23:59:59Z",
                    "singleEvents": "true",
                    "orderBy": "startTime",
                },
            )
            resp.raise_for_status()
            events = resp.json().get("items", [])

        if not events:
            return f"No calendar events found for today ({today})."

        lines = [f"Google Calendar events for {today}:"]
        for event in events:
            start = event.get("start", {}).get("dateTime", event.get("start", {}).get("date", ""))
            lines.append(f"  - {start}: {event.get('summary', '(no title)')}")
        return "\n".join(lines)

    return _fetch_and_list()


# ---------------------------------------------------------------------------
# 에이전트 진입점
# ---------------------------------------------------------------------------

_agent: Agent | None = None


@app.entrypoint
async def handler(payload: dict) -> str:
    global _agent

    if _agent is None:
        _agent = Agent(
            model=_model,
            tools=[get_weather_m2m, get_github_repos, get_calendar_events],
            system_prompt=(
                "You are a helpful assistant with access to three capabilities:\n"
                "1. get_weather_m2m(location) — gets weather using M2M credentials (no user consent). "
                "Uses OpenWeatherMap API with client_credentials token.\n"
                "2. get_github_repos — lists the user's GitHub repositories (requires GitHub OAuth consent on first use)\n"
                "3. get_calendar_events — gets today's Google Calendar events (requires Google OAuth consent on first use)\n"
                "For OAuth flows, return the authorization URL to the user and ask them to complete consent.\n"
                "Always use your tools — never say you can't do something if a tool can handle it."
            ),
        )

    user_input = payload.get("prompt", "")
    response = _agent(user_input)
    return response.message["content"][0]["text"]


if __name__ == "__main__":
    app.run()
