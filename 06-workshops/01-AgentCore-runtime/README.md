# Amazon Bedrock AgentCore Runtime

## 개요
Amazon Bedrock AgentCore Runtime은 AI 에이전트와 도구를 배포하고 확장하도록 설계된 안전한 serverless Runtime입니다.
모든 프레임워크, 모델, 프로토콜을 지원하므로 개발자는 최소한의 코드 변경으로 로컬 프로토타입을 프로덕션용 솔루션으로 전환할 수 있습니다.

Amazon BedrockAgentCore Python SDK는 에이전트 함수를 Amazon Bedrock과 호환되는 HTTP 서비스로 배포할 수 있도록 경량 wrapper를 제공합니다. 모든 HTTP 서버 세부 사항을 처리하므로 에이전트의 핵심 기능에 집중할 수 있습니다.

함수에 `@app.entrypoint` decorator를 적용하고 SDK의 `configure` 및 `launch` 기능을 사용하면 에이전트를 AgentCore Runtime에 배포할 수 있습니다. 이후 애플리케이션은 SDK 또는 boto3, AWS SDK for JavaScript, AWS SDK for Java 같은 AWS 개발자 도구로 이 에이전트를 호출할 수 있습니다.

![Runtime Overview](images/runtime_overview.png)

## 주요 기능

### 유연한 프레임워크 및 모델

- 모든 프레임워크(Strands Agents, LangChain, LangGraph, CrewAI 등)의 에이전트와 도구 배포
- Amazon Bedrock 내외의 모든 모델 사용

### 통합

Amazon Bedrock AgentCore Runtime은 통합 SDK를 통해 다음과 같은 다른 Amazon Bedrock AgentCore 기능과 연동됩니다.

- Amazon Bedrock AgentCore Memory
- Amazon Bedrock AgentCore Gateway
- Amazon Bedrock AgentCore Observability
- Amazon Bedrock AgentCore Tools

이 통합은 개발 과정을 간소화하고 AI 에이전트 구축, 배포, 관리를 위한 종합 플랫폼을 제공하는 것을 목표로 합니다.

### 사용 사례

Runtime은 다음을 포함한 다양한 애플리케이션에 적합합니다.

- 실시간 대화형 AI 에이전트
- 장시간 실행되는 복잡한 AI 워크플로
- 멀티모달 AI 처리(텍스트, 이미지, 오디오, 비디오)

## 자습서 개요

이 자습서에서는 다음 기능을 다룹니다.

- [에이전트 호스팅](01-hosting-agent)
- [MCP 서버 호스팅](02-hosting-MCP-server)
- [고급 개념](03-advanced-concepts)
