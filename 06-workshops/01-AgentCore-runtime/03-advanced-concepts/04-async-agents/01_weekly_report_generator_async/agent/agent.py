from strands import Agent
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp, PingStatus
import threading
from tools import (
    read_project_status,
    read_team_updates,
    read_metrics,
    read_bug_tracker,
    read_meeting_notes,
    analyze_data_quality,
    cross_reference_data,
    analyze_sentiment,
    calculate_risk_scores,
    generate_bug_severity_chart,
    generate_metrics_trend_chart,
    generate_project_timeline_chart,
    generate_team_velocity_chart,
    build_metrics_forecast_model,
    generate_metrics_forecast_chart,
    upload_report_to_s3,
    save_report,
)

app = BedrockAgentCoreApp()

# 모든 도구가 포함된 Agent 생성
model_id = "global.anthropic.claude-sonnet-4-20250514-v1:0"
model = BedrockModel(model_id=model_id)

weekly_update_agent = Agent(
    name="Weekly Update Generator",
    model=model,
    tools=[
        read_project_status,
        read_team_updates,
        read_metrics,
        read_bug_tracker,
        read_meeting_notes,
        analyze_data_quality,
        cross_reference_data,
        analyze_sentiment,
        calculate_risk_scores,
        generate_bug_severity_chart,
        generate_metrics_trend_chart,
        generate_project_timeline_chart,
        generate_team_velocity_chart,
        build_metrics_forecast_model,
        generate_metrics_forecast_chart,
        save_report,
        upload_report_to_s3,
    ],
    system_prompt="""You are a Weekly Update Generator agent. Your role is to:

1. Collect data from multiple sources (projects, team updates, metrics, bugs, meetings)
2. Analyze data quality and cross-reference information
3. Generate visualizations (bug charts, metrics charts, project timeline, team velocity, forecast charts)
4. Synthesize information into a comprehensive markdown report
5. Save the report using file_write tool to weekly_report_output/weekly_report.md
6. Upload the final report and charts to S3 using upload_report_to_s3

When generating reports, follow this structure:

# Weekly Status Update
## Week of [Date]

## 📊 Executive Summary
- Key highlights and concerns from all data sources
- Project status overview, metric trends, bug status

## 🎯 Project Status
- Project data summary

## 👥 Team Highlights  
- Team update summaries

## 📈 Key Performance Indicators
- Metrics data with status
## 🐛 Bug & Issue Tracker
- Bug tracker data

## 📅 Key Meetings & Decisions
- Meeting notes summaries

## ⚠️ Risks & Blockers
- All blockers from projects and team updates

## ✅ Action Items for Next Week
- Action items from team updates and meetings

## 🎯 Next Week Focus
- Top priorities based on critical bugs and at-risk projects

Do not include markdown image syntax (![...]) in the report. The charts are generated and uploaded to S3 separately.

IMPORTANT: After creating the report content, you MUST:
1. Use file_write to save it to 'weekly_report_output/weekly_report.md'
2. Then call upload_report_to_s3 to upload everything to S3

Work systematically through data collection, analysis, visualization, synthesis, saving, and uploading.""",
)

# ping 핸들러를 위해 활성 작업 수 추적
_active_task_count = 0


def system_busy():
    """시스템에 활성 작업이 있는지 확인합니다."""
    return _active_task_count > 0


@app.ping
def ping():
    """Agent 상태를 보고하는 ping 핸들러입니다."""
    if system_busy():
        return PingStatus.HEALTHY_BUSY
    return PingStatus.HEALTHY


@app.entrypoint
def agent(payload):
    """
    페이로드로 주간 업데이트 Agent를 호출합니다.
    ping 확인 및 보고서 생성을 위한 메서드 라우팅을 지원합니다.
    """
    global _active_task_count

    # ping 요청인지 확인
    method = payload.get("method")
    if method == "ping":
        status = "Healthy" if _active_task_count == 0 else "HealthyBusy"
        return {"status": status, "active_tasks": _active_task_count}

    # 일반 보고서 생성 요청
    user_input = payload.get("prompt")
    print(f"📥 Received request: {user_input}")

    # 비동기 작업 추적 시작
    task_id = app.add_async_task("weekly_report_generation", {"prompt": user_input})
    _active_task_count += 1
    print(f"🔄 Started async task: {task_id} (active: {_active_task_count})")

    # 백그라운드 스레드에서 Agent 실행
    def generate_report():
        global _active_task_count
        try:
            print("🤖 Agent is processing...")
            response = weekly_update_agent(user_input)

            # 다양한 응답 유형 처리
            if isinstance(response, str):
                result = response
            elif hasattr(response, "message"):
                result = response.message["content"][0]["text"]
            elif isinstance(response, dict):
                result = response.get("message", {}).get("content", [{}])[0].get("text", str(response))
            else:
                result = str(response)  # noqa: F841

            print("✅ Report generation completed")
        except Exception as e:
            import traceback

            print(f"❌ Report generation failed: {e}")
            traceback.print_exc()
        finally:
            # 작업을 완료로 표시
            app.complete_async_task(task_id)
            _active_task_count -= 1
            print(f"✅ Task {task_id} marked as complete (active: {_active_task_count})")

    # 백그라운드 스레드 시작
    threading.Thread(target=generate_report, daemon=True).start()

    return {
        "message": f"Weekly report generation started (Task ID: {task_id}). Agent status is now BUSY.",
        "task_id": task_id,
        "status": "BUSY",
    }


if __name__ == "__main__":
    app.run()
