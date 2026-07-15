# MCP Stateless Server 전체 예제

## 개요

이 자습서에서는 세 가지 핵심 기능을 모두 갖춘 완전한 MCP(Model Context Protocol) 서버를 구축하고 Amazon Bedrock AgentCore Runtime에 배포하는 방법을 보여 줍니다.

[MCP 사양](https://modelcontextprotocol.io/specification/2025-11-25/server)은 MCP를 통해 language model에 context를 추가하는 구성 요소를 정의합니다. 이러한 작업을 통해 클라이언트, 서버, language model 간의 풍부한 상호 작용이 가능합니다.
- **Prompts**: Language model 상호 작용을 안내하는 미리 정의된 template 또는 지침
- **Resources**: 모델에 추가 context를 제공하는 구조화된 데이터 또는 콘텐츠
- **Tools**: 모델이 작업을 수행하거나 정보를 검색할 수 있게 하는 실행 함수

## 사전 요구 사항

자습서를 시작하기 전에 다음 항목을 준비하세요.
- 적절한 권한으로 구성된 AWS CLI
- Python 3.13+ 설치
- Jupyter Notebook 환경 설정
- Amazon Bedrock AgentCore 액세스

## 시작하기

이 자습서를 시작하려면 Jupyter Notebook을 열고 단계별 가이드를 따르세요.

**[01_full_mcp_server_e2e](01_full_mcp_server_e2e.ipynb)**

Notebook에는 자습서를 완료하는 데 필요한 모든 코드 예제, 구성, 세부 지침이 포함되어 있습니다.

## 학습 내용

이 자습서에서는 다음 내용을 학습합니다.

* Tool, prompt, resource가 포함된 MCP 서버를 생성하는 방법
* AgentCore Runtime에 배포하는 방법
* 배포된 서버를 호출하는 방법

### 자습서 세부 정보

| 정보                | 세부 정보                                                 |
|:--------------------|:----------------------------------------------------------|
| 자습서 유형         | Runtime에서 Tool, Prompt, Resource 호스팅                 |
| 도구 유형           | MCP 서버                                                  |
| 자습서 구성 요소    | AgentCore Runtime에서 호스팅, MCP 서버 생성               |
| 자습서 분야         | 여러 산업 분야                                            |
| 예제 난이도         | 중간                                                      |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK 및 MCP Client          |

### 자습서 아키텍처

이 자습서에서는 이 예제를 AgentCore Runtime에 배포하는 방법을 설명합니다.

<img src="img/architecture.png" style="width: 80%;">

이 자습서 Notebook에서는 하나의 에이전트를 구축합니다. 먼저 네 개의 도구와 함께 에이전트를 AgentCore Runtime에 배포합니다. 그런 다음 prompt를 추가하도록 업데이트하고, 마지막으로 resource를 배포하도록 다시 업데이트합니다.


### 자습서 주요 기능

* 완전한 MCP 서버 호스팅(Stateless)
* MCP 사양의 Tool, Resource, Prompt 사용
