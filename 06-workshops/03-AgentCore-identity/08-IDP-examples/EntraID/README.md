# Microsoft Entra ID와 Amazon Bedrock AgentCore 통합

이 리포지토리에는 다양한 인증 및 권한 부여 시나리오에서 Microsoft Entra ID(이전 Azure Active Directory)를 Amazon Bedrock AgentCore와 통합하는 방법을 보여 주는 세 개의 종합 노트북이 포함되어 있습니다.

## Microsoft Entra ID란?

Microsoft Entra ID는 Microsoft 365, Azure 및 기타 SaaS 애플리케이션의 중앙 Identity Provider 역할을 하는 Microsoft의 클라우드 기반 ID 및 액세스 관리 서비스입니다.

### 주요 기능
- **Single Sign-On(SSO)** - 한 번의 사용자 인증으로 여러 애플리케이션에 액세스
- **Multi-Factor Authentication(MFA)** - 추가 검증 방식으로 보안 강화
- **조건부 액세스** - 사용자, 디바이스, 위치 및 위험을 기반으로 한 정책 기반 액세스 제어
- **애플리케이션 통합** - OAuth 2.0, OpenID Connect 및 SAML 같은 최신 인증 프로토콜 지원

### AgentCore와 통합


Microsoft Entra ID를 AgentCore Identity의 Identity Provider로 사용하여 다음 작업을 수행할 수 있습니다.
- 사용자가 에이전트를 호출하기 전에 인증(인바운드 인증)
- 에이전트가 사용자를 대신해 보호된 리소스에 액세스하도록 권한 부여(아웃바운드 인증)
- JWT 기반 권한 부여로 AgentCore Gateway 엔드포인트 보호

## 예제 노트북 개요

이 학습 과정에는 서로 다른 통합 패턴을 보여 주는 세 개의 실습 노트북이 포함되어 있습니다.

### 1. Step By Step MS EntraID and 3LO Outbound for Tools.ipynb

**목적**: AgentCore Runtime에 배포된 에이전트가 인증된 사용자를 대신해 외부 리소스(Microsoft OneNote)에 액세스하는 **아웃바운드 인증**에 Entra ID를 사용하는 방법을 보여 줍니다.

**학습 내용**:
- Entra ID 테넌트 및 애플리케이션 등록 설정
- AgentCore OAuth2 자격 증명 공급자 생성
- 사용자 위임을 위한 3-legged OAuth(3LO) 흐름 구현
- OneNote 노트북을 생성하고 관리하는 에이전트를 구축하여 AgentCore Runtime에 배포

**주요 통합 패턴**:
- 사용자가 Entra ID로 인증
- AgentCore Runtime이 OneNote API 액세스를 위한 위임 권한 수신
- AgentCore Runtime 에이전트 도구가 사용자를 대신해 작업 수행


**생성되는 도구**:
- `create_notebook` - 새 OneNote 노트북 생성
- `create_notebook_section` - 노트북에 섹션 추가
- `add_content_to_notebook_section` - 콘텐츠가 포함된 페이지 생성

### 2. Step by Step Entra ID for Inbound Auth.ipynb

**목적**: 인증된 사용자만 에이전트를 호출할 수 있도록 AgentCore Runtime 에이전트 엔드포인트를 보호하는 **인바운드 인증**에 Entra ID를 사용하는 방법을 보여 줍니다.

**학습 내용**:
- Entra ID로 사용자 지정 JWT 권한 부여자 구성
- 디바이스 코드 흐름에 MSAL(Microsoft Authentication Library) 사용
- bearer 토큰으로 AgentCore Runtime 엔드포인트 보호
- 인증된 사용자와의 세션 기반 대화 관리

**주요 통합 패턴**:
- AgentCore Runtime 에이전트 엔드포인트에 액세스하기 전에 Entra ID로 사용자 인증
- 각 요청에서 bearer 토큰으로 사용자 ID 검증
- 인증 계층으로 에이전트 보호


### 3. Step by Step Entra ID with AgentCore Gateway.ipynb

**목적**: client credentials 흐름을 사용하는 machine-to-machine(M2M) 인증으로 **AgentCore Gateway** 엔드포인트를 보호하는 데 Entra ID를 사용하는 방법을 보여 줍니다.

**학습 내용**:
- API 보호를 위한 Entra ID 앱 역할 설정
- 사용자 지정 JWT 권한 부여로 AgentCore Gateway 구성
- Lambda 함수를 MCP(Model Context Protocol) 도구로 생성
- 서비스 간 인증에 client credentials 흐름 사용

**주요 통합 패턴**:
- 애플리케이션이 client credentials를 사용해 인증(사용자 상호 작용 없음)
- Gateway가 Entra ID를 기준으로 JWT 토큰 검증
- Lambda 함수를 표준화된 MCP 도구로 노출



## 지원 및 문서

- [Microsoft Entra ID 문서](https://learn.microsoft.com/en-us/entra/)
- [Amazon Bedrock AgentCore 문서](https://docs.aws.amazon.com/bedrock-agentcore/)
- [OAuth 2.0 명세](https://oauth.net/2/)

## 참고

Microsoft Entra ID는 AWS 서비스가 아닙니다. Entra ID 사용과 관련된 비용 및 라이선스는 Microsoft Entra ID 문서를 참조하세요.
