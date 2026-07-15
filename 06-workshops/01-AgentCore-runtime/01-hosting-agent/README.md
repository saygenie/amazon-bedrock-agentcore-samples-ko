# AgentCore Runtime에서 AI 에이전트 호스팅

## 개요

이 자습서에서는 Amazon Bedrock AgentCore Python SDK를 사용하여 **Amazon Bedrock AgentCore Runtime**에서 AI 에이전트를 호스팅하는 방법을 보여 줍니다. 에이전트 코드를 Amazon Bedrock 인프라와 원활하게 통합되는 표준 HTTP 서비스로 전환하는 방법을 학습합니다.

AgentCore Runtime은 **프레임워크와 모델에 독립적인** 플랫폼으로, 모든 에이전틱 프레임워크(Strands Agents, LangGraph, CrewAI)와 모든 LLM 모델(Amazon Bedrock, OpenAI 등)로 구축한 에이전트를 호스팅할 수 있습니다.

Amazon Bedrock AgentCore Python SDK는 다음 작업을 수행하는 wrapper입니다.

- 에이전트 코드를 AgentCore 표준 프로토콜로 **변환**
- HTTP 및 MCP 서버 인프라를 자동으로 **처리**
- 에이전트의 핵심 기능에 **집중할 수 있도록 지원**
- 두 가지 프로토콜 유형 **지원**
  - **HTTP Protocol**: 기존 요청/응답 방식의 REST API 엔드포인트
  - **MCP Protocol**: 도구 및 에이전트 서버용 Model Context Protocol

### 서비스 아키텍처

에이전트를 호스팅하면 SDK가 다음 작업을 자동으로 수행합니다.

- 포트 `8080`에서 에이전트 호스팅
- 두 가지 주요 엔드포인트 제공
  - **`/invocations`**: 기본 에이전트 상호 작용(JSON 입력 → JSON/SSE 출력)
  - **`/ping`**: 모니터링용 상태 확인

![Hosting agent](images/hosting_agent_python_sdk.png)

에이전트를 AgentCore Runtime에 배포할 준비가 되면 Amazon Bedrock AgentCore StarterKit을 사용하여 배포할 수 있습니다.

Starter Kit으로 에이전트 배포를 구성하고 실행하여 에이전트 구성과 AgentCore Runtime 엔드포인트가 포함된 Amazon ECR repository를 생성한 다음, 생성된 엔드포인트를 호출해 검증할 수 있습니다.

![StarterKit](../images/runtime_overview.png)

배포가 완료되면 AWS의 AgentCore Runtime 아키텍처는 다음과 같습니다.

![RuntimeArchitecture](../images/runtime_architecture.png)

## 자습서 예제

이 자습서에는 시작에 도움이 되는 4개의 실습 예제가 포함되어 있습니다.

| 예제                                                                   | 프레임워크     | 모델           | 설명                                       |
| ---------------------------------------------------------------------- | -------------- | -------------- | ------------------------------------------ |
| **[01-strands-with-bedrock-model](01-strands-with-bedrock-model)**     | Strands Agents | Amazon Bedrock | AWS 네이티브 모델을 사용한 기본 에이전트 호스팅 |
| **[02-langgraph-with-bedrock-model](02-langgraph-with-bedrock-model)** | LangGraph      | Amazon Bedrock | LangGraph 에이전트 워크플로                 |
| **[03-strands-with-openai-model](03-strands-with-openai-model)**       | Strands Agents | OpenAI         | 외부 LLM 제공업체와 통합                   |
| **[06-strands-with-skills](06-strands-with-skills)**                   | Strands Agents | Amazon Bedrock | AgentSkills plugin을 사용한 Skills 기반 에이전트 호스팅 |

## 주요 이점

- **프레임워크 독립성**: 모든 Python 기반 에이전트 프레임워크에서 작동
- **유연한 모델 선택**: Amazon Bedrock, OpenAI 및 기타 LLM 제공업체의 LLM 지원
- **프로덕션 지원**: 기본 제공 상태 확인 및 모니터링
- **간편한 통합**: 최소한의 코드 변경만 필요
- **확장성**: 엔터프라이즈 워크로드에 맞게 설계

## 시작하기

선호하는 프레임워크와 모델 조합에 따라 위 자습서 예제 중 하나를 선택하세요. 각 예제에는 다음 내용이 포함되어 있습니다.

- 단계별 설정 지침
- 전체 코드 샘플
- 테스트 지침
- 모범 사례

## 다음 단계

자습서를 완료하면 다음 작업을 수행할 수 있습니다.

- 이러한 패턴을 다른 프레임워크 및 모델로 확장
- 프로덕션 환경에 배포
- 기존 애플리케이션과 통합
- 에이전트 인프라 확장
