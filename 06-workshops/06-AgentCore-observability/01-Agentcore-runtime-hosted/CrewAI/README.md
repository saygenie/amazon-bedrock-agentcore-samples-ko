# Amazon Bedrock AgentCore Runtime 및 Observability를 사용하는 CrewAI 에이전트

이 자습서에서는 Amazon CloudWatch를 통한 관측성을 갖춘 [CrewAI](https://www.crewai.com/) 여행 에이전트를 Amazon Bedrock AgentCore Runtime에 배포하는 방법을 살펴봅니다.

## 개요

Amazon Bedrock 모델을 사용하는 CrewAI 에이전트를 호스팅하고 AWS OpenTelemetry 계측과 Amazon CloudWatch 모니터링으로 포괄적인 관측성을 구현하는 방법을 학습합니다.

## 사전 요구 사항

* Python 3.10+
* 적절한 권한으로 구성된 AWS 자격 증명
* Amazon Bedrock AgentCore SDK
* CrewAI 프레임워크
* Amazon CloudWatch 액세스 권한
* Amazon CloudWatch에서 [Transaction Search](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Enable-TransactionSearch.html) 활성화

## 시작하기

1. 종속성을 설치합니다.
   ```bash
   pip install -r requirements.txt
   ```

2. Jupyter notebook을 엽니다: `runtime-with-crewai-and-bedrock-models.ipynb`

3. 자습서에 따라 다음을 수행합니다.
   - 로컬에서 CrewAI 에이전트 생성 및 테스트
   - AgentCore Runtime에 에이전트 배포
   - OpenTelemetry로 관측성 활성화
   - CloudWatch에서 성능 모니터링

## 주요 기능

* 웹 검색 기능을 갖춘 CrewAI 여행 에이전트
* Amazon Bedrock 모델(Anthropic Claude Haiku 4.5)
* AgentCore Runtime 호스팅
* CloudWatch 관측성 및 트레이싱

## 정리

자습서를 완료한 후 다음을 수행합니다.
1. AgentCore Runtime 배포를 제거합니다.
2. ECR 저장소를 정리합니다.
