"""AgentCore Gateway의 MCP 엔드포인트를 위한 경량 raw HTTP 클라이언트입니다.

이 디렉터리의 Notebook에 있는 prompt/resource/streaming/session/elicitation
데모에서 사용합니다. 셀이 전송 처리(bearer 인증, MCP-Protocol-Version 협상,
JSON-RPC envelope, target 간 pagination, SSE streaming, session ID 관리)보다
시연 중인 MCP 메서드에 집중할 수 있게 합니다.

SDK 클라이언트(Strands MCPClient, 공식 mcp 클라이언트)는 프로토콜 버전을
자동으로 협상하지만 raw `requests.post`는 그렇지 않으므로 명시적인
`MCP-Protocol-Version` 헤더를 사용합니다. 기본값은
`01-mcp-server-target.ipynb` 2.3단계에서 gateway를 생성할 때 사용한 버전과
일치합니다.

Pagination 참고: `tools/list` 및 기타 목록 메서드는 **target별로** 페이지를
나눕니다. 같은 gateway에 DEFAULT target 하나와 DYNAMIC target 하나를 연결하면
첫 호출은 한 target의 항목과 `nextCursor`를 반환하고, 해당 cursor로 다시 호출하면
다음 target의 항목을 반환하는 식으로 진행됩니다. 아래 `list_all_*` 헬퍼는
소진될 때까지 `nextCursor`를 따라가 병합된 목록을 반환합니다.

Streaming 참고: `notifications/progress`, 로그 메시지 또는 elicitation/sampling
요청을 내보내는 도구는 SSE 응답에서 파싱한 각 JSON-RPC frame을 생성하는
generator인 `stream_tool_call(...)`로 읽습니다. 버퍼링된 `call_tool`은 서버가
중간 frame을 내보내지 않고 단일 결과를 반환하는 도구에만 사용할 수 있습니다.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterator, List, Optional

import requests

DEFAULT_PROTOCOL_VERSION = "2025-11-25"


class GatewayMCPClient:
    """gateway의 MCP 엔드포인트로 보내는 JSON-RPC POST를 감싸는 소형 클라이언트입니다."""

    def __init__(
        self,
        gateway_url: str,
        get_token: Callable[[], str],
        protocol_version: str = DEFAULT_PROTOCOL_VERSION,
        session_id: Optional[str] = None,
    ) -> None:
        """클라이언트를 생성합니다.

        ``session_id``(선택 사항)는 모든 요청에 되돌려 보낼 클라이언트 제공
        ``Mcp-Session-Id``입니다. 업스트림 MCP 서버가 ``stateless_http=True``로
        실행되어 서버 발급 session ID가 없지만, AgentCore Runtime이 요청을 특정
        microvm에 고정하게 할 때 유용합니다. 요청과 응답 헤더 모두에서
        ``Mcp-Session-Id``를 허용하는 target ``metadataConfiguration``과 함께
        사용합니다.

        나중에 ``initialize()``를 호출하여 gateway가 session ID를 반환하면
        캡처된 값이 이 값을 대체합니다.
        """
        self.gateway_url = gateway_url
        self._get_token = get_token
        self._protocol_version = protocol_version
        self._session_id: Optional[str] = session_id

    @property
    def session_id(self) -> Optional[str]:
        return self._session_id

    def set_session_id(self, session_id: Optional[str]) -> None:
        """이후 모든 요청에 되돌려 보낼 클라이언트 측 ``Mcp-Session-Id``를 재정의합니다."""
        self._session_id = session_id

    def _headers(
        self, accept: str = "application/json, text/event-stream"
    ) -> Dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept": accept,
            "MCP-Protocol-Version": self._protocol_version,
            "Authorization": f"Bearer {self._get_token()}",
        }
        if self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        return h

    def _rpc(
        self, method: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": method.replace("/", "-") + "-request",
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        return requests.post(
            self.gateway_url, headers=self._headers(), json=payload, timeout=3600
        ).json()

    def rpc_raw(
        self, method: str, params: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        """:meth:`_rpc`와 비슷하지만 raw ``requests.Response``를 반환하여 호출자가
        HTTP 상태, 응답 헤더, 파싱하지 않은 본문을 검사할 수 있게 합니다.
        2xx 이외의 상태가 예상되고 ``response.json()``이 오류 본문과 함께 성공하거나
        파싱에 실패할 수 있는 진단/오류 계약 검사(누락되거나 유효하지 않은
        `Mcp-Session-Id` 등)에 유용합니다. 어느 경우든 상태 코드가 신호입니다.
        """
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": method.replace("/", "-") + "-raw",
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        return requests.post(
            self.gateway_url, headers=self._headers(), json=payload, timeout=3600
        )

    def _paginate(self, method: str, items_key: str) -> List[Dict[str, Any]]:
        """페이지마다 ``result.nextCursor``를 따라가 병합된 항목을 반환합니다."""
        items: List[Dict[str, Any]] = []
        cursor: Optional[str] = None
        while True:
            params = {"cursor": cursor} if cursor else None
            resp = self._rpc(method, params)
            result = resp.get("result", {})
            items.extend(result.get(items_key, []))
            cursor = result.get("nextCursor")
            if not cursor:
                return items

    # --- 수명 주기 ------------------------------------------------------

    def initialize(
        self,
        capabilities: Optional[Dict[str, Any]] = None,
        client_info: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """`initialize`를 보낸 다음 `notifications/initialized`를 보냅니다.

        이후 요청에서 되돌려 보낼 수 있도록 응답 헤더에서 `Mcp-Session-Id`를
        캡처합니다(session이 활성화된 gateway에서 설정).
        """
        body = {
            "jsonrpc": "2.0",
            "id": "initialize-request",
            "method": "initialize",
            "params": {
                "protocolVersion": self._protocol_version,
                "capabilities": capabilities or {},
                "clientInfo": client_info
                or {"name": "GatewayMCPClient", "version": "0.1"},
            },
        }
        r = requests.post(
            self.gateway_url, headers=self._headers(), json=body, timeout=3600
        )
        sid = r.headers.get("mcp-session-id")
        if sid:
            self._session_id = sid

        # `notifications/initialized`(응답 본문 없음)
        requests.post(
            self.gateway_url,
            headers=self._headers(),
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            timeout=3600,
        )

        try:
            result = r.json()
        except ValueError:
            result = {"raw": r.text}

        return {
            "session_id": sid,
            "protocol_version": r.headers.get("mcp-protocol-version"),
            "http_status": r.status_code,
            "result": result,
        }

    # --- 도구 -----------------------------------------------------------

    def list_tools(self, cursor: Optional[str] = None) -> Dict[str, Any]:
        params = {"cursor": cursor} if cursor else None
        return self._rpc("tools/list", params)

    def list_all_tools(self) -> List[Dict[str, Any]]:
        """target별 pagination을 따라 모든 target의 도구를 반환합니다."""
        return self._paginate("tools/list", "tools")

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """버퍼링된 도구 호출입니다. 서버가 중간 frame을 내보내지 않고 단일 결과를
        반환하는 도구에만 사용할 수 있습니다. progress, logging, elicitation 또는
        sampling을 내보내는 도구에는 :meth:`stream_tool_call`을 사용합니다.
        """
        return self._rpc("tools/call", {"name": name, "arguments": arguments})

    def call_tool_json_only(
        self,
        name: str,
        arguments: Dict[str, Any],
        request_id: Any = "tools-call-request",
    ) -> Dict[str, Any]:
        """`Accept: application/json`만 강제하는 버퍼링된 도구 호출입니다.

        streaming이 활성화된 gateway에서 비 streaming 클라이언트와의 하위 호환성을
        보여 줍니다. gateway는 SSE stream 대신 단일 JSON document를 반환합니다.

        `http_status`, `content_type`, `body`가 있는 dict를 반환합니다. `body`는 raw
        응답 텍스트이며, 적절한 경우 호출자가 `json.loads`를 사용할 수 있습니다.
        """
        body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        r = requests.post(
            self.gateway_url,
            headers=self._headers(accept="application/json"),
            json=body,
            timeout=3600,
        )
        return {
            "http_status": r.status_code,
            "content_type": r.headers.get("content-type"),
            "body": r.text,
        }

    def stream_tool_call(
        self,
        name: str,
        arguments: Dict[str, Any],
        progress_token: Optional[str] = None,
        request_id: Any = "tools-call-request",
    ) -> Iterator[Dict[str, Any]]:
        """streaming tools/call에서 파싱한 JSON-RPC frame을 생성하는 generator입니다.

        도착 순서대로 다음 항목을 생성합니다.
          - `notifications/progress` messages (when `progress_token` is set)
          - `notifications/message` log frames
          - `elicitation/create` / `sampling/createMessage` server-initiated requests
          - `notifications/elicitation/complete` server notifications
          - `request_id`를 키로 하는 최종 도구 결과 frame

        gateway가 사용할 수 있는 두 전송 방식을 모두 처리합니다.
          - `Content-Type: text/event-stream`: 각 `data:` 행을 frame으로 생성
          - `Content-Type: application/json`: 버퍼링된 단일 JSON 본문을 생성
            (예: gateway가 SSE channel을 여는 대신 일회성 오류 응답을 반환하는 경우)

        일치하는 응답 frame을 생성한 후 generator가 종료됩니다.
        """
        params: Dict[str, Any] = {"name": name, "arguments": arguments}
        if progress_token is not None:
            params["_meta"] = {"progressToken": progress_token}
        body = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": params,
        }
        with requests.post(
            self.gateway_url,
            headers=self._headers(accept="text/event-stream"),
            json=body,
            stream=True,
            timeout=3600,
        ) as resp:
            ct = resp.headers.get("content-type", "")
            if ct.startswith("application/json"):
                # 버퍼링된 단일 JSON document(SSE 없음)
                try:
                    yield resp.json()
                except ValueError:
                    pass
                return
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"):
                    continue
                try:
                    yield json.loads(raw[5:].strip())
                except json.JSONDecodeError:
                    continue

    def _post_response(self, request_id: Any, result: Dict[str, Any]) -> int:
        """JSON-RPC 응답을 gateway에 POST로 돌려보냅니다. 진행 중인 `tools/call`의
        SSE stream으로 도착하는 서버 시작 요청(`elicitation/create`,
        `sampling/createMessage`)에 응답하는 데 사용합니다.
        """
        r = requests.post(
            self.gateway_url,
            headers=self._headers(),
            json={"jsonrpc": "2.0", "id": request_id, "result": result},
            timeout=3600,
        )
        return r.status_code

    def call_tool_streaming(
        self,
        name: str,
        arguments: Dict[str, Any],
        *,
        elicitation_callback: Optional[
            Callable[[Dict[str, Any]], Dict[str, Any]]
        ] = None,
        sampling_callback: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        notification_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        progress_token: Optional[str] = None,
        request_id: Any = "tools-call-streaming",
    ) -> Dict[str, Any]:
        """도구를 호출하고 서버 시작 요청을 callback으로 전달합니다.

        Callback은 모두 선택 사항이며 동기 방식입니다.

          - ``elicitation_callback(params: dict) -> dict``
            서버가 ``elicitation/create``를 내보낼 때 호출됩니다. form mode에는
            ``{"action": "accept", "content": {...}}`` 같은 dict를, URL mode에는
            ``{"action": "accept"}``를 반환해야 합니다.
          - ``sampling_callback(params: dict) -> dict``
            서버가 ``sampling/createMessage``를 내보낼 때 호출됩니다.
            ``CreateMessageResult`` 형태의 dict를 반환해야 합니다.
            (``{"role": "assistant", "content": {...}, "model": "..."}``).
          - ``progress_callback(params: dict) -> None``
            각 ``notifications/progress`` frame에서 호출됩니다.
          - ``notification_callback(method: str, params: dict) -> None``
            기타 ``notifications/*``에서 호출됩니다(예: ``message``,
            ``elicitation/complete``).

        ``request_id``를 키로 하는 최종 응답에 대해
        ``{"result": ..., "error": ...}``를 반환합니다.
        """
        for msg in self.stream_tool_call(
            name, arguments, progress_token=progress_token, request_id=request_id
        ):
            method = msg.get("method")
            msg_id = msg.get("id")
            if method == "elicitation/create" and elicitation_callback is not None:
                reply = elicitation_callback(msg.get("params") or {})
                self._post_response(msg_id, reply)
            elif method == "sampling/createMessage" and sampling_callback is not None:
                reply = sampling_callback(msg.get("params") or {})
                self._post_response(msg_id, reply)
            elif method == "notifications/progress" and progress_callback is not None:
                progress_callback(msg.get("params") or {})
            elif (
                isinstance(method, str)
                and method.startswith("notifications/")
                and notification_callback is not None
            ):
                notification_callback(method, msg.get("params") or {})
            elif msg_id == request_id:
                return {"result": msg.get("result"), "error": msg.get("error")}
        return {"result": None, "error": None}

    # --- 프롬프트 -------------------------------------------------------

    def list_prompts(self, cursor: Optional[str] = None) -> Dict[str, Any]:
        params = {"cursor": cursor} if cursor else None
        return self._rpc("prompts/list", params)

    def list_all_prompts(self) -> List[Dict[str, Any]]:
        return self._paginate("prompts/list", "prompts")

    def get_prompt(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return self._rpc("prompts/get", {"name": name, "arguments": arguments})

    # --- 리소스 ---------------------------------------------------------

    def list_resources(self, cursor: Optional[str] = None) -> Dict[str, Any]:
        params = {"cursor": cursor} if cursor else None
        return self._rpc("resources/list", params)

    def list_all_resources(self) -> List[Dict[str, Any]]:
        return self._paginate("resources/list", "resources")

    def read_resource(self, uri: str) -> Dict[str, Any]:
        return self._rpc("resources/read", {"uri": uri})

    def list_resource_templates(self, cursor: Optional[str] = None) -> Dict[str, Any]:
        params = {"cursor": cursor} if cursor else None
        return self._rpc("resources/templates/list", params)

    def list_all_resource_templates(self) -> List[Dict[str, Any]]:
        return self._paginate("resources/templates/list", "resourceTemplates")
