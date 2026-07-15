#!/usr/bin/env python3
"""
Pipecat Vite 클라이언트용 경량 서명 서버입니다.

AgentCore에 배포된 Runtime에 연결할 때 브라우저 클라이언트는
SigV4 서명을 수행할 수 없습니다. 이 스크립트는 다음을 수행합니다.

1. 지정된 Runtime ARN에 대해 SigV4 사전 서명 wss:// URL을 생성합니다.
2. {"ws_url": "<presigned>"}를 반환하는 POST /start 엔드포인트를 제공합니다.
3. 브라우저 앱이 URL을 가져올 수 있도록 Vite 개발 서버가 /start를 여기로 프록시합니다.

로컬 개발 환경(AgentCore 미사용)에서는 필요하지 않습니다. Pipecat
WebSocket 서버가 ws://localhost:8081/ws를 사용하는 /start를 직접 제공합니다.
"""

import argparse
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../utils"))
from websocket_helpers import create_presigned_url


class SigningHandler(BaseHTTPRequestHandler):
    runtime_arn = None
    region = None
    expires = 3600
    qualifier = "DEFAULT"

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[signing-server] {fmt % args}\n")

    def do_POST(self):
        if self.path == "/start":
            self._handle_start()
        else:
            self.send_error(404)

    def do_GET(self):
        if self.path == "/ping":
            self._json_response({"status": "ok"})
        else:
            self.send_error(404)

    def _handle_start(self):
        base_url = (
            f"wss://bedrock-agentcore.{self.region}.amazonaws.com"
            f"/runtimes/{self.runtime_arn}/ws?qualifier={self.qualifier}"
        )
        try:
            signed = create_presigned_url(
                base_url,
                region=self.region,
                service="bedrock-agentcore",
                expires=self.expires,
            )
            print(f"✅ Generated presigned URL (expires in {self.expires}s)")
            self._json_response({"ws_url": signed})
        except Exception as e:
            print(f"❌ Signing error: {e}")
            self._json_response({"error": str(e)}, status=500)

    def _json_response(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


def main():
    parser = argparse.ArgumentParser(description="Signing server for Pipecat client")
    parser.add_argument("--runtime-arn", required=True, help="AgentCore runtime ARN")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-east-1"))
    parser.add_argument("--port", type=int, default=8081, help="Port (default: 8081)")
    parser.add_argument("--expires", type=int, default=3600, help="URL expiry seconds")
    parser.add_argument("--qualifier", default="DEFAULT")
    args = parser.parse_args()

    SigningHandler.runtime_arn = args.runtime_arn
    SigningHandler.region = args.region
    SigningHandler.expires = args.expires
    SigningHandler.qualifier = args.qualifier

    print("=" * 60)
    print("🔐 Pipecat Signing Server")
    print("=" * 60)
    print(f"  Runtime ARN: {args.runtime_arn}")
    print(f"  Region:      {args.region}")
    print(f"  Port:        {args.port}")
    print(f"  Expiry:      {args.expires}s")
    print()
    print("  The Vite client proxies /start to this server.")
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    httpd = HTTPServer(("", args.port), SigningHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Signing server stopped.")


if __name__ == "__main__":
    main()
