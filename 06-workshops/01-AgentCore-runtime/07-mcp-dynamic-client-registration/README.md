# AgentCore Runtime 및 Auth0를 사용하는 Dynamic Client Registration

## 개요

이 세션에서는 Amazon Bedrock AgentCore Runtime에서 MCP 도구를 호스팅하는 방법을 설명합니다. 이 MCP는 Auth0의 Dynamic Client Registration 기능과 통합됩니다.

Amazon Bedrock AgentCore Python SDK를 사용하여 에이전트 함수를 Amazon Bedrock AgentCore와 호환되는 MCP 서버로 감쌉니다. SDK가 MCP 서버의 세부 사항을 처리하므로 에이전트의 핵심 기능에 집중할 수 있습니다.

Amazon Bedrock AgentCore Python SDK는 AgentCore Runtime에서 실행할 수 있도록 에이전트 또는 도구 코드를 준비합니다.

## 시작하기

이 자습서를 시작하려면 Jupyter Notebook을 열고 단계별 가이드를 따르세요.

**[deploy_dcr_mcp_agentcore.ipynb](deploy_dcr_mcp_agentcore.ipynb)**

Notebook에는 자습서를 완료하는 데 필요한 모든 코드 예제, 구성, 세부 지침이 포함되어 있습니다.

## 학습 내용

이 자습서에서는 다음 내용을 학습합니다.

* 도구가 포함된 MCP 서버를 생성하는 방법
* 로컬에서 서버를 테스트하는 방법
* DCR을 지원하고 API와 앱을 추가하도록 Auth0 tenant를 구성하는 방법
* Auth0의 DCR과 통합하여 서버를 AWS에 배포하는 방법
* 배포된 서버를 호출하는 방법

### 자습서 세부 정보

| 정보                | 세부 정보                                                 |
|:--------------------|:----------------------------------------------------------|
| 자습서 유형         | 도구 호스팅 + Auth0의 DCR                                 |
| 도구 유형           | MCP 서버                                                  |
| 자습서 구성 요소    | AgentCore Runtime에서 도구 호스팅, MCP 서버 생성          |
| 자습서 분야         | 여러 산업 분야                                            |
| 예제 난이도         | 중간                                                      |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK 및 MCP Client          |

### 자습서 아키텍처

이 자습서에서는 이 예제를 AgentCore Runtime에 배포하는 방법을 설명합니다.

데모를 위해 `add_numbers`, `multiply_numbers`, `greet_users`라는 3개의 도구가 포함된 간단한 MCP 서버를 사용합니다.

<img src="images/architecture.png" width="80%">

### 자습서 주요 기능

* MCP 서버 호스팅
* Dynamic Client Registration (DCR)
* Auth0
