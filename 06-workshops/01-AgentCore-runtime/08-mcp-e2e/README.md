# Stateful MCP 예제

Amazon Bedrock AgentCore Runtime에서 MCP(Model Context Protocol) 서버 및 클라이언트 기능을 보여 주는 end-to-end 자습서입니다.

## AgentCore Runtime의 MCP 기능 지원

<table>
  <thead>
    <tr>
      <th>카테고리</th>
      <th>기능</th>
      <th>사양 Method</th>
      <th align="center">Runtime</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td rowspan="4"><strong>MCP 서버 기능</strong></td>
      <td>Tools</td>
      <td><code>tools/list</code>, <code>tools/call</code></td>
      <td align="center">✅</td>
    </tr>
    <tr>
      <td>Tools(output schema)</td>
      <td><code>output schema</code></td>
      <td align="center">✅</td>
    </tr>
    <tr>
      <td>Resources</td>
      <td><code>resources/list</code>, <code>resources/read</code>, <code>resources/subscribe</code></td>
      <td align="center">✅</td>
    </tr>
    <tr>
      <td>Prompts</td>
      <td><code>prompts/list</code>, <code>prompts/get</code></td>
      <td align="center">✅</td>
    </tr>
    <tr>
      <td rowspan="3"><strong>MCP 클라이언트 기능</strong></td>
      <td>Sampling</td>
      <td><code>sampling/createMessage</code></td>
      <td align="center">✅</td>
    </tr>
    <tr>
      <td>Roots</td>
      <td><code>roots/list</code></td>
      <td align="center">TBD</td>
    </tr>
    <tr>
      <td>Elicitation</td>
      <td><code>elicitation/create</code></td>
      <td align="center">✅</td>
    </tr>
    <tr>
      <td rowspan="2"><strong>MCP 기본 프로토콜</strong></td>
      <td>수명 주기</td>
      <td><code>initialize</code>, <code>initialized</code>, <code>ping</code></td>
      <td align="center">✅</td>
    </tr>
    <tr>
      <td>전송</td>
      <td><code>response streaming</code></td>
      <td align="center">✅</td>
    </tr>
    <tr>
      <td rowspan="4"><strong>MCP 유틸리티</strong></td>
      <td>진행률</td>
      <td><code>notifications/progress</code></td>
      <td align="center">✅</td>
    </tr>
    <tr>
      <td>취소</td>
      <td><code>notifications/cancelled</code></td>
      <td align="center">TBD</td>
    </tr>
    <tr>
      <td>Logging</td>
      <td><code>logging/setLevel</code></td>
      <td align="center">✅</td>
    </tr>
    <tr>
      <td>작업</td>
      <td><code>tasks/list</code>, <code>tasks/cancel</code></td>
      <td align="center">✅</td>
    </tr>
  </tbody>
</table>

> **범례:** ✅ 지원 &nbsp;|&nbsp; TBD 결정 예정

## 프로젝트 구조

```
Stateful/
├── 1-server-e2e/          # MCP 서버 기능(Tools, Resources, Prompts)
├── 2-client-e2e/          # MCP 클라이언트 기능(Elicitation, Sampling, Roots)
├── 3-utilities-e2e/       # MCP 유틸리티(Progress Notifications)
└── helpers/               # AWS 서비스 및 배포용 공유 유틸리티
```

### 1. MCP 서버 기능(`1-server-e2e/`)

세 가지 핵심 기능을 모두 갖춘 MCP 서버를 구축하고 배포하는 방법을 보여 주는 전체 자습서입니다.

- **Tools**: 지출 추적용 실행 함수(transaction 추가, 목록 조회, 상세 조회)
- **Resources**: 읽을 수 있는 resource로 제공되는 동적 지출 보고서
- **Prompts**: 지출 분석 및 분류를 위한 미리 정의된 template

**자습서:** [📓 mcp_server_features_e2e.ipynb](./01-server-e2e/mcp_server_features_e2e.ipynb)

**포함 내용:**
- AgentCore Runtime에 배포
- 영구 저장을 위한 DynamoDB 통합
- Cognito 인증 설정
- 실제 지출 추적 예제

### 2. MCP 클라이언트 기능(`2-client-e2e/`)

고급 stateful 상호 작용을 위한 클라이언트 측 MCP 기능을 보여 줍니다.

- **Elicitation**: 여러 턴에 걸친 대화형 사용자 입력 수집(예: 안내형 지출 입력)
- **Sampling**: AI 기반 분석을 위해 서버가 LLM 추론을 클라이언트에 위임
- **Roots**: 클라이언트가 파일 시스템 root를 서버에 노출(Runtime 지원 제한)

**자습서:** [📓 mcp_client_features_e2e.ipynb](./02-client-e2e/mcp_client_features_e2e.ipynb)


### 3. MCP 유틸리티(`3-utilities-e2e/`)

사용자 경험을 개선하는 MCP 유틸리티 기능 자습서입니다.

- **Progress Notifications**: 장시간 작업 중 실시간 실행 업데이트

**자습서:** [📓 01_progress.ipynb](./03-utilities-e2e/01_progress.ipynb)

**주요 내용:**
- Fire-and-forget 방식 진행률 업데이트(elicitation/sampling 같은 요청/응답 방식과 비교)
- 실시간 progress bar를 사용하는 5단계 월간 재무 보고서
- 실행 상태 스트리밍을 위한 `ctx.report_progress()`
- 클라이언트의 사용자 지정 `progress_handler` callback

### 4. 공유 유틸리티(`helpers/`)

자습서 전반에서 사용하는 공통 유틸리티입니다.

- `utils.py`: AWS 서비스 helper(Cognito, IAM, DynamoDB)
- `dynamo_utils.py`: 재무 추적용 DynamoDB 작업

**Notebook 사용 예:**
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))

from helpers.utils import get_or_create_cognito_pool
from helpers.dynamo_utils import FinanceDB
```

## 사전 요구 사항

- 적절한 권한으로 구성된 AWS CLI
- Python 3.12+(Runtime 배포에는 3.13 권장)
- Jupyter Notebook 환경
- Amazon Bedrock AgentCore Runtime 액세스
- AWS 서비스: DynamoDB, Cognito, IAM


**AgentCore Runtime:**
- Cognito를 통한 전체 인증
- 관리형 인프라 및 확장


## 리소스

- [MCP 사양](https://modelcontextprotocol.io/specification/2025-11-25/server)
- [AWS Bedrock AgentCore 문서](https://docs.aws.amazon.com/bedrock-agentcore/)
