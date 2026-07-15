# Amazon Bedrock AgentCore Gateway와 Amazon Bedrock AgentCore Runtime 통합

[Amazon Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)를 사용하면 인프라나 호스팅을 관리하지 않고도 기존 AWS Lambda 함수 및 API(OpenAPI, Smithy)를 완전관리형 MCP 서버로 전환할 수 있습니다. [Amazon Bedrock AgentCore Runtime](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html)은 AI 에이전트 또는 도구를 배포하고 실행할 수 있도록 특별히 설계된 안전한 serverless 호스팅 환경을 제공합니다. 이 실습에서는 Amazon Bedrock AgentCore Gateway를 AgentCore Runtime 및 [Strands Agents](https://strandsagents.com/latest/)와 통합합니다.

## 실습 세부 정보

| 정보                 | 세부 정보                                                 |
|:---------------------|:----------------------------------------------------------|
| 실습 유형            | 대화형                                                    |
| AgentCore 구성 요소  | AgentCore Gateway, AgentCore Identity, AgentCore Runtime  |
| 에이전트 프레임워크  | Strands Agents                                            |
| Gateway Target 유형  | AWS Lambda, OpenAPI target                                |
| Inbound Auth IdP     | AWS IAM                                                   |
| Outbound Auth        | AWS IAM (AWS Lambda), API Key (OpenAPI target)            |
| LLM 모델             | Anthropic Claude Haiku 4.5, Amazon Nova Pro              |
| 실습 구성 요소       | AgentCore Gateway 생성 및 AgentCore Gateway 호출          |
| 실습 분야            | 산업 공통                                                  |
| 예제 난이도          | 보통                                                       |
| 사용 SDK             | boto3                                                     |

## 실습 아키텍처

이 실습에서는 AWS Lambda 함수와 RESTful API에 정의된 작업을 MCP 도구로 변환하고 Bedrock AgentCore Gateway에 호스팅합니다. AWS SigV4 형식의 AWS IAM 자격 증명을 사용하는 ingress auth를 살펴봅니다. 또한 AgentCore Gateway 도구를 활용하는 Strands Agent를 AgentCore Runtime에 배포합니다.

데모에서는 [Amazon Bedrock](https://aws.amazon.com/bedrock/) 모델을 사용하는 Strands Agent를 사용합니다.

![Runtime Gateway](./images/runtime_gateway.png)
