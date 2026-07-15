# AWS re:Invent 2025 AIML301: Bedrock AgentCore를 사용한 End-to-End SRE 사용 사례 구축

## 개요

이 워크숍에서는 Site Reliability Engineer(SRE)가 Amazon Bedrock AgentCore를 활용하여 진단부터 해결 및 예방에 이르는 incident response를 자동화하는 방법을 보여줍니다.

**워크숍 시나리오:** AWS(EC2 + NGINX + DynamoDB)에 배포된 CRM 애플리케이션에 장애가 발생합니다. 문제를 진단하고 approval workflow를 통해 안전하게 해결하며 조사 및 모범 사례를 활용해 재발을 방지하는 multi-agent 시스템을 구축합니다.

## 학습 목표

이 워크숍을 완료하면 다음을 수행할 수 있습니다.

1. **Lab 1** - 사전 요구 사항을 확인하고 fault injection 기능을 갖춘 현실적인 CRM 애플리케이션 스택 설정
2. **Lab 2** - CloudWatch 로그 및 메트릭을 분석하는 진단 에이전트 구축
3. **Lab 3a** - approval workflow와 Code Interpreter를 사용하는 해결 에이전트 생성
4. **Lab 3b** - custom Lambda interceptor를 사용한 fine-grained access control 구현
5. **Lab 4** - 조사에 AgentCore Browser를 사용하는 예방 에이전트 구현
6. **Lab 5** - AgentCore Gateway 및 대화형 Streamlit UI와 supervisor pattern을 사용해 모든 에이전트 오케스트레이션

## 빠른 시작

### 권장 실습 흐름

```
Lab-01 (Prerequisites & Infrastructure)
   ↓
Lab-02 (Diagnostics Agent)
   ↓
Lab-03a (Remediation Agent)
   ↓
Lab-03b (Fine-Grained Access Control)
   ↓
Lab-04 (Prevention Agent)
   ↓
Lab-05 (Multi-Agent Orchestration + Streamlit UI)
```

### 시작하기

1. 로컬 시스템에 **워크숍을 다운로드**합니다.
2. 워크숍 디렉터리에서 **Jupyter Notebook/Lab을 엽니다**.
3. **`Lab-01-prerequisites-infra.ipynb`부터 시작**하여 모든 섹션을 실행합니다.
4. Lab-05까지 **실습을 순서대로 진행**합니다.
5. 완료하면 Lab-05의 cleanup 셀을 사용해 **리소스를 정리**합니다.

**⏱️ 예상 시간:**
- 전체 워크숍(Lab 1-5): **2시간**

**✨ 모든 작업은 노트북 안에서 이루어지므로 터미널 명령이 필요하지 않습니다!**

## 작동 방식

### 모든 작업이 노트북에서 실행

- 노트북을 열고 위에서 아래로 실행합니다.
- 모든 설정, 구성 및 프로비저닝이 자동으로 이루어집니다.
- 터미널 명령이 필요하지 않습니다.
- 각 노트북은 독립적으로 구성됩니다.
- 필요에 따라 노트북에서 helper와 utility를 import합니다.

**노트북에서 이루어지는 작업 예시:**
1. `pip install`을 통해 필요한 Python 패키지 설치
2. AWS 자격 증명 및 환경 구성
3. 사전 요구 사항 확인
4. AWS 리소스(EC2, DynamoDB, Lambda 등) 프로비저닝
5. 에이전트 구현 및 테스트
6. 테스트를 위한 장애 주입
7. 진단, 해결 또는 예방 워크플로 실행
8. CloudWatch를 통해 결과 모니터링
9. 완료 후 리소스 정리

## 아키텍처

이 워크숍에서는 incident response 자동화를 위한 multi-agent 시스템을 구현합니다.

![아키텍처 다이어그램](architecture/architecture.png)

**주요 구성 요소:**

1. **CRM 애플리케이션 스택**
   - NGINX 웹 서버를 실행하는 EC2 인스턴스
   - 데이터 영속성을 위한 DynamoDB
   - 로그 및 메트릭을 위한 CloudWatch

2. **에이전트 시스템**
   - **진단 에이전트**: CloudWatch 로그 및 메트릭을 분석하여 문제 식별
   - **해결 에이전트**: approval workflow와 함께 Code Interpreter를 사용해 수정 실행
   - **예방 에이전트**: AgentCore Browser 도구를 사용해 모범 사례 조사
   - **Supervisor Agent**: 모든 에이전트를 오케스트레이션하고 워크플로 관리

3. **AgentCore 플랫폼**
   - **AgentCore Runtime**: 에이전트용 serverless 배포
   - **AgentCore Gateway**: JWT 인증을 사용하는 도구 오케스트레이션용 MCP 프로토콜
   - **AgentCore Code Interpreter**: 해결 스크립트를 위한 안전한 실행 환경
   - **AgentCore Browser**: 예방을 위한 웹 조사 기능
   - **AgentCore Memory**: 상호 작용 간 컨텍스트 영속성

4. **보안 및 액세스 제어**
   - 사용자 인증을 위한 Cognito
   - agent-to-agent 통신을 위한 OAuth2 M2M
   - 세분화된 RBAC를 위한 Lambda interceptor
   - JWT 기반 권한 부여

5. **사용자 인터페이스**
   - 대화형 에이전트 상호 작용을 위한 Streamlit 웹 앱
   - 실시간 streaming 응답
   - Approval workflow 통합

## 데모 동영상

전체 워크숍 진행 과정을 확인하세요.

![워크숍 데모](demo/aim301-multi-agent-mcp-agentcore-gateway.gif)

데모에서는 다음 내용을 보여줍니다.
- CRM 애플리케이션 인프라 설정
- 실제 incident를 시뮬레이션하기 위한 장애 주입
- 문제 식별을 위한 진단 실행
- approval workflow를 통한 해결 수행
- 예방 전략 조사
- Streamlit UI를 통한 모든 에이전트 오케스트레이션

## 워크숍 구조

```
├── Lab-01-prerequisites-infra.ipynb             # Lab 1: 사전 요구 사항 및 인프라 설정
├── Lab-02-diagnostics-agent.ipynb               # Lab 2: 진단 Agent
├── Lab-03a-remediation-agent.ipynb              # Lab 3a: 복구 Agent + 승인
├── Lab-03b-remediation-agent-fgac.ipynb         # Lab 3b: 세분화된 접근 제어
├── Lab-04-prevention-agent.ipynb                # Lab 4: 예방 Agent
├── Lab-05-multi-agent-orchestration.ipynb       # Lab 5: Multi-Agent 오케스트레이션 + Streamlit
│
├── lab_helpers/                        # Notebook에서 import하는 helper module
│   ├── lab_01/                        # Lab 1 전용 helper
│   ├── lab_02/                        # Lab 2 전용 helper
│   ├── lab_03/                        # Lab 3 전용 helper
│   ├── lab_04/                        # Lab 4 전용 helper
│   ├── lab_05/                        # Lab 5 전용 helper(streamlit_app.py 포함)
│   ├── constants.py                   # 구성 상수
│   ├── parameter_store.py             # AWS Parameter Store 유틸리티
│   └── ...                            # 기타 공유 utility
├── requirements.txt                    # Python 의존성
└── README.md                           # 이 파일
```

## 사전 요구 사항

시작하기 전에 다음 항목을 준비하세요.

- Python 3.10 이상
- Jupyter Notebook 또는 JupyterLab 설치
- EC2, DynamoDB, Lambda, CloudWatch, Bedrock 권한이 있는 AWS 계정
- 로컬에 구성된 AWS 자격 증명(또는 Lab 1에서 설정)

`Lab-01-prerequisites-infra.ipynb` 노트북에서 이러한 항목을 모두 확인하고 누락된 종속성을 설치합니다.

## 실습 개요

**Lab 1: 사전 요구 사항 및 인프라 설정**
- Python 버전, AWS 자격 증명 및 종속성 확인
- 워크숍 요구 사항 설치 및 Bedrock 액세스 확인
- CRM 애플리케이션 배포(EC2 + NGINX + DynamoDB)
- 인증용 Cognito 설정
- CloudWatch 모니터링 설정
- fault injection utility 생성

**Lab 2: 진단 에이전트**
- CloudWatch 로그를 분석하는 Strands Agent 구축
- 진단 도구가 포함된 Lambda 함수 배포
- MCP 프로토콜을 사용하는 AgentCore Gateway 생성
- 실제 애플리케이션 로그를 대상으로 에이전트 테스트

**Lab 3a: Code Interpreter를 사용하는 해결 에이전트**
- 에이전트를 AgentCore Runtime에 배포
- 안전한 실행을 위해 AgentCore Code Interpreter 통합
- OAuth2 M2M 인증 구현
- 해결 워크플로 테스트

**Lab 3b: Fine-Grained Access Control**
- 요청 권한 부여용 Lambda interceptor 생성
- role-based access control(RBAC) 구현
- Cognito group 구성(Approvers와 SRE)
- 서로 다른 사용자 역할로 액세스 제어 테스트

**Lab 4: AgentCore Browser를 사용하는 예방 에이전트**
- AgentCore Browser 도구가 포함된 Runtime 에이전트 배포
- AWS 문서 및 모범 사례 조사
- 예방 playbook 생성
- OAuth2 M2M 인증

**Lab 5: Streamlit을 사용한 Multi-Agent Orchestration**
- 세 에이전트를 모두 조정하는 supervisor agent 생성
- JWT 인증을 사용하는 중앙 AgentCore Gateway 설정
- RBAC에 Lab 3b interceptor 재사용
- multi-agent 시스템 배포
- 실시간 streaming이 포함된 대화형 Streamlit 채팅 인터페이스 시작
- end-to-end incident response 워크플로 테스트

## 주요 기술

- **Amazon Bedrock** - 기반 모델(Claude 3.7 Sonnet)
- **AgentCore** - Serverless 에이전트 플랫폼
  - AgentCore Runtime(배포)
  - AgentCore Memory(컨텍스트 영속성)
  - AgentCore Gateway(JWT 인증을 사용하는 도구 오케스트레이션)
  - AgentCore Code Interpreter(해결 작업 실행)
  - AgentCore Browser(조사 및 문서)
  - AgentCore Observability(모니터링 및 tracing)
- **Strands Framework** - streaming을 지원하는 도구 사용 패턴용 에이전트 프레임워크
- **Streamlit** - 실시간 에이전트 상호 작용을 위한 대화형 웹 UI
- **AWS 서비스** - EC2, DynamoDB, CloudWatch, Lambda, IAM, Cognito, Bedrock
- **Jupyter Notebooks** - 대화형 학습 환경

## 프로젝트 파일

### 실습 Helper(`lab_helpers/`)
노트북에서 코드를 간결하게 유지하기 위해 import하는 Python 모듈입니다.
- `lab_01/` - 인프라 배포 및 fault injection
- `lab_02/` - Lambda 배포, MCP client, Gateway 설정
- `lab_03/` - Runtime 배포, OAuth2 설정, interceptor
- `lab_04/` - Runtime 배포, Gateway 설정, 로깅
- `lab_05/` - Supervisor agent 코드, Streamlit 앱, IAM 설정
- `constants.py` - 구성 상수 및 파라미터 경로
- `parameter_store.py` - AWS Parameter Store 유틸리티
- `config.py` - 워크숍 구성
- `cognito_setup.py` - Cognito User Pool 및 client 설정
- `short_term_memory.py` - AgentCore Memory 통합

## 문제 해결

**문제가 발생한 경우:**
1. 노트북 출력에서 오류 메시지를 확인합니다.
2. 오류 출력에서 AWS 자격 증명을 확인합니다.
3. 올바른 AWS 리전을 사용하고 있는지 확인합니다.
4. 노트북에서 직접 CloudWatch 로그를 검토합니다.
5. 사전 요구 사항 확인을 다시 실행합니다.

**일반적인 문제:**
- AWS 자격 증명 누락 → `Lab-01-prerequisites-infra.ipynb`를 다시 실행
- Bedrock 모델에 액세스할 수 없음 → 해당 리전에서 Bedrock이 활성화되어 있는지 확인
- Lambda timeout → 노트북에서 CloudWatch 로그 확인
- 리소스가 이미 존재함 → cleanup 노트북을 실행하고 다시 시도

## 워크숍 이후

학습한 내용을 적용하려면 다음을 진행하세요.

1. **자체 환경:**
   - 모니터링 시스템에 맞게 에이전트 조정
   - 배포 pipeline과 통합
   - incident management 플랫폼에 연결

2. **프로덕션 사용:**
   - AgentCore Runtime에 에이전트 배포
   - incident 이력을 위한 persistent memory 설정
   - observability 및 alerting 활성화
   - 팀 approval workflow 수립

3. **고급 기능:**
   - Multi-team orchestration
   - 교차 계정 incident response
   - custom 도구 개발
   - 서드 파티 통합

## 리소스

- [Amazon Bedrock 문서](https://docs.aws.amazon.com/bedrock/)
- [AgentCore 문서](https://docs.aws.amazon.com/agentcore/)
- [Strands Framework GitHub](https://github.com/aws-samples/strands-agents)
- [AWS re:Invent 2025](https://reinvent.awsevents.com/)

## 라이선스

이 워크숍은 MIT License에 따라 있는 그대로 제공됩니다.
