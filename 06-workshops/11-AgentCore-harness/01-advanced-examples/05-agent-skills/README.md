# 05 — Agent Skills

에이전트의 microVM 파일 시스템에 설치되는 파일, 코드, 지침 묶음인 **Agent Skills**로 AgentCore Harness 에이전트를 확장합니다. Agent Skills를 사용하면 모델을 재훈련하지 않고도 스프레드시트 생성, 재무 보고서 작성 등의 도메인별 기능을 에이전트에 제공할 수 있습니다.

## 폴더 구성

| 파일 | 유형 | 설명 |
|---|---|---|
| [`05_agent_skills.ipynb`](05_agent_skills.ipynb) | 노트북 | Agent Skills 설치, `skills` 파라미터를 사용한 호출, 세션당 여러 Agent Skills 사용, 고급 재무 보고서 예제를 다룹니다. |

## 학습 내용

- **Agent Skills**의 개념과 중요성
- 에이전트의 VM에 Agent Skills를 설치하는 방법(`invoke_agent_runtime_command` 사용)
- 호출에서 `skills` 파라미터를 사용하는 방법
- 파일 형식 Agent Skills(xlsx, pdf, docx)를 사용하는 방법
- 세션 하나에 여러 Agent Skills를 설치하는 방법
- Agent Skills와 다른 접근 방식(MCP, 사용자 지정 컨테이너 등)을 선택하는 기준

## 노트북 구성

- **Part 0-1:** 설정 및 표준 AgentCore Harness 생성
- **Part 2:** VM에 Agent Skills 설치 및 설치 확인
- **Part 3:** 호출에서 Agent Skills 사용(여행 예산 스프레드시트 예제)
- **Part 4:** 세션 하나에 여러 Agent Skills 설치
- **Part 5:** 고급 예제 — 재무 보고서 생성
- **Part 6:** 모범 사례(세션 수명 주기, 오류, 사용자 지정 Agent Skills)
- **Part 7:** Agent Skills와 다른 접근 방식을 선택하는 기준
- **정리:** AgentCore Harness 및 IAM 역할 삭제

## 실행 방법

```bash
cd 05-agent-skills
jupyter notebook 05_agent_skills.ipynb
# 또는 VSCode에서 열기
```

셀을 위에서 아래로 실행하세요. Agent Skills를 사용하는 호출보다 먼저 Part 2(Agent Skills 설치)를 실행해야 합니다.

## 핵심 요점

Agent Skills는 에이전트의 파일 시스템에 있으며 `path`로 참조됩니다. 이 경로를 `skills` 파라미터에 지정하고, 세션마다 한 번 설치한 후 여러 호출에서 사용할 수 있습니다.

```python
# Skill을 한 번 설치
command_client.invoke_agent_runtime_command(
    harnessArn=harness_arn,
    runtimeSessionId=session_id,
    command="npx skills add xlsx",
)

# 이후 호출에서 참조
response = client.invoke_harness(
    harnessArn=harness_arn,
    runtimeSessionId=session_id,
    messages=[{"role": "user", "content": [{"text": "Create a budget spreadsheet..."}]}],
    skills=[{"path": "/tmp/skills/xlsx"}],
)
```

## Agent Skills와 다른 접근 방식 비교

| 요구 사항 | 사용할 방식 |
|---|---|
| 외부 API/동적 데이터 | **MCP 도구** |
| 사용자 지정 런타임/VM 수준 종속성 | **사용자 지정 컨테이너** |
| 사전 패키징된 기능(파일 형식, 템플릿) | **Agent Skills** |
| 간단한 일회성 지침 | **시스템 프롬프트** |
