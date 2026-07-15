#!/usr/bin/env python3
"""
독립 실행형 Session Replay Viewer

이 스크립트를 사용하면 새 브라우저 세션을 생성하지 않고도 S3에 저장된
Bedrock Agentcore 브라우저 녹화를 볼 수 있다.

사용법:
    python3 view_recordings.py --bucket BUCKET_NAME --prefix PREFIX [--session SESSION_ID] [--port PORT]

예:
    python3 view_recordings.py --bucket session-record-test-123456789012 --prefix replay-data

환경 변수:
    AWS_REGION          - AWS 리전(기본값: us-west-2)
    AWS_PROFILE         - 자격 증명에 사용할 AWS 프로필(선택 사항)
"""

import sys
import time
import json
import tempfile
import threading
import webbrowser
import signal
import shutil
import gzip
import io
import argparse
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer

import boto3
from rich.console import Console
from rich.panel import Panel

# 콘솔 생성
console = Console()

# 같은 폴더의 session_replay_viewer에서 직접 가져오기
from session_replay_viewer import SessionReplayViewer, SessionReplayHandler  # noqa: E402


# 가져오기 문제를 방지하도록 이 스크립트에서 CustomS3DataSource를 직접 정의
class CustomS3DataSource:
    """구조가 알려진 S3 녹화용 사용자 지정 데이터 소스"""

    def __init__(self, bucket, prefix, session_id):
        self.s3_client = boto3.client("s3")
        self.bucket = bucket
        self.prefix = prefix
        self.session_id = session_id
        self.session_prefix = f"{prefix}/{session_id}"
        self.temp_dir = Path(tempfile.mkdtemp(prefix="bedrock_agentcore_replay_"))

    def cleanup(self):
        """임시 파일을 정리한다."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def list_recordings(self):
        """녹화 목록을 직접 반환한다."""
        recordings = []

        # 녹화 세부 정보를 얻기 위해 메타데이터 가져오기
        metadata = {}
        try:
            metadata_key = f"{self.session_prefix}/metadata.json"
            print(f"Fetching metadata from: {metadata_key}")
            response = self.s3_client.get_object(Bucket=self.bucket, Key=metadata_key)
            metadata = json.loads(response["Body"].read().decode("utf-8"))
            print(f"✅ Found metadata: {metadata}")
        except Exception as e:
            print(f"⚠️ Could not get metadata: {e}")

        # 이벤트 수를 계산하기 위해 배치 파일 나열
        batch_files = []
        response = self.s3_client.list_objects_v2(Bucket=self.bucket, Prefix=f"{self.session_prefix}/batch-")

        if "Contents" in response:
            batch_files = [obj["Key"] for obj in response["Contents"]]
            print(f"✅ Found {len(batch_files)} batch files")

        # 녹화 항목 생성
        timestamp = int(time.time() * 1000)  # 현재 시각을 기본값으로 사용
        duration = 0
        event_count = 0

        # 타임스탬프를 올바르게 파싱
        if "startTime" in metadata:
            try:
                # ISO 형식 처리
                if isinstance(metadata["startTime"], str):
                    dt = datetime.fromisoformat(metadata["startTime"].replace("Z", "+00:00"))
                    timestamp = int(dt.timestamp() * 1000)
                else:
                    timestamp = metadata["startTime"]
            except Exception as e:
                print(f"⚠️ Error parsing startTime: {e}")

        # 여러 재생 시간 필드 시도
        if "duration" in metadata:
            duration = metadata["duration"]
        elif "durationMs" in metadata:
            duration = metadata["durationMs"]

        # 여러 이벤트 수 필드 시도
        if "eventCount" in metadata:
            event_count = metadata["eventCount"]
        elif "totalEvents" in metadata:
            event_count = metadata["totalEvents"]

        # 올바른 날짜 및 시간 형식 사용
        date_string = datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d %H:%M:%S")

        recordings.append(
            {
                "id": self.session_id,
                "sessionId": self.session_id,
                "timestamp": timestamp,
                "date": date_string,
                "events": event_count,
                "duration": duration,
            }
        )

        return recordings

    def download_recording(self, recording_id):
        """S3에서 녹화를 다운로드한다."""
        print(f"Downloading recording: {recording_id}")

        recording_dir = self.temp_dir / recording_id
        recording_dir.mkdir(exist_ok=True)

        try:
            # 메타데이터 가져오기
            metadata = {}
            try:
                metadata_key = f"{self.session_prefix}/metadata.json"
                response = self.s3_client.get_object(Bucket=self.bucket, Key=metadata_key)
                metadata = json.loads(response["Body"].read().decode("utf-8"))
                print(f"✅ Downloaded metadata: {metadata}")
            except Exception as e:
                print(f"⚠️ No metadata found: {e}")

            # 가능하면 메타데이터에서 배치 파일 가져오기
            batch_files = []
            if "batches" in metadata and isinstance(metadata["batches"], list):
                for batch in metadata["batches"]:
                    if "file" in batch:
                        batch_files.append(f"{self.session_prefix}/{batch['file']}")

            # 메타데이터에 배치 파일이 없으면 직접 찾기
            if not batch_files:
                response = self.s3_client.list_objects_v2(Bucket=self.bucket, Prefix=f"{self.session_prefix}/batch-")

                if "Contents" in response:
                    batch_files = [obj["Key"] for obj in response["Contents"]]

            all_events = []
            print(f"Processing {len(batch_files)} batch files: {batch_files}")

            for key in batch_files:
                try:
                    print(f"Downloading batch file: {key}")
                    response = self.s3_client.get_object(Bucket=self.bucket, Key=key)

                    # gzip으로 압축된 JSON Lines로 읽기 시도
                    with gzip.GzipFile(fileobj=io.BytesIO(response["Body"].read())) as gz:
                        content = gz.read().decode("utf-8")
                        print(f"Read {len(content)} bytes of content")

                        # 각 줄을 JSON 이벤트로 처리
                        for line in content.splitlines():
                            if line.strip():
                                try:
                                    event = json.loads(line)
                                    # 이벤트 검증
                                    if "type" in event and "timestamp" in event:
                                        all_events.append(event)
                                    else:
                                        print("⚠️ Skipping invalid event (missing required fields)")
                                except json.JSONDecodeError:
                                    print(f"⚠️ Invalid JSON in line: {line[:50]}...")

                        print(f"  Added {len(all_events)} events")

                except Exception as e:
                    print(f"⚠️ Error processing file {key}: {e}")
                    import traceback

                    traceback.print_exc()

            print(f"✅ Loaded {len(all_events)} events")

            # 로드된 이벤트가 없으면 샘플 이벤트 생성
            if len(all_events) < 2:
                print("⚠️ Insufficient events, creating sample events for testing")
                all_events = [
                    {
                        "type": 2,
                        "timestamp": timestamp,
                        "data": {
                            "href": "https://example.com",
                            "width": 1280,
                            "height": 720,
                        },
                    }
                    for timestamp in range(int(time.time() * 1000), int(time.time() * 1000) + 10000, 1000)
                ]
                # 최소 DOM 스냅샷 이벤트 추가
                all_events.append(
                    {
                        "type": 4,
                        "timestamp": int(time.time() * 1000) + 1000,
                        "data": {
                            "node": {
                                "type": 1,
                                "childNodes": [
                                    {
                                        "type": 2,
                                        "tagName": "html",
                                        "attributes": {},
                                        "childNodes": [
                                            {
                                                "type": 2,
                                                "tagName": "body",
                                                "attributes": {},
                                                "childNodes": [
                                                    {
                                                        "type": 3,
                                                        "textContent": "Sample content",
                                                    }
                                                ],
                                            }
                                        ],
                                    }
                                ],
                            }
                        },
                    }
                )

            # 파싱된 녹화 반환
            return {"metadata": metadata, "events": all_events}

        except Exception as e:
            print(f"❌ Error downloading recording: {e}")
            import traceback

            traceback.print_exc()
            return None


# 이 스크립트에서 CustomSessionReplayHandler를 직접 정의
class CustomSessionReplayHandler(SessionReplayHandler):
    """세션 재생 뷰어용 사용자 지정 HTTP 요청 핸들러"""

    def serve_recordings_list(self):
        """녹화 목록을 반환한다. HTML 응답 문제 수정용."""
        try:
            recordings = self.data_source.list_recordings()
            response = json.dumps(recordings)

            # 반환 내용을 확인하기 위한 디버그 출력
            print(f"Serving recordings list: {response[:100]}...")

            # 올바른 콘텐츠 유형과 헤더 설정
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(response)))
            # 문제 방지를 위한 CORS 헤더 추가
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()

            # 응답을 바이트로 작성
            self.wfile.write(response.encode("utf-8"))

        except Exception as e:
            print(f"❌ Error in serve_recordings_list: {e}")
            import traceback

            traceback.print_exc()

            # 빈 녹화 배열이 포함된 올바른 JSON 오류 응답 반환
            error_response = json.dumps({"error": str(e), "recordings": []})
            self.send_response(200)  # 클라이언트가 오류를 처리할 수 있도록 200 사용
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(error_response)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(error_response.encode("utf-8"))

    def download_and_serve_recording(self, recording_id):
        """녹화를 다운로드해 제공한다. HTML 응답 문제 수정용."""
        try:
            recording_data = self.data_source.download_recording(recording_id)

            if recording_data:
                response = json.dumps({"success": True, "data": recording_data})

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(response.encode("utf-8"))
            else:
                error_response = json.dumps({"success": False, "error": "Recording not found"})
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(error_response)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(error_response.encode("utf-8"))

        except Exception as e:
            print(f"❌ Error in download_and_serve_recording: {e}")
            import traceback

            traceback.print_exc()

            error_response = json.dumps({"success": False, "error": str(e)})
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(error_response)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(error_response.encode("utf-8"))

    def do_OPTIONS(self):
        """CORS 프리플라이트용 OPTIONS 요청을 처리한다."""
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()


# 이 스크립트에서 CustomSessionReplayViewer를 직접 정의
class CustomSessionReplayViewer(SessionReplayViewer):
    def start(self):
        """사용자 지정 핸들러로 재생 뷰어 서버를 시작한다."""
        # 뷰어 디렉터리가 있는지 확인
        self.viewer_path.mkdir(parents=True, exist_ok=True)

        # 사용 가능한 포트 찾기
        port = self.find_available_port()

        # 요청 핸들러 생성
        def handler_factory(*args, **kwargs):
            return CustomSessionReplayHandler(self.data_source, self.viewer_path, *args, **kwargs)

        # 서버 시작
        self.server = HTTPServer(("", port), handler_factory)

        # 스레드에서 시작
        server_thread = threading.Thread(target=self.server.serve_forever)
        server_thread.daemon = True
        server_thread.start()

        url = f"http://localhost:{port}"

        console.print(
            Panel(
                f"[bold cyan]Session Replay Viewer Running[/bold cyan]\n\n"
                f"URL: [link]{url}[/link]\n\n"
                f"[yellow]Press Ctrl+C to stop[/yellow]",
                title="Ready",
                border_style="green",
            )
        )

        # 브라우저 열기
        webbrowser.open(url)

        # 종료 처리
        def signal_handler(sig, frame):
            console.print("\n[yellow]Shutting down...[/yellow]")
            self.server.shutdown()
            if hasattr(self.data_source, "cleanup"):
                self.data_source.cleanup()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)

        # 실행 상태 유지
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(description="Standalone Session Replay Viewer")
    parser.add_argument("--bucket", required=True, help="S3 bucket name containing recordings")
    parser.add_argument("--prefix", required=True, help="S3 prefix where recordings are stored")
    parser.add_argument("--session", help="Specific session ID to view (optional)")
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port to run the viewer on (default: 8080)",
    )
    parser.add_argument("--profile", help="AWS profile to use (optional)")
    args = parser.parse_args()

    # 지정된 AWS 프로필이 있으면 사용
    if args.profile:
        print(f"Using AWS profile: {args.profile}")
        boto3.setup_default_session(profile_name=args.profile)

    # 버킷 확인용 S3 클라이언트 생성
    s3 = boto3.client("s3")

    try:
        # 버킷 존재 여부와 접근 권한 확인
        s3.head_bucket(Bucket=args.bucket)
        print(f"✅ Connected to bucket: {args.bucket}")
    except Exception as e:
        print(f"❌ Error accessing bucket {args.bucket}: {e}")
        sys.exit(1)

    # 특정 세션을 지정하지 않았으면 최신 세션 찾기
    if not args.session:
        print(f"Finding sessions in s3://{args.bucket}/{args.prefix}/")
        try:
            response = s3.list_objects_v2(Bucket=args.bucket, Prefix=args.prefix)

            if "Contents" not in response:
                print("No objects found in S3 location")
                sys.exit(1)

            # metadata.json을 포함하는 고유한 디렉터리 이름 모두 가져오기
            session_dirs = set()

            for obj in response["Contents"]:
                key = obj["Key"]
                if "metadata.json" in key:
                    # 경로에서 세션 디렉터리 추출
                    session_dir = key.split("/")[-2]
                    session_dirs.add(session_dir)
                    print(f"Found session with metadata: {session_dir}")

            if not session_dirs:
                print("No session directories with metadata.json found")
                sys.exit(1)

            # 최신 세션을 찾도록 세션 디렉터리 정렬
            session_dirs = sorted(list(session_dirs))
            args.session = session_dirs[-1]
            print(f"Using latest session: {args.session}")

        except Exception as e:
            print(f"❌ Error listing sessions: {e}")
            sys.exit(1)

    # 특정 세션용 데이터 소스 생성
    data_source = CustomS3DataSource(bucket=args.bucket, prefix=args.prefix, session_id=args.session)

    # 뷰어 시작
    print(f"🎬 Starting session replay viewer for: {args.session}")
    print(f"  Bucket: {args.bucket}")
    print(f"  Prefix: {args.prefix}")
    viewer = CustomSessionReplayViewer(data_source=data_source, port=args.port)
    viewer.start()  # Ctrl+C를 누를 때까지 차단됨


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Process interrupted by user")
        sys.exit(0)
