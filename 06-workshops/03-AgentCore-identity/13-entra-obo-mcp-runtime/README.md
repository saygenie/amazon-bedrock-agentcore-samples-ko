# AgentCore Runtime의 MCP 도구를 위한 Entra ID On-Behalf-Of

## 소개

Amazon Bedrock AgentCore Runtime에서 실행되는 Strands 에이전트는 별도의 AgentCore Runtime으로 배포된 MCP 서버를 통해 로그인한 사용자를 대신하여 Microsoft Graph를 호출합니다. 에이전트는 Microsoft Entra ID On-Behalf-Of(OBO) 흐름을 사용하여 인바운드 사용자 JWT를 Graph scope의 위임 토큰으로 교환하고, 사용자 지정 요청 헤더로 해당 토큰을 MCP 서버에 전달합니다. RFC 8693에 따라 위임 토큰에는 `sub=user, act=agent`가 포함되므로 Graph 감사 로그에는 "agent acting on behalf of user"로 기록됩니다. 사용자 JWT는 에이전트와 MCP 사이의 경계를 절대 넘지 않으며, LLM은 어떤 토큰도 볼 수 없습니다.

이 샘플에서는 AgentCore Runtime에 호스팅된 MCP를 사용하는 OBO 방식을 다룹니다. 에이전트 측 코드 없이 AgentCore Gateway 내부에서 OBO 교환을 수행하는 Gateway 방식은 `06-workshops/02-AgentCore-gateway/18-Outbound_Auth_OBO_Microsoft/`에서 다룹니다.

## 아키텍처

![아키텍처](./images/architecture.png)

## 샘플에서 보여 주는 내용

- Microsoft Entra ID JWT(`customJWTAuthorizer`)를 사용하는 AgentCore Runtime의 인바운드 인증
- 두 번째 Entra 앱 등록에 대한 client-credentials 토큰을 사용하여 에이전트에서 MCP 서버로 수행하는 아웃바운드 M2M 인증
- AgentCore Identity에서 `oauth2Flow=ON_BEHALF_OF_TOKEN_EXCHANGE`와 함께 `GetResourceOauth2Token`을 사용하여 에이전트에서 Microsoft Graph로 수행하는 아웃바운드 OBO 인증
- Graph scope의 위임 토큰을 `X-Amzn-Bedrock-AgentCore-Runtime-Custom-Graph-Token` 요청 헤더로 MCP 서버에 전달. 요청 전달 과정에서 사용자 지정 헤더가 유지되도록 MCP Runtime에 `requestHeaderConfiguration.requestHeaderAllowlist` 필요

## 튜토리얼 세부 정보

| 정보               | 세부 정보                                                         |
|:------------------|:------------------------------------------------------------------|
| 튜토리얼 유형      | Jupyter 노트북                                                    |
| 에이전트 프레임워크 | Strands Agents                                                    |
| LLM 모델           | Anthropic Claude Sonnet 4.5                                       |
| 인바운드 인증      | Microsoft Entra ID(`CUSTOM_JWT`)                                  |
| 아웃바운드 인증    | Microsoft Graph에 대한 OBO(RFC 8693) + MCP Runtime에 대한 M2M     |
| AgentCore 구성     | Runtime 2개(HTTP 에이전트 1개, MCP 서버 1개)                      |
| CLI 도구           | `bedrock-agentcore-starter-toolkit`(Python)                       |
| 난이도             | 고급                                                             |

## 사전 요구 사항

- Bedrock AgentCore 액세스 권한이 있는 AWS 계정. 노트북의 기본 리전은 `us-west-2`입니다.
- 애플리케이션 등록 및 관리자 동의 부여 권한이 있는 Microsoft Entra ID 테넌트
- Jupyter 스택(`ipykernel`, `jupyter`)을 갖춘 Python 3.11 이상
- 노트북 커널에서 사용할 수 있는 AWS 자격 증명(예: Jupyter를 시작하기 전에 내보낸 `AWS_PROFILE`)
- Amazon Bedrock의 Claude Sonnet 4.5 모델 액세스 권한

노트북의 사전 요구 사항 섹션에서는 두 Entra 앱(에이전트 앱과 MCP 서버 앱) 등록, scope 노출, 앱 역할 선언 및 관리자 동의 부여 과정을 안내합니다. 코드 셀을 실행하기 전에 해당 섹션을 완료하세요.

## 사용 방법

1. 가상 환경을 생성하고 노트북 호스트 종속성을 설치합니다.

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. 커널을 등록합니다.

   ```bash
   python -m ipykernel install --user --name=agentcore-entra-obo \
       --display-name="Python (agentcore-entra-obo)"
   ```

3. `runtime_with_entra_id_obo_and_mcp.ipynb`를 열고 위에서 등록한 커널을 선택한 다음, 셀을 위에서 아래 순서로 실행합니다.

## 샘플 프롬프트

두 Runtime을 모두 배포하고 유효한 사용자 JWT로 에이전트를 호출하면, 에이전트가 Microsoft Graph `/me`에 대해 `get_my_profile` MCP 도구를 호출하고 반환된 JSON을 바탕으로 응답합니다. Graph 토큰의 scope는 `User.Read`이므로 로그인한 사용자의 프로필만 읽을 수 있습니다.

- "What is my email address?"
- "What is my display name?"
- "What is my job title?"
- "Give me a summary of my Microsoft 365 profile."

## 파일

- `runtime_with_entra_id_obo_and_mcp.ipynb`: 전체 실습 가이드
- `requirements.txt`: 로컬에서 노트북을 실행하는 데 필요한 종속성
- `mcp/requirements.txt`, `agent/requirements.txt`: 두 Runtime 컨테이너 빌드의 종속성. 노트북은 starter toolkit에서 생성한 `Dockerfile`과 `.bedrock_agentcore.yaml`이 충돌하지 않도록 각 Runtime을 자체 하위 디렉터리에서 배포합니다.
- `images/`: 아키텍처 다이어그램(PNG)

## 정리

노트북의 Cleanup 섹션에서는 두 Runtime과 실습 과정에서 생성한 자격 증명 공급자를 삭제합니다. 노트북은 Entra 앱 등록을 삭제하지 않으므로 더 이상 필요하지 않다면 Entra 관리 센터에서 삭제하세요.

## 관련 자료

- [AgentCore OBO 토큰 교환](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/on-behalf-of-token-exchange.html)
- [AgentCore Runtime에 사용자 지정 헤더 전달](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-header-allowlist.html)
- [Microsoft Entra ID On-Behalf-Of 흐름](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-on-behalf-of-flow)
- [RFC 8693: OAuth 2.0 토큰 교환](https://www.rfc-editor.org/rfc/rfc8693)
