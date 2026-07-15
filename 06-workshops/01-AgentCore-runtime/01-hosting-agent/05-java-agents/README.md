# AgentCore Runtime에서 Java 에이전트 호스팅

## 개요

이 자습서에서는 Amazon Bedrock AgentCore Runtime에서 **Java 기반 AI 에이전트**를 호스팅하는 방법을 보여 줍니다. 공식 자습서에서 처음 제공되는 Java 예제입니다.

이 repository의 기존 자습서는 모두 Python을 사용합니다. 이 Java 자습서는 Spring AI와 Embabel Agent Framework를 사용하여 동일한 패턴을 보여 줍니다.

## 자습서 예제

| 예제                                                                       | 프레임워크             | 기능                              | 난이도       |
| -------------------------------------------------------------------------- | ---------------------- | --------------------------------- | ------------ |
| **[01-springai-with-bedrock-model](01-springai-with-bedrock-model)**       | Spring AI              | 대화형 에이전트, ChatClient       | 쉬움         |
| **[02-embabel-with-bedrock-model](02-embabel-with-bedrock-model)**         | Embabel + Spring AI    | GOAP 계획, AgentCore Browser      | 중급         |

## Python 자습서와의 주요 차이점

| 개념                 | Python                          | Java                                              |
|----------------------|---------------------------------|---------------------------------------------------|
| 진입점               | `@app.entrypoint`               | `@AgentCoreInvocation`                            |
| 에이전트 프레임워크  | Strands / LangGraph / CrewAI    | Spring AI ChatClient / Embabel GOAP               |
| Runtime starter      | `bedrock-agentcore-sdk`         | `spring-ai-agentcore-runtime-starter`             |
| Browser 통합         | 직접 SDK 호출                   | `spring-ai-agentcore-browser` + `ChatClient`      |
| Container base       | Python slim                     | Amazon Corretto 21                                |
| Build 도구           | pip / poetry                    | Maven                                             |

## Spring AI AgentCore Library

이 자습서는 [spring-ai-agentcore](https://github.com/spring-ai-community/spring-ai-agentcore) community library를 사용합니다. 이 Spring Boot starter를 사용하면 기존 Spring Boot 애플리케이션이 최소한의 구성으로 Amazon AgentCore Runtime 계약을 준수할 수 있습니다. 자동 구성된 `/invoke` 및 `/ping` 엔드포인트, `@AgentCoreInvocation` annotation, SSE 스트리밍 지원, AgentCore Memory 통합, 브라우저 자동화 등을 제공합니다.

## 사전 요구 사항

* Java 21(Amazon Corretto 권장)
* Maven 3.9+
* Docker
* Node.js 18+ 및 npm(CDK용)
* 적절한 자격 증명으로 구성된 AWS CLI
* AWS CDK CLI (`npm install -g aws-cdk`)
