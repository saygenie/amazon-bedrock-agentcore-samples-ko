# Amazon Bedrock AgentCore Runtime에서 명령 실행

이 자습서에서는 `invoke_agent_runtime_command` API를 사용하여 Amazon Bedrock AgentCore Runtime 환경에서 시스템 명령을 직접 실행하는 방법을 보여 줍니다. 에이전트를 배포하고 컨테이너화된 Runtime에서 shell 명령을 실행하며 출력을 실시간으로 스트리밍하는 방법을 학습합니다.

## 사전 요구 사항

자습서를 시작하기 전에 다음 항목을 준비하세요.

- Bedrock AgentCore에 대한 적절한 권한이 있는 **AWS 계정**
- 자격 증명으로 구성된 **AWS CLI**
- **Python 3.12+** 설치
- **Jupyter Notebook** or JupyterLab
- 사용 중인 AWS 리전의 **Amazon Bedrock AgentCore 액세스**

필수 Python package:
```bash
pip install -r requirements.txt
```

## 시작하기

1. **이 repository를 clone하거나 download**

2. **Notebook 열기: [01_exec_command.ipynb](./01_exec_command.ipynb)**


3. **Notebook 셀을 순서대로 실행**
   - Notebook에는 자세한 주석이 포함된 단계별 지침이 있습니다.
   - 에이전트 파일을 생성한 후 kernel을 다시 시작하세요(2단계).

## 학습 내용

이 자습서를 완료하면 다음 작업을 수행할 수 있습니다.

1. Python 코드를 직접 배포하여 **Bedrock AgentCore Agent 배포**(Docker 불필요)
2. 상위 수준 SDK 메서드와 직접 boto3 호출을 모두 사용하여 **에이전트 호출**
3. `invoke_agent_runtime_command`로 에이전트 Runtime 환경에서 **shell 명령 실행**
4. 적절한 event 처리로 **명령 출력을 실시간 스트리밍**

## 자습서 세부 정보

| **속성**              | **세부 정보**                                        |
|-----------------------|------------------------------------------------------|
| **자습서 유형**       | Agent Runtime에서 명령 실행                          |
| **도구 유형**         | Bedrock AgentCore Runtime                            |
| **구성 요소**         | 에이전트 배포, 명령 실행, Event 스트리밍             |
| **난이도**            | 중간                                                 |
| **사용 SDK**          | boto3, bedrock-agentcore-starter-toolkit             |


## 자습서 주요 기능

### 1. 코드 직접 배포
- Docker 불필요
- Python 코드를 Runtime에 직접 배포
- 종속성 자동 packaging

### 2. 에이전트 호출 방법
- **상위 수준 SDK**: Toolkit을 사용한 간소화된 호출
- **직접 boto3 호출**: AWS SDK를 사용한 전체 제어

### 3. 명령 실행(주요 기능)
에이전트 Runtime에서 임의의 shell 명령을 실행합니다.

```python
response = client.invoke_agent_runtime_command(
    agentRuntimeArn=agent_arn,
    body={
        'command': '/bin/bash -c "ls -l /tmp"',
        'timeout': 300
    }
)
```

### 4. Event Stream 처리
실시간 명령 출력을 처리합니다.

## 사용 사례

이 명령 실행 기능은 다음 작업에 유용합니다.

- **Debugging**: Runtime 환경 검사
- **파일 작업**: 에이전트 컨테이너의 파일 관리
- **통합 테스트**: 에이전트 환경 내에서 테스트 실행
- **데이터 처리**: 스크립트 실행 및 결과 처리
- **시스템 진단**: Runtime 구성 및 리소스 확인

## 프로젝트 구조

```
.
├── 01_exec_command.ipynb        # 기본 자습서 Notebook
├── agents/
│   ├── agent.py                 # 에이전트 진입점
│   └── requirements.txt         # 에이전트 종속성
└── README.md                    # 이 파일
```

## 정리

지속적인 비용이 발생하지 않도록 Notebook의 정리 섹션(7단계)을 사용하세요.

```python
from bedrock_agentcore_starter_toolkit.operations.runtime.destroy import destroy_bedrock_agentcore

destroy_bedrock_agentcore(
    config_path=Path(".bedrock_agentcore.yaml"),
    agent_name="exec_cmd_sample"
)
```

## 추가 리소스

- [Bedrock AgentCore 문서](https://docs.aws.amazon.com/bedrock/)
- [Runtime 세션 컨테이너에서 명령을 실행하는 Boto3 API](https://docs.aws.amazon.com/boto3/latest/reference/services/bedrock-agentcore/client/invoke_agent_runtime_command.html)
