# Amazon Bedrock AgentCore Runtime에서 AgentSkills Plugin을 사용하는 Strands Agents 호스팅

## 개요

이 자습서에서는 필요할 때 전문 지침을 제공하는 `AgentSkills` plugin을 사용하는 Strands 에이전트를 Amazon Bedrock AgentCore Runtime에서 호스팅하는 방법을 학습합니다.

`AgentSkills` plugin을 사용하면 YAML frontmatter가 포함된 Markdown 파일(`SKILL.md`)로 재사용 가능한 skill을 정의할 수 있습니다. 각 skill은 이름, 설명, 허용된 도구, 행동 지침을 선언합니다. 에이전트는 Runtime에서 사용 가능한 skill을 검색하고 사용자 요청에 따라 적절한 skill을 활성화합니다.

날씨 데이터를 이모지, 온도 범위, 권장 사항과 함께 형식화하는 **weather-reporter** skill과 풀이 과정을 모두 보여 주며 수학 문제를 단계별로 해결하는 **math-tutor** skill을 생성합니다. 먼저 로컬에서 실험한 다음 에이전트를 AgentCore Runtime에 배포합니다.

Skill을 사용하지 않는 기본 Strands 에이전트는 [여기](../01-strands-with-bedrock-model)를 참조하세요.

### 자습서 세부 정보

| 정보                | 세부 정보                                                                                                        |
|:--------------------|:-----------------------------------------------------------------------------------------------------------------|
| 자습서 유형         | 대화형                                                                                                           |
| 에이전트 유형       | 단일                                                                                                             |
| 에이전틱 프레임워크 | Strands Agents                                                                                                   |
| LLM 모델            | Anthropic Claude Haiku 4.5                                                                                       |
| 자습서 구성 요소    | AgentCore Runtime에서 에이전트 호스팅, AgentSkills plugin으로 필요할 때 skill 활성화                             |
| 자습서 분야         | 여러 산업 분야                                                                                                   |
| 예제 난이도         | 중급                                                                                                             |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK 및 boto3                                                                     |

### 자습서 아키텍처

이 자습서에서는 skill 기반 에이전트를 AgentCore Runtime에 배포하는 방법을 설명합니다.

데모를 위해 `skills/` 디렉터리에서 skill 정의를 불러오는 `AgentSkills` plugin과 Strands Agent를 사용합니다. 각 skill은 YAML frontmatter(`name`, `description`, `allowed-tools`)와 Markdown 지침이 포함된 `SKILL.md` 파일을 가진 폴더입니다.

<div style="text-align:left">
    <img src="images/architecture_runtime.png" width="100%"/>
</div>

에이전트는 두 가지 skill을 사용합니다.
- **weather-reporter**: 사용자 지정 `@tool` 날씨 함수와 연결되어 날씨 정보를 이모지 및 권장 사항과 함께 형식화합니다.
- **math-tutor**: `strands-agents-tools`의 `calculator` 도구와 연결되어 수학 문제를 단계별로 풉니다.

에이전트는 Amazon Bedrock을 통해 Anthropic Claude Haiku 4.5에서 실행됩니다.

### 자습서 주요 기능

* Amazon Bedrock AgentCore Runtime에서 에이전트 호스팅
* 필요할 때 전문 지침을 제공하는 Strands `AgentSkills` plugin 사용
* YAML frontmatter를 사용하는 `SKILL.md` 파일로 skill 정의
* Skill을 사용자 지정 `@tool` 함수 및 기존 도구와 연결
* 배포 전 로컬 에이전트 실험
* Skill 기반 에이전트를 AgentCore Runtime에 배포
