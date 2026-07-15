<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Amazon Bedrock AgentCore Gateway - Authorization Code Flow 예제

이 리포지토리에는 OAuth 2.0 Authorization Code Grant 흐름을 사용해 원격 MCP 서버를 [Amazon Bedrock AgentCore Gateway](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/gateway.html)에 연결하는 방법을 단계별로 보여주는 Jupyter 노트북이 포함되어 있습니다.

## 사용 가능한 예제

| MCP Server | 노트북 |
|---|---|
| [GitHub](https://github.com/github/github-mcp-server) | [github-mcp-server.ipynb](github-mcp-server.ipynb) |
| [Atlassian(Jira/Confluence)](https://github.com/atlassian/atlassian-mcp-server) | 제공 예정 |
| [Salesforce](https://help.salesforce.com/s/articleView?id=platform.hosted_mcp_servers.htm&type=5) | 제공 예정 |
| [Snowflake](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp) | 제공 예정 |


## 개념

### Authorization Code Flow

OAuth 2.0 Authorization Code Grant("three-legged OAuth"라고도 함)를 사용하면 애플리케이션이 사용자의 자격 증명을 직접 확인하지 않고도 사용자를 대신해 리소스에 액세스할 수 있습니다. 흐름은 다음과 같습니다.

1. 애플리케이션이 사용자를 authorization server의 로그인 페이지로 redirect합니다.
2. 사용자가 인증하고 동의합니다.
3. authorization server가 authorization code와 함께 다시 redirect합니다.
4. 애플리케이션이 code를 access token으로 교환합니다.
5. access token을 사용해 보호된 API를 호출합니다.

AgentCore Gateway에서는 이 흐름을 사용하여 사용자 수준의 권한 부여가 필요한 MCP 서버 호출용 OAuth 토큰을 가져옵니다(예: 사용자의 GitHub 리포지토리, Jira issue 또는 Salesforce record 액세스).

### 대상을 생성하는 두 가지 방법

각 노트북에서는 AgentCore Gateway에 MCP server target을 생성하는 두 가지 방법을 보여줍니다.

**방법 1 - Implicit Sync:** 관리자가 대상 생성 중 authorization code flow를 완료합니다. AgentCore Gateway는 생성된 토큰을 사용해 MCP 서버에 연결하고 도구를 탐색하여 도구 정의를 cache합니다. 설정 중 사람의 상호 작용이 필요합니다.

**방법 2 - Schema Upfront:** 관리자가 대상을 생성할 때 JSON 파일의 도구 스키마를 직접 제공합니다. 생성 시 OAuth 흐름이 필요하지 않습니다. 사람의 상호 작용이 불가능한 Infrastructure-as-Code pipeline에 적합합니다.

두 방법 모두 Gateway 사용자는 MCP 서버에 인증하지 않고 `tools/list`를 호출할 수 있으며 cache된 도구가 반환됩니다. authorization code flow는 사용자가 `tools/call`을 호출할 때만 시작됩니다.

### URL Session Binding

[URL Session Binding](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/oauth2-authorization-url-session-binding.html)은 OAuth 흐름을 시작한 사용자와 동의를 완료한 사용자가 동일한지 확인하는 보안 메커니즘입니다. AgentCore Identity는 authorization URL을 생성할 때 session URI도 반환합니다. 사용자가 동의를 완료하면 애플리케이션이 session URI 및 사용자의 identity와 함께 `CompleteResourceTokenAuth`를 호출합니다. AgentCore Identity는 access token을 발급하기 전에 일치 여부를 검증합니다.

이를 통해 사용자가 실수로 authorization URL을 공유하고 다른 사람이 대신 동의를 완료하는 상황을 방지합니다. authorization URL과 session URI는 10분 후에 만료됩니다.

### Credential Providers

AgentCore Gateway는 [credential provider](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/identity-credential-providers.html)를 사용해 MCP server target의 OAuth 토큰을 관리합니다. 각 노트북은 특정 MCP 서버의 OAuth 설정에 맞게 구성된 credential provider를 생성합니다.

- **GitHub** - 내장 `GithubOauth2` vendor 사용
- **Atlassian** - 수동 authorization server metadata와 함께 `CustomOauth2` 사용
- **Salesforce** - OpenID Connect discovery URL과 함께 `CustomOauth2` 사용

### Inbound 및 Outbound Authentication 비교

- **Inbound auth**는 AgentCore Gateway를 호출할 수 있는 주체를 제어합니다. 이 노트북은 machine-to-machine(M2M) client credentials flow와 함께 Amazon Cognito를 사용합니다.
- **Outbound auth**는 Gateway가 MCP server target에 인증하는 방식을 제어합니다. 각 노트북에서 보여주는 authorization code flow입니다.

## 사전 요구 사항

- Amazon Bedrock AgentCore에 액세스할 수 있는 AWS 계정
- Python 3.11+
- 대상 MCP server provider(GitHub, Atlassian 또는 Salesforce)에 등록된 OAuth app
- 적절한 자격 증명이 구성된 AWS CLI

## 시작하기

1. 종속성을 설치합니다.
   ```bash
   pip install -r requirements.txt
   ```

2. 노트북을 열고 단계별로 진행합니다.
   ```bash
   jupyter notebook github-mcp-server.ipynb
   ```

3. 각 노트북은 OAuth app 자격 증명 입력을 요청하고 전체 설정, 호출 및 정리 과정을 안내합니다.

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](LICENSE.txt) 파일을 참조하세요.
