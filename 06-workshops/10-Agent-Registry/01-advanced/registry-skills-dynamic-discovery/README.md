# AWS Agent Registry를 사용한 Agent Skills 게시 및 검색

## 개요

AWS Agent Registry는 조직 전반의 AI 에이전트, MCP 서버, Agent Skills 및 사용자 지정 리소스를 구성하고 선별하며 검색할 수 있는 중앙 집중식 카탈로그를 제공하는 완전관리형 검색 서비스입니다. 게시자는 검색 가능한 레지스트리에 리소스를 등록하고, 큐레이터는 승인 대상을 관리하며, 소비자는 시맨틱 검색과 키워드 검색을 사용하여 적합한 도구와 에이전트를 찾습니다.

### Agent Skills란?

[Agent Skill](https://agentskills.io/specification)은 여러 에이전트에서 공유할 수 있는 재사용 가능한 기능입니다. 호출 가능한 도구를 정의하는 MCP 서버나 자율적인 에이전트 간 통신을 정의하는 A2A 에이전트와 달리, 스킬은 문서, 스크립트, 참조 자료 및 패키지 종속성을 비롯해 에이전트가 특정 작업을 수행하는 방법을 익히는 데 필요한 **지침과 컨텍스트**를 패키징합니다.

스킬은 다음 폴더 구조를 따르며 `SKILL.md`만 필수입니다.

```
my-skill/
├── SKILL.md          # 필수: 지침 + metadata(YAML frontmatter + Markdown)
├── scripts/          # 선택 사항: 실행 코드
├── references/       # 선택 사항: 문서, runbook
└── assets/           # 선택 사항: template, config, sample data
```

### Agent Registry에서 스킬이 표현되는 방식

Agent Registry의 `AGENT_SKILLS` 레코드에는 두 가지 설명자가 포함됩니다.

| 구성 요소 | 설명 |
|---|---|
| `skillMd` | 전체 `SKILL.md` 콘텐츠(YAML 프런트매터 + Markdown 지침)입니다. 시맨틱 검색을 위해 인덱싱되며 검색 결과로 반환됩니다. |
| `skillDefinition` | `repository` 참조(예: 지원 파일을 다운로드할 GitHub URL)와 `packages` 목록(PyPI, npm 등의 런타임 종속성)을 포함하는 구조화된 JSON 메타데이터입니다. [Agent Skills 스키마](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/registry-supported-record-types.html)에 따라 검증됩니다. |

### 아키텍처 흐름

![아키텍처 흐름](images/registry-skill-flow.png)

### 동적 스킬 검색

이 튜토리얼에서는 AI 에이전트가 런타임에 Agent Registry에서 스킬을 동적으로 검색하고 로드하는 패턴을 보여 줍니다. 흐름은 다음과 같습니다.

1. 소비자 에이전트가 사용자 작업(예: "Create a PDF")을 받습니다.
2. 에이전트가 시맨틱 검색을 사용하여 Agent Registry에서 일치하는 스킬을 검색합니다.
3. 에이전트가 스킬의 이름과 설명을 읽고 관련성이 있는지 판단합니다.
4. 스킬이 일치하면 에이전트가 스킬 패키지(SKILL.md + 리포지토리의 지원 파일)를 다운로드하고 종속성을 설치한 후 지침을 로드합니다.
5. 에이전트가 스킬 지침에 따라 작업을 실행합니다.

이를 통해 에이전트는 가능한 모든 스킬을 미리 구성하지 않고도 필요할 때 새로운 기능을 확보할 수 있습니다.

### 튜토리얼 세부 정보

| 정보                  | 세부 정보                                                                                 |
|:---------------------|:-----------------------------------------------------------------------------------------|
| 튜토리얼 유형         | 대화형                                                                                    |
| AgentCore 구성 요소   | AWS Agent Registry                                                                       |
| 에이전트 프레임워크   | Strands Agents                                                                           |
| 레코드 유형           | `AGENT_SKILLS`                                                                           |
| 인증 유형             | IAM SigV4                                                                                |
| LLM 모델              | Anthropic Claude Sonnet 4                                                                |
| 튜토리얼 구성 요소    | 레지스트리 생성, 스킬 등록, 승인 워크플로, 시맨틱 검색, 동적 스킬 로드 및 실행 |
| 튜토리얼 분야         | PDF 처리                                                                                 |
| 예제 난이도           | 중급                                                                                     |
| 사용 SDK              | boto3                                                                                    |

### 이 튜토리얼에서 다루는 내용

1. **Agent Registry 생성**: 스킬 레코드를 저장할 수 있도록 수동 승인을 사용하는 레지스트리를 설정합니다.
2. **Agent Skill 등록**: `SKILL.md` 지침과 스킬의 GitHub 리포지토리 및 PyPI 종속성을 참조하는 `skillDefinition`을 포함한 PDF 처리 스킬을 게시합니다.
3. **스킬 레코드 승인**: 스킬을 검색할 수 있도록 승인 워크플로(DRAFT → PENDING_APPROVAL → APPROVED)를 진행합니다.
4. **동적 스킬 검색 및 실행**: Agent Registry를 검색하고 일치하는 스킬 패키지를 다운로드하여 종속성을 설치한 후 런타임에 지침을 로드하는 사용자 지정 `search_and_load_skill` 도구를 포함한 Strands Agent를 구축합니다.
5. **작업 실행**: 에이전트에 자연어 요청을 보내고 에이전트가 스킬을 검색하고 로드하여 작업을 완료하는 과정을 확인합니다.
6. **정리**: 스킬 레코드와 레지스트리를 삭제합니다.

## 튜토리얼

- [AWS Agent Registry의 Agent Skills](registry-skills-dynamic-discovery.ipynb)
