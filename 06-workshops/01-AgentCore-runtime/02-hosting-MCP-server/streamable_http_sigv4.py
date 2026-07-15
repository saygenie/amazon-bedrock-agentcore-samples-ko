"""
AWS SigV4 서명을 사용하는 StreamableHTTP 클라이언트 전송 계층

이 모듈은 AWS IAM으로 인증하는 MCP Server와 통신할 수 있도록
MCP StreamableHTTPTransport에 AWS SigV4 요청 서명을 추가합니다.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Generator

import httpx
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials
from mcp.client.streamable_http import (
    GetSessionIdCallback,
    StreamableHTTPTransport,
    streamablehttp_client,
)
from mcp.shared._httpx_utils import McpHttpClientFactory, create_mcp_http_client
from mcp.shared.message import SessionMessage


class SigV4HTTPXAuth(httpx.Auth):
    """AWS SigV4로 요청에 서명하는 HTTPX Auth 클래스입니다."""

    def __init__(
        self,
        credentials: Credentials,
        service: str,
        region: str,
    ):
        self.credentials = credentials
        self.service = service
        self.region = region
        self.signer = SigV4Auth(credentials, service, region)

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        """SigV4로 요청에 서명하고 요청 헤더에 서명을 추가합니다."""

        # AWS 요청 생성
        headers = dict(request.headers)
        # 서버 측 요청 서명 계산에는 'connection' = 'keep-alive' 헤더를 사용하지 않으므로
        # 이 헤더를 포함하면 서명이 일치하지 않음
        headers.pop("connection", None)  # 있으면 제거하고, 없으면 무시

        aws_request = AWSRequest(
            method=request.method,
            url=str(request.url),
            data=request.content,
            headers=headers,
        )

        # SigV4로 요청 서명
        self.signer.add_auth(aws_request)

        # 원래 요청에 서명 헤더 추가
        request.headers.update(dict(aws_request.headers))

        yield request


class StreamableHTTPTransportWithSigV4(StreamableHTTPTransport):
    """
    AWS SigV4 서명을 지원하는 Streamable HTTP 클라이언트 전송 계층입니다.

    Lambda Function URL 또는 API Gateway 뒤에 있는 서버처럼 AWS IAM으로 인증하는
    MCP Server와 통신할 수 있습니다.
    """

    def __init__(
        self,
        url: str,
        credentials: Credentials,
        service: str,
        region: str,
        headers: dict[str, str] | None = None,
        timeout: float | timedelta = 30,
        sse_read_timeout: float | timedelta = 60 * 5,
    ) -> None:
        """SigV4 서명을 사용하도록 StreamableHTTP 전송 계층을 초기화합니다.

        인자:
            url: 엔드포인트 URL입니다.
            credentials: 서명에 사용할 AWS 자격 증명입니다.
            service: AWS 서비스 이름입니다(예: 'lambda').
            region: AWS 리전입니다(예: 'us-east-1').
            headers: 요청에 포함할 선택적 헤더입니다.
            timeout: 일반 작업의 HTTP 제한 시간입니다.
            sse_read_timeout: SSE 읽기 작업의 제한 시간입니다.
        """
        # SigV4 인증 핸들러로 부모 클래스 초기화
        super().__init__(
            url=url,
            headers=headers,
            timeout=timeout,
            sse_read_timeout=sse_read_timeout,
            auth=SigV4HTTPXAuth(credentials, service, region),
        )

        self.credentials = credentials
        self.service = service
        self.region = region


@asynccontextmanager
async def streamablehttp_client_with_sigv4(
    url: str,
    credentials: Credentials,
    service: str,
    region: str,
    headers: dict[str, str] | None = None,
    timeout: float | timedelta = 30,
    sse_read_timeout: float | timedelta = 60 * 5,
    terminate_on_close: bool = True,
    httpx_client_factory: McpHttpClientFactory = create_mcp_http_client,
) -> AsyncGenerator[
    tuple[
        MemoryObjectReceiveStream[SessionMessage | Exception],
        MemoryObjectSendStream[SessionMessage],
        GetSessionIdCallback,
    ],
    None,
]:
    """
    SigV4 인증을 사용하는 Streamable HTTP 클라이언트 전송 계층입니다.

    Lambda Function URL 또는 API Gateway 뒤에 있는 서버처럼 AWS IAM으로 인증하는
    MCP Server와 통신할 수 있습니다.

    생성:
        다음 항목을 포함하는 튜플:
            - read_stream: 서버 메시지를 읽는 스트림
            - write_stream: 서버로 메시지를 보내는 스트림
            - get_session_id_callback: 현재 세션 ID를 가져오는 함수
    """

    async with streamablehttp_client(
        url=url,
        headers=headers,
        timeout=timeout,
        sse_read_timeout=sse_read_timeout,
        terminate_on_close=terminate_on_close,
        httpx_client_factory=httpx_client_factory,
        auth=SigV4HTTPXAuth(credentials, service, region),
    ) as result:
        yield result
