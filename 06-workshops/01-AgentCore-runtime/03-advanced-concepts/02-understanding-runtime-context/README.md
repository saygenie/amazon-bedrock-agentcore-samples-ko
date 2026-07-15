# AgentCore Runtime의 Runtime Context 및 세션 관리 이해

## 개요

이 자습서에서는 Amazon Bedrock AgentCore Runtime의 Runtime Context와 세션 관리를 이해하고 사용하는 방법을 학습합니다. 이 예제는 AgentCore Runtime이 세션을 처리하고 여러 호출에 걸쳐 context를 유지하는 방법과 에이전트가 context 객체를 통해 Runtime 정보에 액세스하는 방법을 보여 줍니다.

Amazon Bedrock AgentCore Runtime은 각 사용자 상호 작용에 격리된 세션을 제공합니다. 이를 통해 서로 다른 사용자 간에 완전한 보안 격리를 보장하면서 에이전트가 여러 호출에 걸쳐 context와 상태를 유지할 수 있습니다.

### 자습서 세부 정보

|정보| 세부 정보|
|:--------------------|:---------------------------------------------------------------------------------|
| 자습서 유형         | Context 및 세션 관리|
| 에이전트 유형       | 단일           |
| 에이전틱 프레임워크 | Strands Agents |
| LLM 모델            | Anthropic Claude Haiku 4.5 |
| 자습서 구성 요소    | Runtime Context, 세션 관리, AgentCore Runtime, Strands Agent 및 Amazon Bedrock 모델 |
| 자습서 분야         | 여러 산업 분야                                                                   |
| 예제 난이도         | 중급                                                                              |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK 및 boto3|

### 자습서 아키텍처

이 자습서에서는 Amazon Bedrock AgentCore Runtime이 세션을 관리하고 에이전트에 context를 제공하는 방법을 살펴봅니다. 다음 내용을 보여 줍니다.

1. **세션 연속성**: 동일한 세션 ID가 여러 호출에 걸쳐 context를 유지하는 방법
2. **Context 객체**: 에이전트가 context 매개변수를 통해 Runtime 정보에 액세스하는 방법
3. **세션 격리**: 서로 다른 세션 ID가 완전히 격리된 환경을 생성하는 방법
4. **유연한 payload**: payload를 통해 에이전트에 사용자 지정 데이터를 전달하는 방법

데모를 위해 이러한 세션 관리 기능을 보여 주는 Strands Agent를 사용합니다.

    
<div style="text-align:left">
    <img src="images/architecture_runtime.png" width="60%"/>
</div>

### 자습서 주요 기능

* **세션 기반 Context 관리**: AgentCore Runtime이 세션 내에서 context를 유지하는 방법 이해
* **Runtime 세션 수명 주기**: 세션 생성, 유지, 종료 학습
* **Context 객체 액세스**: context 매개변수를 통해 세션 ID 같은 Runtime 정보에 액세스
* **세션 격리**: 서로 다른 세션이 완전한 격리를 제공하는 방식 확인
* **Payload 처리**: 사용자 지정 payload 구조를 통한 유연한 데이터 전달
* **호출 간 상태**: 동일한 세션 내의 여러 호출에 걸쳐 에이전트 상태 유지
