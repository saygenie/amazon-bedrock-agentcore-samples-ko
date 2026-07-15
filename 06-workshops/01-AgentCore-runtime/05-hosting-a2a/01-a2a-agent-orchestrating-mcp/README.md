## AgentCore Runtime에서 A2A 시작하기

### 개요

Amazon Bedrock AgentCore Runtime은 AI 에이전트와 도구를 배포하고 확장하도록 설계된 안전한 serverless Runtime입니다.
모든 프레임워크, 모델, 프로토콜을 지원하므로 개발자는 최소한의 코드 변경으로 로컬 프로토타입을 프로덕션용 솔루션으로 전환할 수 있습니다.

[Strands Agents](https://strandsagents.com/latest/)는 사용하기 쉬운 code-first 에이전트 구축 프레임워크입니다.

AWS는 AgentCore Runtime의 [A2A 지원](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-a2a.html)을 발표했습니다.

이 예제에서는 Amazon Bedrock AgentCore와 Strands Agents를 사용하여 멀티 에이전트 시스템을 구축합니다.

이 자습서에서는 3개의 에이전트를 생성합니다. 첫 번째는 MCP를 사용하여 AWS Docs를 활용하는 AWS 문서 전문가입니다. 두 번째는 웹에서 최신 블로그와 AWS News를 검색합니다. 세 번째는 MCP를 사용하여 앞의 에이전트를 호출하는 오케스트레이터입니다.

<img src="images/architecture.png" style="width: 80%;">

### 자습서 개요

이 자습서에서는 다음 기능을 다룹니다.

- [1 - Strands 및 Bedrock AgentCore로 A2A 시작하기](01-a2a-getting-started-agentcore-strands.ipynb)
- [2 - A2A를 사용하여 하위 에이전트를 호출하는 오케스트레이터 생성](02-a2a-deploy-orchestrator.ipynb)
- [3 - 정리](03-a2a-cleanup.ipynb)
