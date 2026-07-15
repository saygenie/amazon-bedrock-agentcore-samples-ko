#!/usr/bin/env python3
"""
Bedrock-AgentCore Browser Live Viewer를 실행하는 독립 실행형 스크립트.
interactive_tools 모듈 사용 방법을 보여준다.
"""

import time


from rich.console import Console
from rich.panel import Panel
from bedrock_agentcore.tools.browser_client import BrowserClient
from .browser_viewer import BrowserViewerServer

console = Console()


def main():
    """화면 크기를 지정하여 브라우저 라이브 뷰어를 실행한다."""
    console.print(
        Panel(
            "[bold cyan]Bedrock-AgentCore Browser Live Viewer[/bold cyan]\n\n"
            "This demonstrates:\n"
            "• Live browser viewing with DCV\n"
            "• Configurable display sizes (not limited to 900×800)\n"
            "• Proper display layout callbacks\n\n"
            "[yellow]Note: Requires Amazon DCV SDK files[/yellow]",
            title="Browser Live Viewer",
            border_style="blue",
        )
    )

    try:
        # 1단계: 브라우저 세션 생성
        console.print("\n[cyan]Step 1: Creating browser session...[/cyan]")
        browser_client = BrowserClient(region="us-west-2")
        session_id = browser_client.start()
        console.print(f"✅ Session created: {session_id}")

        # 2단계: 뷰어 서버 시작
        console.print("\n[cyan]Step 2: Starting viewer server...[/cyan]")
        viewer = BrowserViewerServer(browser_client, port=8000)
        viewer_url = viewer.start(open_browser=True)

        # 3단계: 기능 표시
        console.print("\n[bold green]Viewer Features:[/bold green]")
        console.print("• Default display: 1600×900 (configured via displayLayout callback)")
        console.print("• Size options: 720p, 900p, 1080p, 1440p")
        console.print("• Real-time display updates")
        console.print("• Take/Release control functionality")

        console.print("\n[yellow]Press Ctrl+C to stop[/yellow]")

        # 실행 상태 유지
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Shutting down...[/yellow]")
        if "browser_client" in locals():
            browser_client.stop()
            console.print("✅ Browser session terminated")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
