# MCP Server와 AgentCore Gateway 통합

## 개요
Amazon Bedrock AgentCore Gateway는 REST API 및 AWS Lambda 함수와 함께 MCP 서버를 native target으로 지원합니다. 따라서 서버별 클라이언트 코드를 작성하거나 팀별로 Gateway를 따로 운영할 필요 없이 하나의 통합 인터페이스를 통해 기존 MCP 서버 구현을 통합하고, 도구 관리, 인증, 라우팅, 프로토콜 업그레이드를 한 곳에서 중앙 집중화할 수 있습니다.

Gateway는 tool/prompt/resource 탐색, 보안 및 라우팅을 위한 중앙 관리 프레임워크입니다. 이를 통해 엔터프라이즈는 보안 및 운영 표준을 분산하지 않고 단일 엔드포인트 뒤에서 수십 개의 MCP 서버를 수백 개까지 확장할 수 있습니다.

![작동 방식](images/mcp-server-target.png)

### Gateway가 전달하는 MCP primitive
Gateway는 각 MCP server target에 세 가지 MCP primitive 유형을 모두 전달합니다.

- **Tools** - `tools/list`(대상의 `listingMode`에 따라 cache 또는 live) 및 `tools/call`(항상 live).
- **Prompts** - `prompts/list`(cache 또는 live) 및 `prompts/get`(항상 live). Prompt 이름에는 `{targetName}___{promptName}` prefix가 자동으로 추가됩니다(밑줄 3개, Tools와 동일한 규칙).
- **Resources** - `resources/list`, `resources/templates/list`(cache 또는 live) 및 `resources/read`(항상 live). Resource URI는 prefix 없이 **그대로** 반환됩니다. 대상 간 URI 충돌은 `resourcePriority`로 해결하며 값이 낮을수록 우선하고 기본값은 1000입니다.

> **Resource 보안 경고**(AWS 문서): Gateway는 Resource URI를 검증하거나 정제하지 않습니다. 악의적이거나 침해된 MCP server target은 내부 엔드포인트(SSRF) 또는 로컬 파일 시스템 경로(예: `file:///etc/passwd`)를 가리키는 URI를 반환할 수 있습니다. 신뢰할 수 없는 대상의 URI는 사용하기 전에 검증하고 정제하세요.

### 카탈로그를 동기화하는 세 가지 방법
MCP 서버의 tool, prompt 및 resource 정의는 시간이 지남에 따라 변경됩니다. AgentCore Gateway는 각 MCP server target이 실제로 노출하는 항목과 카탈로그를 동기화하기 위해 다음 세 가지 메커니즘을 제공합니다.

1. **명시적 동기화** - upstream MCP 서버가 변경된 후 필요할 때 `SynchronizeGatewayTargets`를 호출합니다.
2. **암시적 동기화** - `CreateGatewayTarget` 및 `UpdateGatewayTarget`은 작업의 일부로 항상 upstream 서버의 카탈로그를 다시 읽습니다.
3. **동적 목록 조회**(`listingMode='DYNAMIC'`) - Gateway는 모든 목록 요청(`tools/list`, `prompts/list`, `resources/list`, `resources/templates/list`)을 MCP 서버에 live로 전달하므로 동기화가 필요하지 않습니다.

(1)과 (2)는 **`listingMode='DEFAULT'` 대상에 대한 control plane 작업**입니다. DEFAULT 모드의 목록 호출에 응답하는 Gateway 카탈로그 *cache*를 채웁니다. `CreateGatewayTarget`은 최초로 cache를 채우고(생성 시 암시적 실행), `UpdateGatewayTarget`은 업데이트할 때마다 부수 효과로 다시 채우며, `SynchronizeGatewayTargets`는 그 사이에 필요할 때 cache를 다시 채웁니다. DYNAMIC 모드 대상은 이 cache를 완전히 건너뜁니다. Gateway가 각 목록 호출을 서버에 직접 proxy하므로 대상에 `Synchronize`/`Update` 호출을 실행할 필요가 없습니다.

> **DYNAMIC 호환성 주의 사항:** `listingMode='DYNAMIC'`은 `searchType='SEMANTIC'`인 Gateway에서 거부되며 outbound three-legged OAuth(3LO)와 호환되지 않습니다. 따라서 Notebook 02는 동적 목록 조회 데모를 위해 `searchType='NONE'`인 자체 Gateway를 생성합니다.

#### 명시적 동기화(control plane → cache 채우기)
![명시적 동기화](images/mcp-server-target-explicit-sync.png)

#### 암시적 동기화(Create/UpdateGatewayTarget 중)
![암시적 동기화](images/mcp-server-target-implicit-sync.png)

### 실습 세부 정보

| 정보                 | 세부 정보                                                                                |
|:---------------------|:-----------------------------------------------------------------------------------------|
| 실습 유형            | 대화형                                                                                   |
| AgentCore 구성 요소  | AgentCore Gateway, AgentCore Identity, AgentCore Runtime                                 |
| 에이전트 프레임워크  | Strands Agents                                                                           |
| Gateway Target 유형  | MCP server                                                                               |
| MCP primitives       | Tools, Prompts, Resources(static 및 templated)                                           |
| Inbound Auth IdP     | Amazon Cognito, 다른 IdP도 사용 가능                                                     |
| Outbound Auth        | Amazon Cognito, 다른 방식도 사용 가능                                                    |
| LLM 모델             | Anthropic Claude Haiku 4.5                                                               |
| 실습 구성 요소       | Gateway를 통한 tools/prompts/resources, `resourcePriority`, 명시적/암시적/동적 동기화    |
| 실습 분야            | 산업 공통                                                                                |
| 예제 난이도          | 쉬움                                                                                     |
| 사용 SDK             | boto3                                                                                    |

## 실습 아키텍처

### 실습의 주요 기능

* MCP Server와 AgentCore Gateway 통합
* Gateway를 통해 **tools**, **prompts**, **resources**(static + templated) 사용
* resource URI 충돌 해결을 위한 `resourcePriority`와 함께 여러 MCP server target을 하나의 Gateway에 결합(퍼블릭 **Exa MCP server**를 대상으로 데모)
* **명시적** 동기화(`SynchronizeGatewayTargets`), **암시적** 동기화(`UpdateGatewayTarget`)로 Gateway의 tool/prompt/resource 카탈로그를 새로 고치거나 **`listingMode='DYNAMIC'`**으로 cache를 완전히 건너뜀

## 리포지토리 구성

- `01-mcp-server-target.ipynb` - 기본 워크숍입니다. Gateway를 생성하고 네 가지 MCP primitive 유형을 모두 포함하는 FastMCP 서버를 배포하여 대상으로 연결한 다음 tools, prompts, resources와 퍼블릭 Exa MCP server(`https://mcp.exa.ai/mcp`)를 대상으로 한 `resourcePriority` shadow 데모를 진행합니다.
- `02-mcp-target-synchronization.ipynb` - 명시적 `SynchronizeGatewayTargets`, 암시적 `UpdateGatewayTarget`, `listingMode='DYNAMIC'`의 세 가지 카탈로그 동기화 메커니즘을 모두 보여주는 독립 후속 워크숍입니다. DEFAULT 및 DYNAMIC 대상 전반의 대상별 cursor pagination 동작도 다룹니다.
- `gateway_mcp_client.py` - 두 노트북에서 사용하는 간단한 `GatewayMCPClient` helper입니다. bearer-token auth, `MCP-Protocol-Version` header, JSON-RPC envelope 및 대상별 pagination(`list_all_tools()`, `list_all_prompts()`, `list_all_resources()`, `list_all_resource_templates()`이 끝날 때까지 `nextCursor`를 따라감)을 래핑합니다.
- `runtime_deploy.py` - AgentCore Runtime 구성, 시작, URL 파생 boilerplate를 한 번의 호출로 래핑하고 `DeployedRuntime` dataclass를 반환하는 `deploy_mcp_server(...)` helper입니다.

## 실습 개요

이 실습에서는 다음 기능을 다룹니다.

- [MCP Server와 AgentCore Gateway 통합 - tools, prompts, resources, `resourcePriority`](01-mcp-server-target.ipynb)
- [Gateway 카탈로그 새로 고침: 명시적 동기화, 암시적 동기화 및 동적 목록 조회](02-mcp-target-synchronization.ipynb)
