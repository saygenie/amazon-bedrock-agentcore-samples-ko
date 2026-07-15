# 02 — AgentCore Gateway 통합

AgentCore Harness 에이전트를 **AgentCore Gateway**에 연결하여 중앙 집중식 인증, 라우팅, 관찰성을 제공하는 관리형 프록시를 통해 외부 MCP 도구 서버에 접근할 수 있도록 합니다.

## AgentCore Gateway란?

AgentCore Gateway는 에이전트와 외부 도구 서버 사이에 위치하는 관리형 서비스입니다. 에이전트는 MCP 엔드포인트를 직접 호출하는 대신 AgentCore Gateway를 호출하며, AgentCore Gateway는 다음 작업을 수행합니다.

- **인증**을 중앙에서 처리(IAM, OAuth, API 키)
- 트래픽을 올바른 대상으로 전달하는 **라우팅 규칙** 적용
- **관찰성** 데이터 생성(모든 도구 호출을 CloudWatch에서 추적)
- 에이전트 구성을 변경하지 않고 **도구 백엔드 교체**

## 폴더 구성

| 파일 | 유형 | 설명 |
|---|---|---|
| [`02_agentcore_gateway_integration.py`](02_agentcore_gateway_integration.py) | CLI 스크립트 | 전체 수명 주기 데모입니다. IAM 역할, AgentCore Gateway, MCP 대상, 라우팅 규칙, AgentCore Gateway에 연결된 AgentCore Harness를 생성하고, AgentCore Gateway를 통해 도구를 검색하고 호출하는 에이전트를 호출한 후 리소스를 정리합니다. |

## 엔드 투 엔드 흐름(스크립트 기준)

```
1. Create IAM execution role (reuses helper/iam.py)
2. Create Gateway           → IAM auth + MCP protocol
3. Add MCP target           → remote MCP server endpoint (default: Exa)
4. Create routing rule      → directs traffic to the target
5. Create harness           → wired to the Gateway's ARN
6. invoke_harness           → agent discovers tools via Gateway and calls them
7. Cleanup                  → delete harness, target, Gateway, IAM role
```

## 실행 방법

### 기본 스크립트

```bash
# 기본값 - Exa MCP search를 대상으로 사용
python 02_agentcore_gateway_integration.py

# 사용자 지정 MCP endpoint
python 02_agentcore_gateway_integration.py \
    --mcp-endpoint https://your-mcp-server.example.com/mcp \
    --target-name my-tools

# 데모 후 리소스 유지
python 02_agentcore_gateway_integration.py --skip-cleanup

# 기존 IAM 역할 사용(역할 생성 건너뛰기)
python 02_agentcore_gateway_integration.py --role-arn arn:aws:iam::123456789012:role/MyRole

# 모든 옵션 보기
python 02_agentcore_gateway_integration.py --help
```
