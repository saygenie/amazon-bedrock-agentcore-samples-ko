# AgentCore 엔드 투 엔드 워크숍

이 워크숍에서는 Amazon Bedrock AgentCore 서비스를 사용해 프로토타입부터 프로덕션까지 완전한 고객 지원 에이전트를 구축합니다. 동일한 워크숍이 세 가지 에이전트 프레임워크로 구현되어 있으므로 선호하는 프레임워크를 선택해 학습할 수 있습니다.

> [!IMPORTANT]
> 이 워크숍은 교육용입니다. 에이전트 사용 사례를 프로토타입에서 프로덕션으로 전환할 때 AgentCore 서비스가 어떻게 활용되는지 보여 주며, 프로덕션 환경에서 직접 사용하는 것을 목적으로 하지 않습니다.

## 프레임워크

| 프레임워크                                             | 폴더                               | 상태        |
| ------------------------------------------------------ | ---------------------------------- | ----------- |
| [Strands Agents](https://strandsagents.com/)           | [strands-agents/](strands-agents/) | 이용 가능   |
| [Google ADK](https://google.github.io/adk-docs/)       | [google-adk/](google-adk/)         | 공개 예정   |
| [LangGraph](https://langchain-ai.github.io/langgraph/) | [langgraph/](langgraph/)           | 공개 예정   |

## 구축할 내용

6개의 실습을 통해 프로덕션 수준의 고객 지원 에이전트를 단계적으로 구축합니다. 이 에이전트에는 서버리스 배포를 위한 AgentCore Runtime, 개인화된 대화를 위한 AgentCore Memory, 안전한 도구 공유를 위한 AgentCore Gateway와 Identity, Cedar 정책을 활용한 세분화된 액세스 제어를 위한 AgentCore Policy, 에이전트 동작을 추적하고 모니터링하기 위한 AgentCore Observability, 지속적인 품질 모니터링을 위한 AgentCore Evaluations, 고객 상호 작용을 위한 Streamlit 프런트엔드가 포함됩니다.

각 프레임워크 폴더는 자체 README, 노트북, 종속성을 포함해 독립적으로 구성되어 있습니다. 프레임워크를 하나 선택한 후 해당 README의 안내에 따라 시작하세요.
