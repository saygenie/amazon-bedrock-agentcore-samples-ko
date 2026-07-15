# Amazon Bedrock AgentCore Gateway Interceptor를 사용한 SQL Injection 공격 방지

> [!CAUTION]
> 이 리포지토리에서 제공하는 예제는 실험 및 교육 목적으로만 사용됩니다. 개념과 기법을 보여주지만 프로덕션 환경에서 직접 사용하도록 설계되지 않았습니다. [prompt injection](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-injection.html)을 방지하도록 Amazon Bedrock Guardrails를 반드시 적용하세요.

## 개요

최신 AI 에이전트 시스템은 데이터를 조회, 업데이트 또는 분석하기 위해 데이터베이스와 상호 작용하는 경우가 많습니다. 에이전트가 동적으로 쿼리를 생성하거나 데이터베이스 작업에 영향을 주는 사용자 입력을 수락하면 SQL injection 취약성이 중요한 보안 문제가 됩니다. 에이전트가 SQL 문을 동적으로 구성할 수 있고, prompt 조작이 도구 인수에 영향을 줄 수 있으며, 도구 계약에서 기존 입력 검증을 우회하는 유연한 형식 또는 자유 형식 입력을 허용할 수 있으므로 AI 시스템에서는 기존 SQL injection 위험이 더 커집니다.

Amazon Bedrock AgentCore Gateway는 도구 인수가 백엔드 데이터베이스 도구에 도달하기 전에 분석하고 검증하는 AWS Lambda 함수인 REQUEST interceptor를 통해 이 문제를 해결합니다. 이를 통해 실행 경계에서 결정론적인 도구 수준 제어를 적용하여 데이터베이스 쿼리가 실행되기 전에 악의적인 SQL injection 시도를 차단합니다.

![SQL Injection 방지 아키텍처](images/sql-injection-prevention.png)

### 도구 수준 SQL Injection 보호

Gateway interceptor는 데이터베이스 실행 전에 도구 인수를 분석하고, pattern matching을 통해 일반적인 SQL injection pattern을 탐지하며, fail-closed 동작으로 악의적인 요청을 차단하여 도구 수준 보호를 제공합니다. SQL injection이 탐지되면 AWS Lambda 함수는 요청이 데이터베이스 도구에 도달하기 전에 차단하고 공격 세부 정보를 노출하지 않는 일반적인 보안 경고를 반환합니다. 이를 통해 모델의 판단에 의존하지 않고 도구 경계에서 결정론적인 제어를 보장합니다.

### 에이전트 수준과 도구 수준 보호 비교

Amazon Bedrock Guardrails는 에이전트 자체에 대한 prompt injection 공격을 방지합니다. 하지만 에이전트가 도구를 호출하기로 결정한 시점에는 prompt가 이미 에이전트 계층을 통과한 상태입니다. Gateway REQUEST interceptor는 실제 도구 인수(query parameter)가 데이터베이스에 도달하기 전에 분석하여 2차 방어선을 제공합니다. 이러한 분리를 통해 에이전트가 조작되어 데이터베이스 도구를 호출하더라도 Gateway 계층에서 도구 인수를 독립적으로 검증합니다.

이 포괄적인 데이터베이스 보안 방식은 결정론적인 도구 수준 제어, AI 에이전트 시스템을 위한 심층 방어, 외부 API 호출이 필요 없는 빠른 pattern 기반 탐지, 모든 데이터베이스 도구에 걸친 중앙 집중식 보안 정책, 보안 분석을 위한 상세한 감사 로깅 등의 주요 이점을 제공합니다. 이 구현은 안전하고 확장 가능한 엔터프라이즈 환경을 유지하면서 데이터베이스 실행 전에 SQL injection 시도를 차단합니다.

### 실습 세부 정보

## 실습 세부 정보

| 정보                     | 세부 정보                                                                    |
|:-------------------------|:-----------------------------------------------------------------------------|
| 실습 유형                | 대화형                                                                       |
| AgentCore 구성 요소      | Amazon Bedrock AgentCore Gateway, Gateway Interceptors                      |
| Gateway Target 유형      | MCP Server(Lambda 기반 데이터베이스 도구)                                   |
| Interceptor types        | AWS Lambda (REQUEST)                                                        |
| Inbound Auth IdP         | Amazon Cognito (CUSTOM_JWT authorizer)                                      |
| 보안 패턴                | pattern matching을 사용한 SQL injection 탐지                                |
| 실습 구성 요소           | Amazon Bedrock AgentCore Gateway, AWS Lambda Interceptor, Amazon Cognito, MCP tools |
| 실습 분야                | 산업 공통(데이터베이스에 액세스하는 모든 AI 에이전트에 적용 가능)           |
| 예제 난이도              | 중급                                                                         |
| 사용 SDK                 | boto3                                                                        |

## 실습의 주요 기능

* 데모 목적으로 pattern matching을 사용하는 Amazon Bedrock AgentCore Gateway REQUEST interceptor 기반 SQL injection 방지

> **참고:** 이 구현은 데모를 위해 내장 pattern matching을 사용합니다. AWS Lambda interceptor는 모든 서드 파티 보안 도구, 외부 API 또는 AWS 서비스(예: Amazon Bedrock Guardrails, AWS WAF, threat intelligence feed, ML 기반 탐지)와 통합할 수 있습니다. 프로덕션 시스템에서는 parameterized query 및 구조화된 query template을 사용하여 raw SQL을 완전히 제거해야 합니다.

## 실습 개요

이 실습에서는 다음 기능을 다룹니다.

- [Gateway Interceptor를 사용한 SQL Injection 방지](01-prevent-sql-injection-with-interceptor.ipynb)
