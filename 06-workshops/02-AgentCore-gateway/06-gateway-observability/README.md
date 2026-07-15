AgentCore Gateway Observability 실습
# Amazon CloudWatch 및 AWS CloudTrail을 사용해 AgentCore Gateway Observability 구성

## 개요

Observability는 Gateway를 통해 배포된 AI 에이전트의 작동 및 성능에 관한 포괄적인 실시간 인사이트를 제공하므로 AgentCore Gateway의 핵심 기능입니다. Observability 기능은 요청량, 성공률, 오류 패턴, 도구 호출 지연 시간, 인증 이벤트 등의 주요 메트릭을 수집하고 표시하여 개발자와 운영자가 에이전트 워크플로의 상태와 효율성을 지속적으로 모니터링할 수 있게 합니다. 이 수준의 모니터링을 통해 사용자 경험이나 시스템 안정성에 영향을 줄 수 있는 이상 징후 또는 병목을 빠르게 식별하고 선제적으로 문제를 해결하며 성능을 조정할 수 있습니다.

상위 수준 메트릭 외에도 AgentCore Gateway observability는 각 에이전트 워크플로의 상세 tracing을 제공합니다. 도구 호출부터 모델 호출 및 memory 검색에 이르는 모든 작업이 OpenTelemetry 표준을 준수하는 span과 trace로 기록됩니다. 이 풍부한 telemetry 데이터는 각 단계의 실행 방식과 소요 시간을 포함하여 에이전트의 내부 의사 결정 프로세스를 투명하게 보여줍니다. 이러한 세분화된 traceability를 사용하면 오류나 비효율이 발생한 정확한 지점을 자세히 살펴볼 수 있으므로 복잡한 장애 또는 예기치 않은 동작을 디버깅하는 데 매우 유용합니다. 또한 Amazon CloudWatch처럼 널리 사용되는 모니터링 플랫폼과 통합하여 통합되고 접근하기 쉬운 운영 개요를 제공합니다.

Observability는 에이전트 활동의 audit trail을 제공하여 엔터프라이즈 환경에 중요한 규정 준수 및 거버넌스 요구 사항을 지원합니다. 또한 사용 패턴을 보여주고 에이전트 워크플로를 조정하여 비용을 줄이거나 속도를 높일 수 있도록 최적화를 지원합니다. 궁극적으로 이러한 observability 기능은 AgentCore Gateway를 black box 인터페이스에서 투명하고 관리 가능한 시스템으로 전환하여 프로덕션 환경에서 안정적이고 확장 가능하며 성능이 뛰어난 AI 에이전트 배포를 지원합니다.
 
## Amazon CloudWatch 및 AWS CloudTrail을 통한 Observability

* Amazon CloudWatch는 AgentCore Gateway의 실시간 성능 모니터링과 운영 문제 해결에 중점을 두며, 지연 시간, 오류율, 사용 패턴에 관한 상세 메트릭과 로그를 제공합니다.
* AWS CloudTrail은 Gateway 관련 API 호출 및 사용자 작업의 전체 이력을 기록하여 보안, 규정 준수 및 감사에 중점을 둡니다.

두 서비스를 함께 사용하면 프로덕션에서 AgentCore Gateway를 관리하기 위한 포괄적인 observability 및 거버넌스 프레임워크를 제공합니다.

![AgentCore Gateway 아키텍처]

#### AgentCore Gateway CloudWatch 메트릭

Gateway는 다음 메트릭을 Amazon CloudWatch에 게시합니다. 이 메트릭은 API 호출, 성능 및 오류에 관한 정보를 제공합니다.

* **Invocations:** 각 Data Plane API에 이루어진 총 요청 수입니다. 각 API 호출은 응답 상태와 관계없이 하나의 호출로 계산됩니다.

* **Throttles:** 서비스가 제한한 요청(상태 코드 429)의 수입니다.

* **SystemErrors:** 5xx 상태 코드로 실패한 요청 수입니다.

* **UserErrors:** 429를 제외한 4xx 상태 코드로 실패한 요청 수입니다.

* **Latency:** 서비스가 요청을 수신한 시점부터 첫 번째 응답 토큰 전송을 시작할 때까지 걸린 시간입니다. 즉, 초기 응답 시간입니다.

* **Duration:** 요청을 수신한 시점부터 최종 응답 토큰을 전송할 때까지 걸린 총시간입니다. 요청의 전체 end-to-end 처리 시간을 나타냅니다.

* **TargetExecutionTime:** Lambda, OpenAPI 등의 대상을 실행하는 데 걸린 총시간입니다. 전체 Latency에서 대상이 차지하는 비중을 파악하는 데 도움이 됩니다.

* **TargetType:** 각 대상 유형(MCP, Lambda, OpenAPI)이 처리한 총 요청 수입니다.

#### AgentCore Gateway CloudWatch Vended Logs

AgentCore는 Gateway 리소스에 관해 다음 정보를 기록합니다.

* Gateway 요청 처리 시작 및 완료
* Target 구성 오류 메시지
* authorization header가 없거나 잘못된 MCP 요청
* 요청 파라미터(tools, method)가 잘못된 MCP 요청

AgentCore는 로그를 Amazon CloudWatch, Amazon S3 또는 Firehose stream으로 출력할 수 있습니다. 이 실습에서는 Amazon CloudWatch를 중점적으로 다룹니다.

AWS 콘솔의 AgentCore Gateway Log Delivery에서 Amazon CloudWatch Logs를 추가하면 이러한 로그는 기본 log group **/aws/vendedlogs/bedrock-agentcore/gateway/APPLICATION_LOGS/{gateway_id}**에 저장됩니다. /**aws/vendedlogs/**로 시작하는 custom log group도 구성할 수 있습니다.

#### AgentCore Gateway CloudWatch Tracing

Amazon Bedrock AgentCore Gateway에서 tracing을 활성화하면 AI 에이전트와 에이전트가 상호 작용하는 도구의 동작 및 성능을 자세히 파악할 수 있습니다. 요청이 Gateway를 통과하는 전체 실행 경로를 수집하므로 복잡한 에이전트 워크플로를 효과적으로 디버깅하고 최적화하며 감사하는 데 필수적입니다.

* **Traces - 최상위 컨테이너**

  * 전체 상호 작용 컨텍스트를 나타냅니다.
  * 에이전트 호출에서 시작하는 전체 실행 경로를 수집합니다.
  * 상호 작용 전체에서 여러 에이전트 호출을 포함할 수 있습니다.
  * 전체 워크플로를 가장 넓은 관점에서 보여줍니다.

* **Requests - 개별 에이전트 호출**

  * trace 내의 단일 요청-응답 주기를 나타냅니다.
  * 각 에이전트 호출은 새 request를 생성합니다.
  * 에이전트에 대한 하나의 완전한 호출과 응답을 수집합니다.
  * 하나의 trace 안에 여러 request가 있을 수 있습니다.

* **Spans - 개별 작업 단위**

  * request 내의 구체적이고 측정 가능한 작업을 나타냅니다.
  * 다음과 같은 세분화된 단계를 수집합니다.
    * 구성 요소 초기화
    * 도구 실행
    * API 호출
    * 처리 단계
  * 기간 분석을 위한 정확한 시작/종료 timestamp가 있습니다.

이 세 observability 구성 요소의 관계는 다음과 같습니다.

  Traces(최상위 수준) - 전체 사용자 대화 또는 상호 작용 컨텍스트를 나타냅니다.

  Requests(중간 수준) - Trace 내의 개별 요청-응답 주기를 나타냅니다.

  Spans(최하위 수준) - Request 내의 특정 작업 또는 단계를 나타냅니다.

          Trace 1
          ├── Request 1.1
          │   ├── Span 1.1.1
          │   ├── Span 1.1.2
          │   └── Span 1.1.3
          ├── Request 1.2
          │   ├── Span 1.2.1
          │   ├── Span 1.2.2
          │   └── Span 1.2.3
          └── Request 1.N

          Trace 2
          ├── Request 2.1
          │   ├── Span 2.1.1
          │   ├── Span 2.1.2
          │   └── Span 2.1.3
          ├── Request 2.2
          │   ├── Span 2.2.1
          │   ├── Span 2.2.2
          │   └── Span 2.2.3
          └── Request 2.N



#### AgentCore Gateway CloudTrail

AgentCore Gateway는 AWS CloudTrail과 완전히 통합되어 있으며, Gateway 인프라 내에서 **API 활동을 추적**하고 운영 이벤트를 확인할 수 있는 포괄적인 로깅 및 모니터링 기능을 제공합니다.

CloudTrail은 AgentCore Gateway에서 서로 다른 두 가지 이벤트 유형을 수집합니다.
* Management event는 자동으로 기록되며 Gateway 리소스 생성, 업데이트 또는 삭제와 같은 control plane 작업을 수집합니다.
* Gateway에서 또는 Gateway 내에서 수행된 리소스 작업(data plane 작업이라고도 함)에 관한 정보를 제공하는 Data event는 대량으로 발생하는 활동이며 기본적으로 기록되지 않으므로 명시적으로 활성화해야 합니다.

CloudTrail은 Gateway 콘솔의 호출 및 코드에서 Gateway API로 보낸 호출을 포함하여 Gateway의 모든 API 호출을 이벤트로 수집합니다. CloudTrail이 수집한 정보를 사용하면 Gateway에 어떤 요청이 이루어졌는지, 누가 언제 요청했는지와 추가 세부 정보를 확인할 수 있습니다[3]. Management event는 AWS 계정의 리소스에 수행된 관리 작업, 즉 control plane 작업에 관한 정보를 제공합니다.

## 실습 개요

이 실습에서는 AgentCore Gateway의 observability를 다룹니다.


| 정보                 | 세부 정보                                                 |
|:---------------------|:----------------------------------------------------------|
| 실습 유형            | 대화형                                                    |
| AgentCore 구성 요소  | AgentCore Gateway, Amazon CloudWatch, AWS CloudTrail      |
| 에이전트 프레임워크  | Strands Agents                                            |
| Gateway Target 유형  | AWS Lambda                                                |
| Inbound Auth IdP     | Amazon Cognito                                            |
| Outbound Auth        | AWS IAM                                                   |
| LLM 모델             | Anthropic Claude Sonnet 4.0                               |
| 실습 구성 요소       | CloudWatch, CloudTrail을 사용한 AgentCore Gateway Observability |
| 실습 분야            | 산업 공통                                                  |
| 예제 난이도          | 쉬움                                                       |
| 사용 SDK             | boto3                                                     |

#### 실습 세부 정보

* 이 실습에서는 Bedrock AgentCore Gateway를 생성하고 get_order와 update_order라는 두 도구가 포함된 Lambda를 대상 유형으로 추가합니다.
* 대상을 CloudWatch로 지정하여 log delivery group을 생성하고 vended log를 관찰합니다.
* Amazon CloudWatch Tracing을 활성화하고 vended log에서 찾은 trace ID를 Trace/Span과 연결하여 자세히 살펴봅니다.
* Strands Agent가 포함된 AgentCore Runtime을 생성하고 Span을 살펴봅니다.
* CloudTrail Management Event 및 Data Event를 구성하고 몇 가지 예시를 확인합니다.

### 리소스

* [AgentCore가 생성하는 Gateway observability 데이터](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-gateway-metrics.html)
* [AgentCore Gateway의 로그 대상 및 tracing 활성화](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html#observability-configure-cloudwatch)
* [CloudTrail을 사용한 AgentCore Gateway API 호출 로깅](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-cloudtrail.html)
* [AgentCore CloudWatch 메트릭 및 경보 설정](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-advanced-observability-metrics.html)
* [CloudTrail을 사용한 Gateway API 호출 로깅](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway-cloudtrail.html)
* [Observability 개념](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-telemetry.html)
