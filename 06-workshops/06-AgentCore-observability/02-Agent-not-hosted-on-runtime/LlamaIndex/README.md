# AWS Bedrock 및 OpenTelemetry를 사용하는 LlamaIndex Function Agent

이 프로젝트에서는 LlamaIndex로 간단한 산술 에이전트를 만들고, AgentCore Observability 트레이싱을 위한 OpenTelemetry 계측과 함께 AWS Bedrock에서 호스팅하는 방법을 살펴봅니다.

## 프로젝트 개요

이 프로젝트에서는 다음을 구현합니다.
- LlamaIndex.core의 FunctionAgent를 사용하는 함수 에이전트 패턴
- LLM 백엔드를 위한 AWS Bedrock의 Claude 모델 통합
- AWS CloudWatch 관측성을 위한 OpenTelemetry 계측
- 간단한 산술 도구(덧셈 및 곱셈)
- 여러 에이전트 실행의 트레이스를 연결하기 위한 세션 추적 기능

## 아키텍처 다이어그램

다음 다이어그램은 AWS Bedrock 및 OpenTelemetry를 사용하는 LlamaIndex 에이전트 구현의 아키텍처를 보여 줍니다.

![LlamaIndex AgentCore 아키텍처 다이어그램](images/llamaindex_agentcore_arch_diagram.png)

## 사전 요구 사항

- Python 3.9+
- Bedrock 서비스(특히 Claude 모델)에 액세스할 수 있는 AWS 계정
- 로컬에 구성된 AWS 자격 증명
- AWS Bedrock 및 CloudWatch에 대한 적절한 IAM 권한
- CloudWatch Transaction Search 활성화(트레이스 확인용)

## 설치

1. 전체 Amazon Bedrock AgentCore Samples 저장소를 복제한 경우:
```bash
git clone https://github.com/aws-samples/amazon-bedrock-agentcore-samples.git
cd amazon-bedrock-agentcore-samples/06-workshops/06-AgentCore-observability/02-Agent-not-hosted-on-runtime/LlamaIndex
```

2. 가상 환경을 생성하고 활성화합니다.
```bash
# 가상 환경 생성
python -m venv venv

# 가상 환경 활성화
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
```

3. 종속성을 설치합니다.
```bash
pip install -r requirements.txt
```

4. Jupyter 또는 VS Code에서 notebook을 열 때:
   - 커널 선택기에서 "venv" 커널을 선택합니다.
   - 커널이 목록에 표시되지 않으면 Jupyter 또는 VS Code를 다시 시작합니다.

## 구성

### AWS 자격 증명

AWS Bedrock 및 CloudWatch에 액세스할 수 있도록 AWS 자격 증명이 올바르게 구성되었는지 확인합니다.

CLI에서 ```aws configure```를 실행하여 Amazon 자격 증명을 올바르게 구성합니다. 자격 증명을 .env 파일에 저장할 필요는 없습니다.

### OpenTelemetry 구성

이 프로젝트에서는 다음 OpenTelemetry 환경 변수를 사용합니다. `.env` 파일에 설정하되 `.env.example`을 템플릿으로 사용하세요.

```bash
# Agent 구성
AGENT_ID=llama-index-function-agent
SERVICE_NAME=llama-index-bedrock-agent
BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0

# OpenTelemetry 구성
AGENT_OBSERVABILITY_ENABLED=true
OTEL_PYTHON_DISTRO=aws_distro
OTEL_PYTHON_CONFIGURATOR=aws_configurator
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_TRACES_EXPORTER=otlp
```

### CloudWatch 로그 그룹 설정

에이전트를 실행하기 전에 CloudWatch에 로그 그룹과 로그 스트림을 생성해야 합니다.

```python
import boto3

cloudwatch_client = boto3.client("logs")
cloudwatch_client.create_log_group(logGroupName='agents/llama-index-agent-logs')
cloudwatch_client.create_log_stream(logGroupName='agents/llama-index-agent-logs', logStreamName='default')
```

그런 다음 `.env` 파일에 다음을 추가합니다.

```bash
OTEL_EXPORTER_OTLP_LOGS_HEADERS=x-aws-log-group=agents/llama-index-agent-logs,x-aws-log-stream=default,x-aws-metric-namespace=bedrock-agentcore
OTEL_RESOURCE_ATTRIBUTES=service.name=agentic-llamaindex-agentcore
```

## 사용 방법

### 기본 에이전트

OpenTelemetry 계측을 적용하여 기본 산술 에이전트를 실행하려면 다음 명령을 사용합니다.

```bash
opentelemetry-instrument python llama_index_agent.py
```

이 명령은 간단한 산술 작업 `What is (121 + 2) * 5?`를 실행합니다.

### 세션 추적 에이전트

트레이스를 연결하기 위한 세션 추적과 함께 에이전트를 실행하려면 다음 명령을 사용합니다.

```bash
opentelemetry-instrument python llama_index_agent_with_session.py --session-id "your-session-id"
```

이 버전에서는 일관된 세션 ID를 사용하여 여러 에이전트 실행의 트레이스를 연결할 수 있습니다.

## Jupyter 노트북 자습서

저장소에는 다음 내용을 보여 주는 Jupyter 노트북(`LlamaIndex_Observability.ipynb`)이 포함되어 있습니다.

1. 환경 및 사전 요구 사항 설정
2. 필요한 CloudWatch 로그 그룹 생성
3. 환경 변수 구성
4. 세션 추적 사용 여부에 따른 에이전트 실행
5. AWS CloudWatch 대시보드의 트레이스 이해

이 notebook은 적절한 관측성을 갖춘 에이전트를 설정하고 실행하는 대화형 자습서입니다.

## OpenTelemetry 계측 세부 정보

이 프로젝트에서는 AWS Distro for OpenTelemetry(ADOT)를 사용하여 텔레메트리 데이터를 AWS CloudWatch로 전송합니다. 계측은 `LlamaIndexOpenTelemetry` 클래스를 사용하여 설정하며, 이 클래스는 `llama_index.observability.otel`에서 가져옵니다.

주요 계측 지점:
- 에이전트 초기화
- AWS Bedrock에 대한 LLM 호출
- 도구 실행(각 도구에 자체 스팬 사용)
- 에이전트 쿼리 처리

### 트레이스 확인

트레이스를 확인하려면 다음을 수행합니다.
1. CloudWatch Transaction Search가 활성화되어 있는지 확인합니다.
2. CloudWatch 콘솔로 이동합니다.
3. GenAI Observability로 이동합니다.
4. 에이전트의 서비스 이름이 지정된 트레이스를 찾습니다(기본값: `agentic-llamaindex-agentcore`).

## 문제 해결

### 일반적인 문제

1. **AWS 자격 증명을 찾을 수 없음**
   - 환경에 AWS 자격 증명이 올바르게 설정되어 있는지 확인합니다.
   - IAM 사용자에게 Bedrock 및 CloudWatch에 대한 적절한 권한이 있는지 확인합니다.

2. **OpenTelemetry 트레이스가 표시되지 않음**
   - CloudWatch Transaction Search가 활성화되어 있는지 확인합니다.
   - `OTEL_EXPORTER_OTLP_LOGS_HEADERS`에 지정된 로그 그룹이 있는지 확인합니다.
   - AWS 리전이 올바르게 설정되어 있는지 확인합니다.

3. **Bedrock 모델 액세스**
   - `BEDROCK_MODEL_ID`에 지정된 Bedrock 모델에 액세스할 수 있는지 확인합니다.
   - 계정의 Bedrock 모델 처리량 할당량을 확인합니다.

4. **Jupyter Notebooks의 OpenTelemetry 경고**
   - Jupyter 노트북 셀에서 `opentelemetry-instrument`를 실행하면 다음과 같은 경고가 표시될 수 있습니다.
     ```
     WARNING:opentelemetry.trace:Overriding of current TracerProvider is not allowed
     ```
     또는 `SpanDropEvent` 관련 메시지와 오류로 종료되는 스팬 관련 메시지가 표시될 수 있습니다.
   - 이러한 경고는 노트북 환경에서 예상되는 동작이며 에이전트의 기능이나 관측성 데이터 수집에 영향을 주지 않습니다.
   - Jupyter에 자체 계측 컨텍스트가 있고 셀을 여러 번 실행하면 OpenTelemetry가 재등록을 시도할 수 있기 때문에 발생합니다.
   - 에이전트가 올바르게 실행되고 트레이스가 CloudWatch에 표시된다면 이러한 경고를 무시해도 됩니다.

### CloudWatch 로그 그룹

OpenTelemetry 트레이스는 환경 변수에 지정된 CloudWatch 로그 그룹으로 전송됩니다.
```
agents/llama-index-agent-logs
```

트레이스가 표시되지 않으면 이 로그 그룹이 존재하고 `.env` 파일에 올바르게 구성되어 있는지 확인합니다.


## 추가 자료

- [LlamaIndex 문서](https://docs.llamaindex.ai/)
- [AWS Bedrock 문서](https://docs.aws.amazon.com/bedrock)
- [OpenTelemetry 문서](https://opentelemetry.io/docs/)
- [AWS Distro for OpenTelemetry (ADOT)](https://aws.amazon.com/otel/)
- [CloudWatch Transaction Search 문서](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Enable-TransactionSearch.html)
