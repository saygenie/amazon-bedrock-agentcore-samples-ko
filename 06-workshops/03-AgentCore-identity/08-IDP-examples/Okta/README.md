# Okta와 Amazon Bedrock AgentCore 통합

이 리포지토리에는 다양한 인증 및 권한 부여 시나리오에서 Okta를 Amazon Bedrock AgentCore와 통합하는 방법을 보여 주는 종합 노트북이 포함되어 있습니다.

## Okta란?

Okta는 기업에 안전한 ID 솔루션을 제공하는 클라우드 기반 ID 및 액세스 관리 서비스로, 애플리케이션과 서비스 전반에서 원활한 인증과 권한 부여를 지원합니다.

### 주요 기능
- **Single Sign-On(SSO)** - 한 번의 사용자 인증으로 여러 애플리케이션에 액세스
- **Multi-Factor Authentication(MFA)** - 추가 검증 방식으로 보안 강화
- **적응형 인증** - 사용자 행동과 컨텍스트를 기반으로 한 위험 기반 인증 정책
- **Universal Directory** - 중앙 집중식 사용자 관리 및 프로필 동기화
- **API 액세스 관리** - API 보안을 위한 OAuth 2.0 및 OpenID Connect 지원

### AgentCore와 통합

Okta를 AgentCore Identity의 Identity Provider로 사용하여 다음 작업을 수행할 수 있습니다.
- 사용자가 에이전트를 호출하기 전에 인증(인바운드 인증)
- 에이전트가 사용자를 대신해 보호된 리소스에 액세스하도록 권한 부여(아웃바운드 인증)
- JWT 기반 권한 부여로 AgentCore Gateway 엔드포인트 보호

## 예제 노트북 개요

이 학습 과정에는 서로 다른 통합 패턴을 보여 주는 실습 노트북이 포함되어 있습니다.

### 1. Step by Step Okta for Inbound Auth.ipynb

**목적**: 인증된 사용자만 에이전트를 호출할 수 있도록 AgentCore Runtime 에이전트 엔드포인트를 보호하는 **인바운드 인증**에 Okta를 사용하는 방법을 보여 줍니다.

**학습 내용**:
- Okta 테넌트 및 애플리케이션 구성 설정
- AgentCore OAuth2 자격 증명 공급자 생성
- 사용자 인증 및 위임을 위한 OAuth 2.0 흐름 구현
- Okta와 통합된 에이전트를 구축하여 AgentCore Runtime에 배포
- 사용자 세션 관리

**주요 통합 패턴**:
- AgentCore Runtime 에이전트 엔드포인트에 액세스하기 전에 Okta로 사용자 인증
- 각 요청에서 bearer 토큰으로 사용자 ID 검증
- 인증 계층으로 에이전트 보호

## 지원 및 문서

- [Okta 개발자 문서](https://developer.okta.com/)
- [Amazon Bedrock AgentCore 문서](https://docs.aws.amazon.com/bedrock-agentcore/)
- [OAuth 2.0 및 OpenID Connect](https://developer.okta.com/docs/concepts/oauth-openid/)

## 참고

Okta는 AWS 서비스가 아닙니다. Okta 사용과 관련된 비용 및 라이선스는 Okta 문서를 참조하세요.
