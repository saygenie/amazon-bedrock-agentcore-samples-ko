# 02 — 웹 애플리케이션 시각적 테스트 에이전트

AI 기반 **자동 시각적 QA** 파이프라인입니다. 에이전트에 웹 애플리케이션을 제공하면 격리된 AgentCore Harness microVM 안에서 애플리케이션을 빌드, 실행, 테스트하고 각 단계의 스크린샷을 반환합니다.

## 폴더 구성

| 파일 | 유형 | 설명 |
|---|---|---|
| [`02_webapp_visual_testing_agent.ipynb`](02_webapp_visual_testing_agent.ipynb) | 노트북 | 엔드 투 엔드 데모입니다. 에이전트가 TodoMVC 애플리케이션을 생성하고 `localhost:3000`에서 서비스한 후 Puppeteer를 설치하고 테스트 스크립트를 작성 및 실행합니다. 이어서 스크린샷을 촬영해 노트북으로 가져옵니다. |

## 핵심 아이디어

AgentCore Harness microVM은 자체 파일 시스템과 네트워크 스택을 갖춘 완전한 Linux ARM64 환경입니다. 따라서 에이전트는 다음 작업을 수행할 수 있습니다.

1. 시스템 도구 설치(`apt-get install chromium`)
2. 웹 애플리케이션 복제 또는 생성
3. `localhost`에서 웹 서버 시작
4. `puppeteer-core`를 설치하고 Headless Browser 제어
5. 스크린샷을 촬영하여 `/tmp`에 저장
6. 검토할 수 있도록 스크린샷 반환

이 모든 작업은 격리된 환경에서 이루어지며 로컬 시스템에는 영향을 주지 않습니다.

## 활용 가치

"복제 → 빌드 → 서비스 → 테스트 → 스크린샷" 패턴을 사용하면 다음 작업을 수행할 수 있습니다.

- **CI/CD 시각적 검증** — 커밋할 때마다 에이전트가 애플리케이션을 실행하고 시각적 테스트를 수행하여 코드 리뷰 전에 회귀를 표시
- **버전 간 비교** — 두 버전을 나란히 빌드하고 각각 스크린샷을 촬영한 후 차이 비교
- **탐색적 QA** — 에이전트에 URL과 *"find anything that looks broken"*이라는 요청을 전달하면 에이전트가 탐색하고 상호 작용한 결과를 보고
- **자동 문서화** — 에이전트가 애플리케이션을 단계별로 살펴보고 주석이 포함된 스크린샷 가이드 생성
- **에이전트에 피드백 제공** — *"Do these screenshots look correct?"*라고 질문하여 시각적 QA 루프를 완전히 자동화

## 핵심 원리

Puppeteer는 웹 서버와 **동일한 VM 안에서 실행**되므로 네트워크 격리 문제 없이 브라우저 도구에서 `localhost:3000`에 바로 접근할 수 있습니다. 이는 브라우저 도구와 VM 셸을 동일한 네트워크 네임스페이스에 두는 이점 중 하나입니다.

## 노트북 실습 과정

| Part | 수행 내용 |
|---|---|
| **0** | 설정 — IAM 역할, Boto3 클라이언트, 베타 서비스 모델 로드 |
| **1** | **Node.js 20 컨테이너**가 연결된 AgentCore Harness 생성 |
| **2** | 환경 준비 — `apt-get install chromium`, 독립형 TodoMVC 애플리케이션 생성, 포트 3000에서 `npx serve` 시작, `npm install puppeteer-core` |
| **3** | **에이전트가 테스트를 작성하고 실행** — 자연어로 테스트 단계를 설명하면 에이전트가 Puppeteer 스크립트를 작성 및 실행하고 스크린샷 저장 |
| **4** | `ExecuteCommand`를 통해 Base64로 인코딩된 스크린샷을 가져와 인라인으로 표시 |
| **5** | 정리 |

## 테스트 흐름(Part 3)

에이전트에는 자연어로 다음 작업을 지시합니다.

1. Launch Chromium headless, open `http://localhost:3000`
2. Screenshot → `/tmp/screenshot_1.png` (empty app)
3. Add three todos
4. Screenshot → `/tmp/screenshot_2.png` (three todos)
5. Click the first todo's checkbox to mark it complete
6. Screenshot → `/tmp/screenshot_3.png` (one completed)
7. Close the browser

에이전트는 Puppeteer 스크립트를 직접 작성하고 `node /tmp/test.mjs`로 실행한 후 스크린샷 목록을 표시합니다. 생성된 스크린샷을 가져와 인라인으로 렌더링합니다.

## 실행 방법

```bash
cd 02-use-cases/02-webapp-visual-testing
jupyter notebook 02_webapp_visual_testing_agent.ipynb
# 또는 VSCode에서 열기
```

셀을 위에서 아래로 실행하세요. `npm install puppeteer-core`가 큰 종속성 트리를 다운로드하므로 **Part 2**를 완료하는 데 약 1분이 걸립니다.

## 자체 애플리케이션에 적용하는 방법

TodoMVC 생성 단계를 자체 빌드 과정으로 교체합니다.

```python
# Part 2 - 일반 패턴
run_command("git clone https://github.com/your/repo /tmp/app")
run_command("cd /tmp/app && npm install && npm run build")
run_command("cd /tmp/app && nohup npm start > /tmp/server.log 2>&1 &")
run_command("cd /tmp && npm install puppeteer-core")
# 이어서 Part 3 - 테스트 scenario를 자연어로 에이전트에 설명
```

그 밖의 테스트 생성, 실행, 스크린샷 촬영 과정은 동일합니다.

## 알려진 제한 사항

이 패턴과 별개인 독립 실행형 `agentcore_browser` 도구는 서로 다른 네트워크 네임스페이스에서 실행되므로 VM의 `localhost`에 있는 서비스에 **접근할 수 없습니다**. 자세한 내용은 AgentCore Harness 출시 문서의 기능 요청을 참조하세요. 이 노트북은 `ExecuteCommand`를 통해 **VM 안에서 Puppeteer를 직접 실행**하여 브라우저와 서버가 동일한 네트워크 스택을 공유하도록 함으로써 이 제한을 우회합니다.
