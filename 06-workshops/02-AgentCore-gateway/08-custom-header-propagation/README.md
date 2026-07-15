# AgentCore Gateway를 사용한 Custom Header 및 Query Parameter 전파

## 개요
최신 엔터프라이즈 에이전트 시스템에서는 distributed tracing, multi-tenant 격리, API versioning 및 rate limiting을 위해 API 호출을 통해 컨텍스트 정보를 전달해야 합니다. AgentCore Gateway는 `metadataConfiguration` 기능을 통해 클라이언트에서 대상으로 custom HTTP header 및 query parameter를 전파하는 기능을 기본 지원하므로 custom interceptor 코드 없이 이러한 엔터프라이즈 패턴을 구현할 수 있습니다.

이 실습에서는 대상 수준에서 header 및 query parameter 전파를 구성하여 Gateway가 correlation ID 및 tenant 식별자와 같은 특정 header와 API 버전 및 환경 flag와 같은 query parameter를 다운스트림 Lambda 함수 또는 MCP 서버에 자동으로 전달하도록 하는 방법을 보여줍니다.

![작동 방식](images/08-custom-header-propagation.png)

### Header Propagation과 Interceptor 방식 비교

AgentCore Gateway는 header 처리를 위해 두 가지 방식을 제공합니다.

**Header Propagation**(이 실습): 특정 header와 query parameter를 자동으로 전달하도록 `metadataConfiguration`을 구성합니다. 변환이 필요하지 않은 correlation ID, tenant ID 및 API 버전과 같은 custom header에 가장 적합합니다.

**Interceptor Lambda**(14-token-exchange-at-request-interceptor 실습): Authorization header token exchange, custom 인증 로직 또는 동적 header 변환과 같이 보안에 민감한 시나리오에 interceptor Lambda를 사용합니다.

### Header Propagation 작동 방식

Gateway 대상을 생성할 때 `metadataConfiguration`을 통해 전파할 header 및 query parameter를 지정합니다.

```python
"metadataConfiguration": {
    "allowedRequestHeaders": ["x-correlation-id", "x-tenant-id"],
    "allowedResponseHeaders": ["x-rate-limit-remaining"],
    "allowedQueryParameters": ["version", "environment"]
}
```

Gateway는 다음 작업을 자동으로 수행합니다.
1. 클라이언트 요청에서 지정된 header 및 query parameter를 추출합니다.
2. 올바른 event 구조로 대상 Lambda에 전달합니다.
3. 지정된 response header를 클라이언트에 반환합니다.

### 주요 사용 사례

* **Distributed Tracing**: Correlation ID로 microservice 전반의 요청 추적
* **Multi-Tenancy**: Tenant 식별자로 적절한 데이터 격리 보장
* **API Versioning**: version parameter로 적절한 구현에 라우팅
* **Environment Routing**: environment flag로 staging 및 production 동작 제어
* **Rate Limiting**: response header로 quota 정보 전달

### 실습 세부 정보


| 정보                 | 세부 정보                                                 |
|:---------------------|:----------------------------------------------------------|
| 실습 유형            | 대화형                                                    |
| AgentCore 구성 요소  | AgentCore Gateway                                         |
| 에이전트 프레임워크  | Strands Agents                                            |
| Gateway Target 유형  | AWS Lambda                                                |
| Inbound Auth IdP     | Amazon Cognito, 다른 IdP도 사용 가능                      |
| Outbound Auth        | AWS IAM                                                   |
| LLM 모델             | Anthropic Claude Haiku 4.5, Amazon Nova Pro              |
| 실습 구성 요소       | AgentCore Gateway 생성 및 AgentCore Gateway 호출          |
| 실습 분야            | 산업 공통                                                  |
| 예제 난이도          | 쉬움                                                       |
| 사용 SDK             | boto3                                                     |

## 실습 아키텍처

### 실습의 주요 기능

* metadataConfiguration을 사용해 custom header 전파 구성
* correlation ID 및 tenant 식별자를 Lambda 대상에 전달
* API versioning 및 environment routing을 위한 query parameter 전파
* rate limiting 정보를 위한 custom response header 반환

## 실습 개요

이 실습에서는 다음 기능을 다룹니다.

- [AgentCore Gateway를 사용한 Custom Header 및 Query Parameter 전파](gateway-interceptor-header-propagation.ipynb)

## 리소스

* [Gateway를 사용한 Header 전파 - AWS 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-headers.html)
* [MetadataConfiguration API 참조](https://docs.aws.amazon.com/bedrock-agentcore-control/latest/APIReference/API_MetadataConfiguration.html)
