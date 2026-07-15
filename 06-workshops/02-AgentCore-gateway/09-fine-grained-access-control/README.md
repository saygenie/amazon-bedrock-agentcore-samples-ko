# JWT scope 및 AgentCore Gateway Interceptor를 사용한 Fine-Grained Access Control

## 개요
최신 엔터프라이즈 에이전트 시스템은 검색, retrieval, 주문 시스템, 분석, 문서 pipeline 등 여러 도구를 노출하는 경우가 많습니다. 모든 사용자가 모든 도구에 액세스하도록 허용해서는 안 되며 역할(Analyst, Manager, Auditor, Contractor 등)에 따라 서로 다른 액세스 수준이 필요할 수 있습니다. AgentCore Gateway의 Fine-Grained Access Control(FGAC)은 두 가지 주요 지점, 즉 대상에 도달하기 전(Request Interceptor)과 호출 에이전트에 결과를 반환하기 전(Response Interceptor)에 요청을 처리하는 custom Lambda 함수인 Gateway Interceptor를 통해 이 문제를 해결합니다.

![작동 방식](images/fgac.png)

### 도구 호출을 위한 Fine-Grained Access Control 구현
Gateway interceptor는 JWT scope를 활용해 사용자 권한을 검증하고, 도구 실행 전에 권한 부여를 확인하며, 전체 대상 액세스와 도구별 권한을 모두 지원하여 도구 호출을 제어합니다. 권한이 없는 액세스를 시도하면 Lambda가 요청이 대상에 도달하기 전에 차단하고 구조화된 MCP 오류를 반환합니다. 이를 통해 모든 도구 상호 작용에서 안전한 액세스 관리를 보장합니다.

### 동적 도구 필터링
Gateway interceptor는 도구 탐색 및 필터링 액세스를 List Tools와 Semantic Search라는 두 가지 주요 방법으로 관리합니다. tools/list 작업을 처리할 때 response interceptor는 사용자 JWT scope를 기준으로 사용 가능한 도구를 필터링하여 요청 에이전트에 권한이 있는 도구만 반환되도록 합니다. 마찬가지로 semantic search 작업에서는 response interceptor가 검색 결과를 에이전트에 반환하기 전에 처리하고, 권한이 없는 도구를 제거하며 목록 작업과 동일한 권한 로직을 적용합니다. 이 방식은 cache 없이 동적으로 권한을 업데이트하고 모든 탐색 방법에서 일관된 액세스 제어를 보장합니다.

이 포괄적인 액세스 제어 방식은 사용자 역할과 권한을 기반으로 한 안전한 도구 액세스, 권한 상태 cache가 필요 없는 동적 필터링, 모든 도구 탐색 방법에서 일관된 권한 부여, 기존 인증 시스템과의 간소화된 통합, 조기 요청 검증을 통한 보안 위험 감소 등의 주요 이점을 제공합니다. 이 구현은 안전하고 확장 가능한 엔터프라이즈 환경을 유지하면서 사용자가 자신의 역할에 적합한 도구만 탐색하고 액세스하도록 보장합니다.

### 실습 세부 정보


| 정보                 | 세부 정보                                                                       |
|:---------------------|:-----------------------------------------------------------------------         |
| 실습 유형            | 대화형                                                                          |
| AgentCore 구성 요소  | AgentCore Gateway, AgentCore Identity, AgentCore Runtime, Gateway Interceptors  |
| 에이전트 프레임워크  | Strands Agents                                                                  |
| Gateway Target 유형  | MCP Server                                                                      |
| Inbound Auth IdP     | Amazon Cognito, 다른 IdP도 사용 가능                                            |
| Outbound Auth        | Amazon Cognito, 다른 방식도 사용 가능                                           |
| 실습 구성 요소       | AgentCore Gateway Interceptor를 통한 Fine-Grained Access Control                |
| 실습 분야            | 산업 공통                                                                       |
| 예제 난이도          | 초급-중급                                                                       |
| 사용 SDK             | boto3                                                                           |

## 실습의 주요 기능

* 주요 MCP 작업에 custom scope를 사용하는 AgentCore Gateway Interceptor 기반 Fine-Grained Access Control

## 실습 개요

이 실습에서는 다음 기능을 다룹니다.

- [custom scope 및 AgentCore Gateway Interceptor를 사용한 Fine-Grained Access Control](01-fine-grained-access-control-using-custom-scopes.ipynb)
