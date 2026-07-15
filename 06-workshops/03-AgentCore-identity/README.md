# Amazon Bedrock AgentCore Identity

## 개요

Amazon Bedrock AgentCore Identity는 AI 에이전트와 자동화된 워크로드를 위해 특별히 설계된 종합적인 자격 증명 및 ID 관리 서비스입니다. 엄격한 보안 제어와 감사 추적을 유지하면서 사용자가 에이전트를 호출하고, 에이전트가 사용자를 대신해 외부 리소스와 서비스에 액세스할 수 있도록 안전한 인증, 권한 부여 및 자격 증명 관리 기능을 제공합니다.

AgentCore Identity는 보안이나 사용자 경험을 저해하지 않으면서 에이전트가 여러 서비스의 사용자별 데이터에 안전하게 액세스하도록 지원해야 하는 AI 에이전트 배포의 근본적인 과제를 해결합니다. 이 서비스는 **가장이 아닌 위임** 원칙에 따라 작동하며, 에이전트는 검증 가능한 사용자 컨텍스트를 포함한 상태로 에이전트 자신을 인증합니다.

## 주요 기능

- **인바운드 인증**: 에이전트나 도구를 호출하는 사용자 및 애플리케이션의 액세스 검증
- **아웃바운드 인증**: 에이전트가 사용자를 대신해 외부 서비스에 안전하게 액세스
- **OAuth 통합**: 2-legged 및 3-legged OAuth 흐름 지원
- **AWS IAM 통합**: AWS Identity and Access Management와 기본 통합
- **제로 트러스트 보안**: 요청의 출처나 이전 신뢰 관계와 관계없이 모든 요청 검증
- **크로스 플랫폼 지원**: AWS, 다른 클라우드 공급자 및 온프레미스 환경 전반에서 작동

## 인증 유형

AgentCore Identity는 두 가지 주요 인증 패턴을 지원합니다.

### 인바운드 인증
AgentCore Runtime이나 Gateway 대상에서 에이전트 또는 도구를 호출하는 사용자와 애플리케이션의 액세스를 검증합니다. 다음 방식을 지원합니다.
- **AWS IAM**: IAM 기반의 직접 액세스 제어
- **OAuth**: 최종 사용자에게 IAM 권한을 요구하지 않는 토큰 기반 인증

### 아웃바운드 인증
에이전트가 사용자를 대신해 AWS 서비스와 외부 리소스에 액세스할 수 있도록 합니다.
- **AWS 리소스**: AWS 서비스 액세스에 IAM 실행 역할 사용
- **외부 서비스**: OAuth 2-legged(client credentials) 및 3-legged(authorization code) 흐름 사용


![인증 기본 사항](images/auth_basics3.png)

## 작동 방식

AgentCore Identity는 여러 신뢰 도메인에 걸친 인증과 권한 부여를 조정하는 포괄적인 워크플로를 구현합니다.

1. **사용자 인증**: 사용자는 기존 Identity Provider(Cognito, Auth0 등)를 통해 인증합니다.
2. **에이전트 권한 부여**: 애플리케이션은 사용자 토큰으로 에이전트 액세스를 요청합니다.
3. **토큰 교환**: AgentCore Identity가 사용자 토큰을 검증하고 워크로드 액세스 토큰을 발급합니다.
4. **리소스 액세스**: 에이전트는 워크로드 토큰을 사용해 AWS 및 서드 파티 리소스에 액세스합니다.
5. **위임 및 감사**: 모든 작업에서 사용자 컨텍스트와 감사 추적을 유지합니다.

![작동 방식](images/how_it_works.png)

자세한 기술 정보는 [AgentCore Identity 작동 방식](02-how_it_works.md)을 참조하세요.

## 시작하기

1. **소개 읽기**: [시작하기](01-getting_started.md)에서 AgentCore Identity 개념을 살펴보세요.
2. **워크플로 이해하기**: [작동 방식](02-how_it_works.md)에서 기술 세부 정보를 확인하세요.
3. **예제 선택하기**: 인증 요구 사항에 맞는 튜토리얼 예제를 선택하세요.
   - 에이전트에 대한 사용자 인증: **인바운드 인증 예제**로 시작
   - 에이전트의 외부 서비스 액세스: **아웃바운드 인증 예제** 실습
   - 사용자 위임 액세스 패턴: **3-Legged OAuth** 또는 **GitHub 통합** 살펴보기

## 주요 이점

- **향상된 보안**: 세분화된 액세스 제어를 적용하는 제로 트러스트 인증
- **사용자 경험**: 반복적인 인증 요청 없이 원활한 액세스
- **감사 및 규정 준수**: 모든 에이전트 작업에 대한 완전한 감사 추적
- **프레임워크 독립성**: 모든 에이전트 프레임워크(Strands, LangGraph, CrewAI 등)와 호환
- **확장성**: 여러 Identity Provider를 지원하는 엔터프라이즈급 환경
- **표준 기반**: OAuth 2.0, OIDC 및 업계 보안 표준을 기반으로 구축

## 아키텍처 통합

AgentCore Identity는 다른 AgentCore 구성 요소와 원활하게 통합됩니다.

- **AgentCore Runtime**: 호스팅된 에이전트에 인증 제공
- **AgentCore Gateway**: 도구 및 외부 API에 대한 액세스 보호
- **AgentCore Memory**: 사용자별 메모리 저장소에 대한 안전한 액세스 유지
- **서드 파티 서비스**: 외부 API 및 서비스와 안전하게 통합

## 튜토리얼 예제

| # | 예제 | 유형 | 방식 | 설명 |
|---|---------|------|--------|-------------|
| 03 | **[인바운드 인증](03-Inbound%20Auth%20example)** | 인바운드 | 노트북 | Strands 에이전트 및 Bedrock 모델을 사용한 사용자 인증 |
| 04 | **[아웃바운드 인증](04-Outbound%20Auth%20example)** | 아웃바운드 | 노트북 | Strands 및 OpenAI를 사용한 에이전트의 외부 서비스 액세스 |
| 05 | **[Google 3LO](05-Outbound_Auth_3lo)** | 아웃바운드 | 노트북 | Cognito 및 Google 3-legged OAuth 흐름을 사용한 사용자 위임 액세스 |
| 06 | **[GitHub 3LO](06-Outbound_Auth_Github)** | 아웃바운드 | 노트북 | 3-legged OAuth 인증을 사용한 GitHub API 액세스 |
| 07 | **[ECS Fargate의 3LO](07-Outbound_Auth_3LO_ECS_Fargate)** | 아웃바운드 | 노트북 | ECS Fargate에 배포한 3-legged OAuth |
| 08 | **[IDP 예제](08-IDP-examples)** | 인바운드 + 아웃바운드 | 노트북 | Identity Provider 예제(EntraID, Okta) |
| 09 | **[자체 호스팅 에이전트 OAuth](09-Outbound_Auth_Self_Hosted)** | 아웃바운드 | 노트북 | 자체 호스팅 로컬 에이전트의 OAuth 토큰 관리 |
| 10 | **[Runtime 인바운드 + 아웃바운드 인증](10-runtime-inbound-outbound-auth)** | 인바운드 + 아웃바운드 | CLI | AgentCore Runtime의 Cognito JWT 및 AgentCore Identity를 통한 아웃바운드 API 키 |
| 11 | **[Gateway 인바운드 + 아웃바운드 인증](11-gateway-inbound-outbound-auth)** | 인바운드 + 아웃바운드 | CLI | AgentCore Gateway의 Cognito JWT 및 업스트림 MCP 서버에 대한 OAuth2 |
| 12 | **[M2M + 3LO 인증 흐름](12-m2m-3lo-runtime)** | 인바운드 + 아웃바운드 | CLI | M2M(client credentials) + GitHub/Google 3LO 아웃바운드 |

## 다음 단계

튜토리얼을 완료한 후 다음 작업을 진행할 수 있습니다.
- AgentCore Identity를 기존 ID 인프라와 통합
- 사용자 지정 OAuth 공급자 및 scope 구성
- 고급 보안 정책 및 액세스 제어 구현
- 프로덕션 수준의 에이전트 인증 워크플로 배포
- 여러 서비스와 플랫폼으로 안전한 에이전트 인프라 확장
