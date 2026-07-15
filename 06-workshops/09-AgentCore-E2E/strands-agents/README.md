# AgentCore를 활용한 엔드 투 엔드 고객 지원 에이전트

Amazon Bedrock AgentCore 서비스를 사용해 고객 지원 에이전트를 프로토타입에서 프로덕션으로 전환합니다. 6개의 실습을 통해 메모리, 공유 도구, 관찰 기능, 웹 인터페이스를 갖추고 실제 고객 대화를 처리하는 완전한 시스템을 구축합니다.

> [!IMPORTANT]
> 이 워크숍은 교육용입니다. 에이전트 사용 사례를 프로토타입에서 프로덕션으로 전환할 때 AgentCore 서비스가 어떻게 활용되는지 보여 주며, 프로덕션 환경에서 직접 사용하는 것을 목적으로 하지 않습니다.

## 아키텍처 개요

6개의 실습을 모두 마치면 다음 아키텍처를 구축하게 됩니다.

<div style="text-align:left">
    <img src="images/architecture_lab6_streamlit.png" width="100%"/>
</div>

## 사전 요구 사항

- Amazon Bedrock에 액세스할 수 있는 AWS 계정이 필요합니다.
- 로컬 환경에 Python 3.10 이상이 설치되어 있어야 합니다.
- 적절한 자격 증명으로 AWS CLI가 구성되어 있어야 합니다.
- [Amazon Bedrock 모델 액세스](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access.html) 설정에서 Amazon Nova 2 Lite가 활성화되어 있어야 합니다.

## 시작하기

### AWS Workshop 계정을 사용하지 않고 자율 학습으로 진행하는 경우

실습 1을 시작하기 전에 필요한 인프라(Lambda 함수, DynamoDB 테이블, IAM 역할, Cognito 사용자 풀, Bedrock Knowledge Base)를 프로비저닝해야 합니다. 다음 단계를 따르세요.

1. IAM 역할에 워크숍에 [필요한 권한](https://catalog.us-east-1.prod.workshops.aws/workshops/850fcd5c-fd1f-48d7-932c-ad9babede979/en-US/00-prerequisites/02-self-paced)이 있는지 확인합니다. 여기에는 워크숍 사전 요구 사항에 설명된 [IAM 정책, AWS 관리형 정책, 신뢰 관계](https://catalog.us-east-1.prod.workshops.aws/workshops/850fcd5c-fd1f-48d7-932c-ad9babede979/en-US/00-prerequisites/02-self-paced#iam-policy-for-bedrock-agentcore-workshop)가 포함됩니다.
2. 사전 요구 사항 스크립트를 실행하여 CloudFormation 스택을 배포합니다.

```bash
bash scripts/prereq.sh
```

이 스크립트는 S3 버킷을 생성하고 Lambda 코드를 패키징해 업로드한 다음, 모든 실습에서 사용할 기반 리소스를 프로비저닝하는 두 개의 CloudFormation 스택(인프라 및 Cognito)을 배포합니다.

### 종속성 설치 및 실습 1 시작

```bash
pip install -r requirements.txt
```

그런 다음 [실습 1](lab-01-create-an-agent.ipynb)을 열고 안내에 따라 진행하세요. 각 실습은 이전 실습의 내용을 기반으로 구성됩니다.

## 실습

| 실습 | 제목                                                                 | 노트북                                     | 시간    | 학습 내용                                                 |
| --- | -------------------------------------------------------------------- | ------------------------------------------ | ------- | --------------------------------------------------------- |
| 1   | [에이전트 프로토타입 만들기](#lab-1-create-agent-prototype)          | [노트북](lab-01-create-an-agent.ipynb)     | 약 20분 | Strands Agents를 활용한 에이전트 생성 및 도구 통합        |
| 2   | [Memory 추가하기](#lab-2-add-memory)                                 | [노트북](lab-02-agentcore-memory.ipynb)    | 약 20분 | 단기 및 장기 지속성을 위한 AgentCore Memory               |
| 3   | [Gateway와 Identity로 확장하기](#lab-3-scale-with-gateway--identity) | [노트북](lab-03-agentcore-gateway.ipynb)   | 약 30분 | 안전한 도구 공유를 위한 AgentCore Gateway와 Identity      |
| 4   | [프로덕션에 배포하기](#lab-4-deploy-to-production)                   | [노트북](lab-04-agentcore-runtime.ipynb)   | 약 30분 | 프로덕션 수준의 관찰 기능을 갖춘 AgentCore Runtime         |
| 5   | [에이전트 성능 평가하기](#lab-5-evaluate-agent-performance)          | [노트북](lab-05-agentcore-evals.ipynb)     | 약 10분 | 품질 모니터링을 위한 AgentCore Evaluations                |
| 6   | [고객 인터페이스 구축하기](#lab-6-build-customer-interface)          | [노트북](lab-06-frontend.ipynb)            | 약 20분 | 안전한 에이전트 엔드포인트와 프런트엔드 통합              |

<a id="lab-1-create-agent-prototype"></a>

### 실습 1: 에이전트 프로토타입 만들기

Strands Agents와 Amazon Nova 2 Lite를 사용해 다음 네 가지 핵심 도구를 갖춘 고객 지원 에이전트 프로토타입을 구축합니다.

- 제품 카테고리별 반품 정책을 조회합니다.
- 제품 정보와 사양을 검색합니다.
- 문제 해결에 도움이 되는 정보를 웹에서 검색합니다.
- 기술 지원 문서를 찾기 위해 Bedrock Knowledge Base를 쿼리합니다.

<a id="lab-2-add-memory"></a>

### 실습 2: Memory 추가하기

AgentCore Memory를 사용해 "금붕어 에이전트"를 여러 대화에 걸쳐 고객을 기억하는 에이전트로 전환합니다.

- 단기 기억으로 대화 기록을 지속적으로 저장합니다.
- 장기 기억으로 고객 선호도와 행동 패턴을 추출합니다.
- 여러 세션에 걸쳐 컨텍스트를 인식해 에이전트가 응답을 개인화할 수 있도록 합니다.

<a id="lab-3-scale-with-gateway--identity"></a>

### 실습 3: Gateway와 Identity로 확장하기

AgentCore Gateway와 AgentCore Identity를 사용해 로컬 도구를 공유 가능한 엔터프라이즈 수준의 서비스로 전환합니다.

- AgentCore Gateway를 통해 Lambda 함수를 MCP 호환 도구로 노출하여 도구 관리를 중앙화합니다.
- Amazon Cognito를 사용하는 JWT 기반 인증으로 Gateway 엔드포인트를 보호합니다.
- 도구 코드를 다시 작성하지 않고 기존 AWS Lambda 함수(보증 확인, 웹 검색)를 통합합니다.
- (선택 사항) AgentCore Policy에서 Cedar 정책으로 세분화된 액세스 제어를 정의하여 특정 도구 호출을 제한합니다.

<a id="lab-4-deploy-to-production"></a>

### 실습 4: 프로덕션에 배포하기

완전한 관찰 기능을 갖추고 실제 트래픽을 처리할 수 있도록 에이전트를 AgentCore Runtime에 배포합니다.

- 최소한의 코드 변경(단 네 줄 추가)으로 에이전트를 완전관리형 서버리스 Runtime에 배포합니다.
- 각 고객에게 별도의 대화 컨텍스트가 제공되도록 세션 연속성과 세션 격리를 활성화합니다.
- 자동 추적 및 지표를 제공하는 CloudWatch GenAI Observability를 통해 에이전트 동작을 모니터링합니다.

<a id="lab-5-evaluate-agent-performance"></a>

### 실습 5: 에이전트 성능 평가하기

AgentCore Evaluations를 사용해 프로덕션 에이전트를 위한 지속적인 품질 모니터링을 설정합니다.

- 목표 성공률, 정확성, 도구 선택 정확도를 측정하는 내장 평가기로 온라인 평가를 구성합니다.
- 테스트 상호 작용을 생성하고 AgentCore Observability 대시보드에서 평가 결과를 검토합니다.
- 품질 지표를 사용해 개선할 영역을 식별하고 높은 에이전트 성능을 유지합니다.

<a id="lab-6-build-customer-interface"></a>

### 실습 6: 고객 인터페이스 구축하기

고객이 배포된 에이전트와 상호 작용할 수 있는 Streamlit 웹 앱을 만듭니다.

- AgentCore Runtime 기반의 실시간 응답 스트리밍을 지원하는 채팅 인터페이스를 제공합니다.
- Amazon Cognito를 통해 안전한 사용자 인증을 구현합니다.
- AgentCore Memory를 통해 지속적인 대화 기록과 함께 사용자 세션을 관리합니다.

## 선택 실습

- [Identity 심층 학습](Optional-lab-identity.ipynb) -- OAuth2 3LO 흐름을 사용하는 AgentCore Identity를 통해 Google Calendar를 통합하여 에이전트가 인증된 사용자를 대신해 일정을 만들고 캘린더를 조회할 수 있도록 합니다.
- [Observability 심층 학습](Optional-lab-agentcore-observability.ipynb) -- AWS OpenTelemetry Python 계측과 CloudWatch GenAI Observability를 사용해 AgentCore Runtime 외부에서 실행되는 에이전트에 AgentCore Observability를 설정합니다.

## 정리

모든 실습을 마치면 [정리 노트북](lab-07-cleanup.ipynb)을 실행하여 워크숍 중에 생성한 모든 리소스를 삭제하세요.
