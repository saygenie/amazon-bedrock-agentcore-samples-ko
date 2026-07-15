# Amazon Bedrock AgentCore Runtime을 사용하는 주간 상태 보고서 생성기

## 개요

이 자습서에서는 Amazon Bedrock AgentCore Runtime을 사용하여 자동화된 주간 상태 보고서 생성기를 구축하고 배포하는 방법을 학습합니다. 에이전트는 여러 소스(팀 업데이트, 회의록, metric, 버그 추적기)에서 데이터를 수집하고 분석과 시각화를 수행한 뒤 종합 보고서를 S3에 업로드합니다.

### 자습서 세부 정보

| 정보                | 세부 정보                                                                        |
|:--------------------|:---------------------------------------------------------------------------------|
| 자습서 유형         | 데이터 분석 및 보고                                                              |
| 에이전트 유형       | 단일                                                                              |
| 에이전틱 프레임워크 | Strands Agents                                                                    |
| LLM 모델            | Anthropic Claude Sonnet 4                                                        |
| 자습서 구성 요소    | 멀티 도구 에이전트, 데이터 분석, 시각화, S3 통합, AgentCore Runtime             |
| 자습서 분야         | 비즈니스 운영 및 보고                                                            |
| 예제 난이도         | 중급                                                                              |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK, boto3, matplotlib, scikit-learn              |

### 자습서 아키텍처

이 자습서에서는 보고 에이전트를 AgentCore Runtime에 배포하는 방법을 보여 줍니다. 에이전트는 여러 도구를 사용하여 다음 작업을 수행합니다.
- 다양한 소스(CSV, JSON, Markdown 파일)의 데이터 읽기 및 분석
- 감성 분석 및 위험 점수 산정
- 데이터 시각화 생성(차트 및 그래프)
- Machine learning을 사용한 예측 모델 구축
- 보고서 및 시각화를 S3에 업로드

에이전트는 16개의 서로 다른 도구를 오케스트레이션하여 종합적인 주간 상태 보고서를 자동으로 생성합니다.

![Architecture Diagram](01_weekly_report_generator_async/images/architecture.png)

### 자습서 주요 기능

* Amazon Bedrock AgentCore Runtime에서 비동기 멀티 도구 에이전트 호스팅
* Amazon Bedrock 모델(Claude Sonnet 4) 사용
* Strands Agents 프레임워크 사용


## 사전 요구 사항

- Amazon Bedrock AgentCore에 액세스할 수 있는 AWS 계정
- Python 3.12+
- 적절한 자격 증명으로 구성된 AWS CLI
- 데모 데이터와 보고서를 저장할 S3 bucket

## 프로젝트 구조

```
├── README.md                              # 이 파일
└── 01_weekly_report_generator_async/     # Agent 코드 및 데이터
    ├── weekly_update_agentcore_deploy.ipynb  # 배포 Notebook
    ├── images/                            # 아키텍처 다이어그램
    ├── agent/                             # Agent 구현
    │   ├── agent.py                     # 기본 agent 정의
    │   ├── tools.py                     # 모든 tool 함수(16개 tool)
    │   ├── requirements.txt             # Python 의존성
    │   └── .dockerignore                # Docker ignore 패턴
    ├── demo_data/                       # 샘플 데이터 디렉터리
    │   ├── team_updates/                # 팀원 업데이트(Markdown)
    │   ├── meeting_notes/               # 회의록(Markdown)
    │   ├── metrics/                     # KPI 지표(CSV)
    │   ├── issues/                      # Bug tracker 데이터(JSON)
    │   └── project_status/              # 프로젝트 상태(CSV)
    └── update_demo_dates.py             # Demo 데이터 관리 script
```



## 에이전트 동작

에이전트는 호출되면 다음 작업을 수행합니다.

1. 여러 소스에서 **데이터 수집**
   - 팀원 업데이트(5명)
   - 회의록(3개 회의)
   - KPI metric(과거 및 현재)
   - 버그 추적기 데이터
   - 프로젝트 상태 정보

2. **데이터 분석**
   - 데이터 품질 검증
   - 업데이트에 언급된 버그 상호 참조
   - 팀 업데이트 감성 분석
   - 프로젝트 위험 점수 계산

3. **시각화 생성**
   - 버그 심각도 pie chart
   - Metric 상태 bar chart
   - 프로젝트 timeline chart
   - 팀 velocity chart
   - Metric 예측 chart(ML 예측 포함)

4. **보고서 생성**
   - 모든 정보를 종합적인 Markdown 보고서로 통합
   - 경영진 요약, 팀 주요 내용, KPI, 위험, 실행 항목 포함

5. **S3에 업로드**
   - Markdown 보고서 업로드
   - 생성된 모든 chart 업로드
   - 연도 및 주별로 정리: `s3://bucket/weekly_reports/2026/week_09_2026-02-23/`
