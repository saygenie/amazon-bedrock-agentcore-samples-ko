# AgentCore Browser Tool의 OS 수준 작업(InvokeBrowser API)

이 튜토리얼에서는 SigV4로 서명한 REST 호출과 `InvokeBrowser` API를 통해 Amazon Bedrock AgentCore Browser Tool의 **OS 수준 작업**을 사용하는 방법을 살펴봅니다.

## 개요

OS 수준 작업을 사용하면 CDP/Playwright 자동화 계층을 완전히 우회하여 Browser 샌드박스에서 마우스, 키보드, 스크린샷, 스크롤 작업을 직접 수행할 수 있습니다. 다음 대상과 상호 작용할 때 유용합니다.

- **OS 네이티브 대화 상자**: 파일 업로드/다운로드 프롬프트, 인쇄 대화 상자, 인증 팝업
- **브라우저 UI 요소**: 주소 표시줄, 확장 프로그램 팝업, 권한 배너
- **키보드 단축키**: CDP 기반 자동화에서 OS로 보낼 수 없는 Ctrl+S, Ctrl+A, Alt+Tab
- **Canvas/WebGL 콘텐츠**: DOM 선택자가 없는 콘텐츠
- **모든 요소**: CDP 기반 자동화로 조작하기 어려운 요소

## 사용 사례

- Playwright에서 접근할 수 없는 파일 업로드 대화 상자 자동화
- Browser에 OS 수준 키보드 단축키(Ctrl+S, Ctrl+P) 전송
- 마우스 좌표를 사용하여 Canvas/WebGL 애플리케이션과 상호 작용
- OS 수준 요소를 포함한 전체 브라우저 VM 화면 캡처
- OS 수준의 드래그 앤 드롭 작업

## 아키텍처

```
┌──────────┐    SigV4-signed     ┌──────────────────────┐    OS-level     ┌─────────────────┐
│  Client   │ ──────────────────▶│  AgentCore Browser   │ ──────────────▶│  Browser Sandbox │
│ (Notebook │    REST calls      │  InvokeBrowser API   │    actions      │  (Headless VM)   │
│  / Script)│ ◀──────────────────│                      │ ◀──────────────│                  │
└──────────┘   JSON + screenshot └──────────────────────┘   results       └─────────────────┘
```

`InvokeBrowser` API는 SigV4로 서명한 요청을 받아 격리된 브라우저 샌드박스 VM 안에서 실행되는 OS 수준 입력 이벤트로 변환합니다.

## 시작하기

### 사전 요구 사항

- Python 3.10 이상
- Amazon Bedrock AgentCore 액세스가 활성화된 AWS 계정
- 구성된 AWS 자격 증명(`aws sts get-caller-identity`)
- Amazon Bedrock AgentCore를 사용할 수 있는 AWS 리전

> **참고:** 노트북에서 필요한 모든 리소스(IAM 역할, 사용자 지정 Browser)를 자동으로 생성합니다. 리소스를 미리 생성할 필요는 없습니다.

### 설치

```bash
pip install -r requirements.txt
```

### 실행

```bash
jupyter notebook browser-os-actions.ipynb
```

셀을 순서대로 실행합니다. 노트북에서 설정, OS 수준 작업, 리소스 정리를 단계별로 진행합니다.

## 노트북 둘러보기

[browser-os-actions.ipynb 노트북](browser-os-actions.ipynb)에서는 다음 내용을 살펴봅니다.

### 설정

- `bedrock-agentcore.amazonaws.com`에 대한 신뢰 정책과 `InvokeBrowser`, `StartBrowserSession`, `StopBrowserSession` 권한이 있는 IAM 실행 역할 생성
- 퍼블릭 네트워크 구성으로 사용자 지정 AgentCore Browser 생성
- OS 수준 작업을 활성화하여 브라우저 세션 시작

### OS 수준 작업

1. **마우스 작업**: 특정 화면 좌표에서 클릭(왼쪽, 오른쪽, 가운데, 두 번 클릭), 이동, 드래그 수행
2. **스크롤 작업**: 델타 값을 지정할 수 있는 세로 및 가로 스크롤
3. **키보드 작업**: 텍스트 입력, 키 입력(Enter, Tab, Escape, Backspace, 화살표), 키보드 단축키(Ctrl+S, Ctrl+P, Ctrl+Shift+I)
4. **스크린샷**: 전체 브라우저 VM 화면을 PNG 형식으로 캡처하고 인라인으로 표시

### 리소스 정리

브라우저 세션을 중지하고 사용자 지정 Browser를 삭제한 후 IAM 역할과 정책을 제거합니다.

## 샘플 작업

```python
# 마우스 클릭
invoke(endpoint, sid, {"mouseClick": {"x": 600, "y": 370, "button": "LEFT"}}, ...)

# 키보드 입력
invoke(endpoint, sid, {"keyType": {"text": "Hello World"}}, ...)

# 키보드 단축키
invoke(endpoint, sid, {"keyShortcut": {"keys": ["ctrl", "s"]}}, ...)

# 스크린샷
invoke(endpoint, sid, {"screenshot": {"format": "PNG"}}, ...)

# 마우스 스크롤
invoke(endpoint, sid, {"mouseScroll": {"x": 500, "y": 300, "deltaX": 0, "deltaY": -500}}, ...)
```

## 파일

| 파일 | 설명 |
|------|-------------|
| `browser-os-actions.ipynb` | 설정, OS 수준 작업, 리소스 정리가 포함된 대화형 튜토리얼 노트북 |
| `helpers/browser.py` | SigV4로 서명한 요청과 세션 관리를 위한 도우미 함수 |
| `helpers/utils.py` | IAM 역할 생성 및 리소스 정리 유틸리티 |
| `requirements.txt` | Python 종속성 |
| `.env_sample` | AWS 자격 증명 환경 변수 템플릿 |
| `README.md` | 현재 파일 |

## 보안 고려 사항

- 모든 API 호출은 SigV4 인증을 사용하며, 인증되지 않은 요청은 HTTP 403으로 거부됩니다.
- 각 브라우저 세션은 세션과 VM이 1:1로 매핑되는 격리된 샌드박스 VM에서 실행됩니다.
- IAM 역할에는 최소 권한 원칙에 따라 `InvokeBrowser`, `StartBrowserSession`, `StopBrowserSession` 권한만 부여됩니다.
- AWS 자격 증명을 커밋하지 마세요. `.env`(`.gitignore`에서 제외됨) 또는 `isengardcli creds`를 사용합니다.

## 추가 리소스

- [Amazon Bedrock AgentCore Browser 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html)
- [Amazon Bedrock AgentCore Python SDK](https://github.com/aws/bedrock-agentcore-sdk-python)
