# 04 — MCP 통합

AgentCore Harness 에이전트를 **MCP (Model Context Protocol) 서버**에 연결합니다. 도구 호출 코드를 작성하지 않고 선언적 방식으로 타사 공급자가 제공하는 도구(검색, 지식 기반, API 등)를 활용하여 에이전트의 기능을 확장할 수 있습니다.

## 폴더 구성

| 파일 | 유형 | 설명 |
|---|---|---|
| [`04_mcp_integration`](04_mcp_integration.ipynb) | 노트북 | 기본 MCP, 여러 MCP 도구, 인증된 MCP, 오류 처리, 고급 연구 어시스턴트를 다루는 엔드 투 엔드 예제입니다. |

## 학습 내용

- AgentCore Harness 에이전트를 **MCP 서버**(Exa, Brave, 사용자 지정 서버)에 연결하는 방법
- 서로 다른 MCP 공급자를 동시에 사용하는 방법
- 인증된 MCP 서버에 헤더와 구성을 전달하는 방법
- MCP 연결의 오류 처리 및 디버깅
- 프로덕션 환경의 MCP 모범 사례

## 노트북 구성

- **Part 0-1:** 설정 및 예제용 AgentCore Harness 생성
- **Part 2:** 기본 MCP 통합 — Exa Search
- **Part 3:** 여러 MCP 도구 — 검색 공급자 조합
- **Part 4:** 인증을 사용하는 MCP — 헤더 전달
- **Part 5:** 오류 처리 및 디버깅
- **Part 6:** 모범 사례(제한 시간, 인증, 이름 지정, 로깅, 테스트)
- **Part 7:** 고급 예제 — 여러 MCP 도구를 사용하는 Research Assistant
- **정리:** AgentCore Harness 및 IAM 역할 삭제

## 실행 방법

```bash
cd 04-mcp-integration
jupyter notebook 04_mcp_integration.ipynb
# 또는 VSCode에서 열기
```

셀을 위에서 아래로 실행하세요. Part 1에서 AgentCore Harness를 생성한 이후에는 각 Part를 독립적으로 실행할 수 있습니다.

## 핵심 요점

MCP를 사용하면 SDK 코드 없이 단일 JSON 구성만으로 모든 원격 MCP 호환 서버에 연결할 수 있습니다. 에이전트는 사용 가능한 도구를 검색하고 자동으로 호출합니다.

```python
# 최소 MCP 통합
tools = [{
    "type": "remote_mcp",
    "name": "exa",
    "config": {"remoteMcp": {"url": "https://mcp.exa.ai/mcp"}}
}]
response = client.invoke_harness(
    harnessArn=harness_arn,
    runtimeSessionId=session_id,
    messages=[...],
    tools=tools,
)
```
