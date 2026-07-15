# MCP 서버 메타데이터를 AWS Agent Registry에 동기화

## 개요

이 튜토리얼에서는 AWS Agent Registry의 URL 기반 동기화를 사용하여 외부 호스팅 MCP 서버와 AgentCore Runtime 호스팅 MCP 서버에서 MCP 서버 메타데이터(서버 스키마, 도구, 설명 및 버전)를 자동으로 추출하고 등록하는 방법을 보여 줍니다.

도구 스키마를 수동으로 정의하는 대신 MCP 서버 URL을 제공하면 레지스트리가 서버에 연결하여 기능을 검색하고 추출한 메타데이터로 레지스트리 레코드를 생성합니다.

## 시작하기

이 튜토리얼을 시작하려면 Jupyter 노트북을 열고 단계별 가이드를 따르세요.

**[📓 registry_synchronize_mcpserver.ipynb](registry_synchronize_mcpserver.ipynb)**

노트북에는 이 튜토리얼을 완료하는 데 필요한 모든 코드 예제, 구성 및 자세한 지침이 포함되어 있습니다.

## 학습 내용

* 사용 가능한 레지스트리를 나열하고 IAM 권한 부여를 사용하는 새 레지스트리를 생성하는 방법
* **보호되지 않는 퍼블릭** MCP 서버를 레지스트리에 동기화하는 방법
* AgentCore Runtime에 배포된 **OAuth 보호** MCP 서버를 동기화하는 방법
* AgentCore Runtime에 배포된 **IAM 보호** MCP 서버를 동기화하는 방법
                             |
### 튜토리얼 아키텍처

아래 다이어그램은 AWS Agent Registry가 OAuth 보호 및 IAM 보호 MCP 서버의 메타데이터를 동기화하는 방식을 보여 줍니다.

![Agent Registry의 MCP 서버 동기화 아키텍처](registry-synchronize-mcpserver-arch.png)

동기화 후 레코드는 CREATING 상태로 생성됩니다. 약 10초 후 레코드가 DRAFT 상태로 전환되며, 서버 설명자와 도구 설명자를 비롯해 MCP 서버에서 추출한 설명자가 포함됩니다. MCP 서버에 연결할 때 이러한 값을 찾으면 레지스트리에서 레코드 이름, 설명 및 버전도 업데이트합니다.

### 튜토리얼 주요 기능

* URL 기반 동기화(풀 기반 메타데이터 추출)
* 퍼블릭 MCP 서버 동기화
* Cognito를 사용한 OAuth 보호 MCP 서버 동기화
* 역할 기반 액세스를 사용한 IAM 보호 MCP 서버 동기화

## 사전 요구 사항

- AWS Agent Registry, AgentCore Runtime, Cognito 및 IAM 역할 관리 권한이 있는 IAM 자격 증명을 갖춘 AWS 계정
- boto3 >= 1.42.87(`bedrock-agentcore-control` 서비스 지원 포함)이 설치된 Python 3.10+
- 적절한 프로파일로 구성된 AWS CLI v2
- AgentCore Runtime에 MCP 서버를 배포하기 위한 `bedrock-agentcore-starter-toolkit`

## 노트북 섹션

| 섹션 | 수행 작업 |
|---------|--------------|
| 설정 | 종속성을 설치하고 AWS 세션과 클라이언트를 초기화하며 비동기 작업을 기다리는 헬퍼 함수를 생성합니다. |
| 1. 레지스트리 나열 | 계정에서 사용 가능한 모든 레지스트리를 나열합니다. |
| 2. 레지스트리 생성 | IAM 권한 부여와 `autoApproval: False`를 사용하는 새 레지스트리를 생성합니다. |
| 3. 퍼블릭 MCP 서버에서 동기화 | URL 기반 동기화를 사용하여 보호되지 않는 퍼블릭 MCP 서버(예: AWS Knowledge MCP Server)의 메타데이터를 동기화합니다. |
| 4. OAuth 보호 MCP 서버에서 동기화 | Cognito 사용자 풀과 OAuth 공급자를 생성하고 JWT 권한 부여를 사용하는 MCP 서버를 AgentCore Runtime에 배포한 후 OAuth 자격 증명을 사용하여 동기화합니다. |
| 5. IAM 보호 MCP 서버에서 동기화 | 기본 IAM 인증을 사용하는 MCP 서버를 AgentCore Runtime에 배포하고 레지스트리에서 Runtime을 호출하기 위한 IAM 역할을 생성한 후 IAM 자격 증명을 사용하여 동기화합니다. |
| 6. 모든 레코드 나열 | 레지스트리에서 동기화된 모든 레코드를 나열합니다. |
| 7. 정리 | 레지스트리 레코드, 레지스트리, Runtime, OAuth 공급자, Cognito 리소스, IAM 역할 및 로컬 파일 등 생성한 모든 리소스를 삭제합니다. |

## 사용되는 AWS 서비스

| 서비스 | 용도 |
|---------|---------|
| **AWS Agent Registry** | 추출한 도구 스키마 및 메타데이터와 함께 MCP 서버 레코드를 저장합니다. |
| **AgentCore Runtime** | OAuth 또는 IAM 인증을 사용하는 MCP 서버를 호스팅합니다. |
| **Amazon Cognito** | MCP 서버 액세스를 위한 OAuth2 인증(클라이언트 자격 증명 흐름)을 제공합니다. |
| **IAM** | 레지스트리에서 Runtime을 호출하기 위한 역할 기반 액세스를 제공합니다. |

## 정리

노트북에는 튜토리얼에서 생성한 모든 리소스를 제거하는 정리 섹션(섹션 7)이 포함되어 있습니다.

- 레지스트리 레코드 및 레지스트리
- AgentCore Runtime 배포
- OAuth2 자격 증명 공급자
- Cognito 사용자 풀 및 도메인
- IAM 역할 및 정책
- `%%writefile`로 생성된 로컬 파일

지속적인 요금 발생을 방지하려면 정리 셀을 실행하세요.
