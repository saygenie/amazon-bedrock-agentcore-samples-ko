# Amazon Bedrock AgentCore SDK Tools 예제

이 폴더에는 AgentCore SDK Tools 사용 방법을 보여 주는 예제가 포함되어 있습니다.

## Browser 도구

* `browser_viewer.py` - 적절한 디스플레이 크기 조절을 지원하는 Amazon Bedrock AgentCore Browser Live Viewer
* `run_live_viewer.py` - Amazon Bedrock AgentCore Browser Live Viewer를 실행하는 독립 실행형 스크립트

## Code Interpreter 도구

* `dynamic_research_agent_langgraph.py` - 동적 코드 생성 기능을 갖춘 LangGraph 기반 연구 에이전트

## 사전 요구 사항

### Python 종속성
```bash
pip install -r requirements.txt
```

필수 패키지: fastapi, uvicorn, rich, boto3, bedrock-agentcore

### AWS 자격 증명(Amazon S3 스토리지용)
녹화물을 Amazon S3에 저장하려면 AWS 자격 증명이 구성되어 있는지 확인합니다.
```bash
aws configure
```

## 예제 실행

### Browser Live Viewer
`02-Agent-Core-browser-tool` 디렉터리에서 다음 명령을 실행합니다.
```bash
python -m interactive_tools.run_live_viewer
```

### 동적 연구 에이전트
`02-Agent-Core-browser-tool` 디렉터리에서 다음 명령을 실행합니다.
```bash
python -m interactive_tools.dynamic_research_agent_langgraph
```

### Amazon Bedrock 모델 액세스
동적 연구 에이전트 예제는 Amazon Bedrock의 Claude 모델을 사용합니다.
- AWS 계정에서 Anthropic Claude 모델에 액세스할 수 있어야 합니다.
- 기본 모델은 `global.anthropic.claude-haiku-4-5-20251001-v1:0`입니다.
- `dynamic_research_agent_langgraph.py`에서 다음 줄을 수정하여 모델을 변경할 수 있습니다.
  ```python
  # DynamicResearchAgent.__init__()의 38번째 줄
  self.llm = ChatBedrockConverse(
      model="global.anthropic.claude-haiku-4-5-20251001-v1:0", # <- 원하는 model로 변경
      region_name=region
  )
  ```
- [Amazon Bedrock 콘솔](https://console.aws.amazon.com/bedrock/home#/modelaccess)에서 모델 액세스를 요청합니다.

### Session Replay
`02-Agent-Core-browser-tool/interactive_tools` 디렉터리에서 다음 명령을 실행합니다.
```bash
python -m live_view_sessionreplay.browser_interactive_session
```

## Browser Live Viewer

Amazon DCV 기술을 사용한 실시간 브라우저 보기 기능입니다.

### 기능

**디스플레이 크기 조절**
- 1280×720 (HD)
- 1600×900 (HD+) - 기본값
- 1920×1080 (Full HD)
- 2560×1440 (2K)

**세션 제어**
- Take Control: 자동화를 비활성화하고 수동으로 상호 작용
- Release Control: 자동화에 제어권 반환

### 구성
- 사용자 지정 포트: `BrowserViewerServer(browser_client, port=8080)`

## 브라우저 세션 녹화 및 재생

디버깅, 테스트, 시연을 위해 브라우저 세션을 녹화하고 재생합니다.

### 중요 제한 사항
이 도구는 비디오 스트림이 아니라 rrweb을 사용하여 DOM 이벤트를 기록합니다.
- 실제 브라우저 콘텐츠(DCV 캔버스)가 검은 상자로 표시될 수 있습니다.
- 픽셀 단위로 정확한 비디오를 녹화하려면 화면 녹화 소프트웨어를 사용합니다.

## 문제 해결

### DCV SDK를 찾을 수 없음
DCV SDK 파일이 `interactive_tools/static/dcvjs/`에 있는지 확인합니다.

### 브라우저 세션이 표시되지 않음
- 브라우저 콘솔(F12)에서 오류 확인
- AWS 자격 증명에 적절한 권한이 있는지 확인

### 재생 중 녹화물을 찾을 수 없음
- 녹화물을 저장할 때 표시된 정확한 경로 확인
- Amazon S3 녹화물에는 전체 S3 URL 사용
- `aws s3 ls` 또는 `ls` 명령으로 파일이 있는지 확인

### Amazon S3 액세스 오류
- AWS 자격 증명이 구성되어 있는지 확인
- Amazon S3 작업에 대한 IAM 권한 확인
- 버킷 이름이 전역적으로 고유한지 확인

## 성능 고려 사항
- 녹화하면 브라우저 성능에 오버헤드가 추가됩니다.
- 일반적인 파일 크기는 분당 1~10MB입니다.
- 녹화가 중지된 후 Amazon S3 업로드가 시작됩니다.
- 재생하려면 먼저 전체 파일을 다운로드해야 합니다.

## 아키텍처 참고 사항
- Live Viewer는 FastAPI를 사용하여 미리 서명된 DCV URL을 제공합니다.
- 녹화 기능은 rrweb 라이브러리를 통해 DOM 이벤트를 캡처합니다.
- 재생 기능은 rrweb-player를 사용합니다.
- 모든 구성 요소가 동일한 BrowserClient 인스턴스를 공유합니다.
- 모듈식 설계이므로 각 구성 요소를 독립적으로 사용할 수 있습니다.
