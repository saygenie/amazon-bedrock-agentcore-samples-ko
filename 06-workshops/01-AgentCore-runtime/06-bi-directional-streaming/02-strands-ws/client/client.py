#!/usr/bin/env python3
import argparse
import os
import sys
import webbrowser
import json
import secrets
import string
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

# utils 폴더에서 websocket_helpers 가져오기
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../utils"))
from websocket_helpers import create_presigned_url


class StrandsClientHandler(BaseHTTPRequestHandler):
    """Strands Client를 제공하는 HTTP 요청 핸들러입니다."""

    # 연결 세부 정보를 저장하는 클래스 변수
    websocket_url = None
    session_id = None
    is_presigned = False

    # URL 재생성용 구성 저장
    runtime_arn = None
    region = None
    service = None
    expires = None
    qualifier = None

    def log_message(self, format, *args):
        """더 깔끔한 로깅을 위해 재정의합니다."""
        sys.stderr.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def do_GET(self):
        """GET 요청을 처리합니다."""
        parsed_path = urlparse(self.path)

        if parsed_path.path == "/" or parsed_path.path == "/index.html":
            self.serve_client_page()
        elif parsed_path.path == "/api/connection":
            self.serve_connection_info()
        elif parsed_path.path == "/api/profiles":
            self.serve_profiles()
        else:
            self.send_error(404, "File not found")

    def do_POST(self):
        """POST 요청을 처리합니다."""
        parsed_path = urlparse(self.path)

        if parsed_path.path == "/api/regenerate":
            self.regenerate_url()
        else:
            self.send_error(404, "Endpoint not found")

    def serve_client_page(self):
        """연결이 미리 구성된 HTML Client를 제공합니다."""
        try:
            # HTML 템플릿 읽기
            html_path = os.path.join(os.path.dirname(__file__), "strands-client.html")
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()

            # 제공된 경우 WebSocket URL 주입
            if self.websocket_url:
                html_content = html_content.replace(
                    'id="presignedUrl" placeholder="wss://endpoint/runtimes/arn/ws?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...&X-Amz-Signature=..."',
                    f'id="presignedUrl" placeholder="wss://endpoint/runtimes/arn/ws?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...&X-Amz-Signature=..." value="{self.websocket_url}"',
                )

            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", len(html_content.encode()))
            self.end_headers()
            self.wfile.write(html_content.encode())

        except FileNotFoundError:
            self.send_error(404, "strands-client.html not found")
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")

    def serve_connection_info(self):
        """연결 정보를 JSON으로 제공합니다."""
        response = {
            "websocket_url": self.websocket_url or "",
            "session_id": self.session_id,
            "is_presigned": self.is_presigned,
            "can_regenerate": self.runtime_arn is not None,
            "status": "ok" if self.websocket_url else "no_connection",
        }

        response_json = json.dumps(response, indent=2)

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.send_header("Content-Length", len(response_json.encode()))
        self.end_headers()
        self.wfile.write(response_json.encode())

    def serve_profiles(self):
        """profiles.json 파일을 제공합니다."""
        try:
            profiles_path = os.path.join(os.path.dirname(__file__), "profiles.json")
            with open(profiles_path, "r", encoding="utf-8") as f:
                profiles_content = f.read()

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(profiles_content.encode()))
            self.end_headers()
            self.wfile.write(profiles_content.encode())

        except FileNotFoundError:
            self.send_response(200)
            empty = "[]"
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(empty.encode()))
            self.end_headers()
            self.wfile.write(empty.encode())
        except Exception as e:
            self.send_error(500, f"Internal server error: {str(e)}")

    def regenerate_url(self):
        """Presigned URL을 다시 생성합니다."""
        try:
            if not self.runtime_arn:
                error_response = {
                    "status": "error",
                    "message": "Cannot regenerate URL - not using presigned URL mode",
                }
                response_json = json.dumps(error_response)
                self.send_response(400)
                self.send_header("Content-type", "application/json")
                self.send_header("Content-Length", len(response_json.encode()))
                self.end_headers()
                self.wfile.write(response_json.encode())
                return

            # 새 Presigned URL 생성
            base_url = f"wss://bedrock-agentcore.{self.region}.amazonaws.com/runtimes/{self.runtime_arn}/ws?qualifier={self.qualifier}"

            new_url = create_presigned_url(base_url, region=self.region, service=self.service, expires=self.expires)

            # 클래스 변수 업데이트
            StrandsClientHandler.websocket_url = new_url

            response = {
                "status": "ok",
                "websocket_url": new_url,
                "expires_in": self.expires,
                "message": "URL regenerated successfully",
            }

            response_json = json.dumps(response, indent=2)

            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(response_json.encode()))
            self.end_headers()
            self.wfile.write(response_json.encode())

            print(f"✅ Regenerated presigned URL (expires in {self.expires} seconds)")

        except Exception as e:
            error_response = {"status": "error", "message": str(e)}
            response_json = json.dumps(error_response)
            self.send_response(500)
            self.send_header("Content-type", "application/json")
            self.send_header("Content-Length", len(response_json.encode()))
            self.end_headers()
            self.wfile.write(response_json.encode())


def main():
    parser = argparse.ArgumentParser(
        description="Start web service for Strands WebSocket client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local WebSocket server (no authentication)
  python client.py --ws-url ws://localhost:8080/ws
  
  # AWS Bedrock with presigned URL
  python client.py --runtime-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/RUNTIMEID
  
  # Specify custom port
  python client.py --runtime-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/RUNTIMEID --port 8080
  
  # Custom region
  python client.py --runtime-arn arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/RUNTIMEID \\
    --region us-east-1
""",
    )

    parser.add_argument(
        "--runtime-arn",
        help="Runtime ARN for AWS Bedrock connection (e.g., arn:aws:bedrock-agentcore:region:account:runtime/id)",
    )

    parser.add_argument(
        "--ws-url",
        help="WebSocket server URL for local connections (e.g., ws://localhost:8080/ws)",
    )

    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION", "us-east-1"),
        help="AWS region (default: us-east-1, from AWS_REGION env var)",
    )

    parser.add_argument(
        "--service",
        default="bedrock-agentcore",
        help="AWS service name (default: bedrock-agentcore)",
    )

    parser.add_argument(
        "--expires",
        type=int,
        default=3600,
        help="URL expiration time in seconds for presigned URLs (default: 3600 = 1 hour)",
    )

    parser.add_argument("--qualifier", default="DEFAULT", help="Runtime qualifier (default: DEFAULT)")

    parser.add_argument("--port", type=int, default=8000, help="Web server port (default: 8000)")

    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")

    args = parser.parse_args()

    # 인자 검증
    if not args.runtime_arn and not args.ws_url:
        parser.error("Either --runtime-arn or --ws-url must be specified")

    if args.runtime_arn and args.ws_url:
        parser.error("Cannot specify both --runtime-arn and --ws-url")

    # 제공된 경우 Runtime ARN에서 리전 추출
    if args.runtime_arn:
        arn_parts = args.runtime_arn.split(":")
        if len(arn_parts) >= 4:
            arn_region = arn_parts[3]
            if arn_region and arn_region != args.region:
                args.region = arn_region

    print("=" * 70)
    print("🎙️ Strands Client Web Service")
    print("=" * 70)

    websocket_url = None
    session_id = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(50))
    is_presigned = False

    try:
        # Amazon Bedrock용 Presigned URL 생성
        if args.runtime_arn:
            base_url = f"wss://bedrock-agentcore.{args.region}.amazonaws.com/runtimes/{args.runtime_arn}/ws?qualifier={args.qualifier}"

            print(f"📡 Base URL: {base_url}")
            print(f"🔑 Runtime ARN: {args.runtime_arn}")
            print(f"🌍 Region: {args.region}")
            print(f"🆔 Session ID: {session_id}")
            print(f"⏰ URL expires in: {args.expires} seconds ({args.expires / 60:.1f} minutes)")
            print()
            print("🔐 Generating pre-signed URL...")

            websocket_url = create_presigned_url(
                base_url, region=args.region, service=args.service, expires=args.expires
            )
            is_presigned = True
            print("✅ Pre-signed URL generated successfully!")

        # 로컬 연결에 제공된 WebSocket URL 사용
        else:
            websocket_url = args.ws_url
            print(f"🔗 WebSocket URL: {websocket_url}")
            print("💡 Using local WebSocket connection (no authentication)")

        print(f"🌐 Web Server Port: {args.port}")
        print()

        # 핸들러 클래스에 연결 세부 정보 설정
        StrandsClientHandler.websocket_url = websocket_url
        StrandsClientHandler.session_id = session_id
        StrandsClientHandler.is_presigned = is_presigned

        # URL 재생성용 구성 저장
        if args.runtime_arn:
            StrandsClientHandler.runtime_arn = args.runtime_arn
            StrandsClientHandler.region = args.region
            StrandsClientHandler.service = args.service
            StrandsClientHandler.expires = args.expires
            StrandsClientHandler.qualifier = args.qualifier

        # Web Server 시작
        server_address = ("", args.port)
        httpd = HTTPServer(server_address, StrandsClientHandler)

        server_url = f"http://localhost:{args.port}"

        print("=" * 70)
        print("🌐 Web Server Started")
        print("=" * 70)
        print(f"📍 Server URL: {server_url}")
        print(f"🔗 Client Page: {server_url}/")
        print(f"📊 API Endpoint: {server_url}/api/connection")
        print()
        if is_presigned:
            print("💡 The pre-signed WebSocket URL is pre-populated in the client")
        else:
            print("💡 The WebSocket URL is pre-populated in the client")
        print("💡 Press Ctrl+C to stop the server")
        print("=" * 70)
        print()

        # 브라우저 자동 열기
        if not args.no_browser:
            print("🌐 Opening browser...")
            webbrowser.open(server_url)
            print()

        # 서비스 시작
        httpd.serve_forever()

    except KeyboardInterrupt:
        print("\n\n👋 Shutting down server...")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
