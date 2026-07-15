# Gateway용 Lambda 함수 도구 구현

## 개요
Bedrock AgentCore Gateway를 사용하면 인프라나 호스팅을 관리하지 않고도 기존 Lambda 함수를 완전관리형 MCP 서버로 전환할 수 있습니다. 기존 AWS Lambda 함수를 가져오거나, 도구를 제공하는 새 Lambda 함수를 추가할 수 있습니다. Gateway는 이러한 모든 도구에 일관된 Model Context Protocol(MCP) 인터페이스를 제공합니다. Gateway는 수신 요청과 대상 리소스로 나가는 연결 모두에 안전한 액세스 제어를 보장하기 위해 이중 인증 모델을 사용합니다. 이 프레임워크는 Gateway 대상에 액세스하려는 사용자를 검증하고 권한을 부여하는 Inbound Auth와, 인증된 사용자를 대신해 Gateway가 백엔드 리소스에 안전하게 연결하도록 지원하는 Outbound Auth라는 두 가지 핵심 구성 요소로 이루어집니다. 이 두 인증 메커니즘은 IAM 자격 증명과 OAuth 기반 인증 흐름을 모두 지원하며, 사용자와 대상 리소스 사이에 안전한 연결을 제공합니다.

![작동 방식](images/lambda-iam-gateway.png)

![작동 방식](images/lambda-gw-iam-inbound.png)


### Lambda context 객체 이해
Gateway가 Lambda 함수를 호출할 때 context.client_context 객체를 통해 특별한 컨텍스트 정보를 전달합니다. 이 컨텍스트에는 호출에 관한 중요한 메타데이터가 포함되어 있으며, 함수는 이를 사용해 요청 처리 방법을 결정할 수 있습니다.
context.client_context.custom 객체에서는 다음 속성을 사용할 수 있습니다.
* bedrockagentcoreEndpointId: 요청을 수신한 Gateway 엔드포인트의 ID입니다.
* bedrockagentcoreTargetId: 요청을 함수로 라우팅한 Gateway 대상의 ID입니다.
* bedrockagentcoreMessageVersion: 요청에 사용된 메시지 형식의 버전입니다.
* bedrockagentcoreToolName: 호출되는 도구의 이름입니다. Lambda 함수가 여러 도구를 구현할 때 특히 중요합니다.
* bedrockagentcoreSessionId: 현재 호출의 세션 ID입니다. 동일한 세션에서 이루어진 여러 도구 호출을 연결하는 데 사용할 수 있습니다.

Lambda 함수 코드에서 이러한 속성에 액세스하여 호출되는 도구를 확인하고 그에 맞게 함수 동작을 조정할 수 있습니다.

![작동 방식](images/lambda-context-object.png)

### 응답 형식 및 오류 처리

Lambda 함수는 Gateway가 해석하여 클라이언트에 전달할 수 있는 응답을 반환해야 합니다. 응답은 JSON 객체여야 하며, statusCode 필드에는 작업 결과를 나타내는 다음 HTTP 상태 코드 중 하나가 있어야 합니다.
* 200: 성공
* 400: 잘못된 요청(클라이언트 오류)
* 500: 내부 서버 오류

body 필드는 문자열 또는 더 복잡한 응답을 나타내는 JSON 문자열일 수 있습니다. 구조화된 응답을 반환하려면 JSON 문자열로 직렬화해야 합니다.

### 오류 처리
적절한 오류 처리는 클라이언트에 유용한 피드백을 제공하는 데 중요합니다. Lambda 함수는 예외를 포착하고 적절한 오류 응답을 반환해야 합니다.

### 테스트

`__context__` 필드는 Gateway가 함수를 호출할 때 실제로 전달하는 이벤트의 일부가 아닙니다. 컨텍스트 객체를 시뮬레이션하기 위한 테스트 용도로만 사용됩니다.
Lambda 콘솔에서 테스트할 때는 시뮬레이션된 컨텍스트를 처리하도록 함수를 수정해야 합니다. 이 방법을 사용하면 Lambda 함수를 Gateway 대상으로 배포하기 전에 여러 도구 이름과 입력 파라미터로 테스트할 수 있습니다.

### 교차 계정 Lambda 액세스

Lambda 함수가 Gateway와 다른 AWS 계정에 있다면 Gateway가 함수를 호출할 수 있도록 Lambda 함수에 리소스 기반 정책을 구성해야 합니다. 다음은 정책 예시입니다.

```
{
  "Version": "2012-10-17",
  "Id": "default",
  "Statement": [
    {
      "Sid": "cross-account-access",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::123456789012:role/GatewayExecutionRole"
      },
      "Action": "lambda:InvokeFunction",
      "Resource": "arn:aws:lambda:us-west-2:987654321098:function:MyLambdaFunction"
    }
  ]
}
```
이 정책에서 각 값은 다음을 의미합니다.
- 123456789012는 Gateway가 배포된 계정 ID입니다.
- GatewayExecutionRole은 Gateway가 사용하는 IAM 역할입니다.
- 987654321098는 Lambda 함수가 배포된 계정 ID입니다.
- MyLambdaFunction은 Lambda 함수의 이름입니다.

이 정책을 추가하면 Lambda 함수가 다른 계정에 있더라도 Gateway 대상 구성에 해당 함수의 ARN을 지정할 수 있습니다.

### 실습 세부 정보


| 정보                 | 세부 정보                                                 |
|:---------------------|:----------------------------------------------------------|
| 실습 유형            | 대화형                                                    |
| AgentCore 구성 요소  | AgentCore Gateway, AgentCore Identity, AWS IAM            |
| 에이전트 프레임워크  | Strands Agents                                            |
| LLM 모델             | Anthropic Claude Haiku 4.5, Amazon Nova Pro              |
| 실습 구성 요소       | AgentCore Gateway 생성 및 AgentCore Gateway 호출          |
| 실습 분야            | 산업 공통                                                  |
| 예제 난이도          | 쉬움                                                       |
| 사용 SDK             | boto3                                                     |

## 실습 아키텍처

### 실습의 주요 기능

* Lambda 함수를 MCP 도구로 노출
* OAuth 및 IAM을 사용해 도구 호출 보호

## 실습 개요

이 실습에서는 다음 기능을 다룹니다.

- [OAuth Inbound Auth를 사용해 AWS Lambda 함수를 MCP 도구로 전환](01-gateway-target-lambda-oauth.ipynb)

- [AWS IAM Inbound Auth를 사용해 AWS Lambda 함수를 MCP 도구로 전환](02-gateway-target-lambda-iam.ipynb)
