# AgentCore Harness 시작하기

이 폴더에는 Amazon Bedrock AgentCore Harness 입문 튜토리얼이 있습니다.

## AgentCore Harness란?

AgentCore Harness를 사용하면 프레임워크 설정, 오케스트레이션 코드 작성, 배포 과정을 거치지 않고 한 번의 API 호출로 에이전트를 정의하고 실행할 수 있어 더 빠르게 에이전트를 실험하고 출시할 수 있습니다. 개발자는 한 번의 API 호출에 모델, 시스템 프롬프트, 도구를 지정합니다.

## 시작 가이드

### AgentCore CLI 사용

Markdown 파일 [CLI](CLI.md)에는 AgentCore CLI를 사용해 AgentCore Harness 워크플로를 실습하는 전체 과정이 담겨 있습니다.

**학습 내용:**
1. Bedrock 모델 공급자를 사용해 에이전트 생성 및 호출
2. OpenAI 모델 공급자를 사용해 에이전트 생성 및 호출

### Jupyter 노트북과 Boto3로 시작하기

Jupyter 노트북 [01_getting_started_bedrock.ipynb](01_getting_started_bedrock.ipynb)에는 핵심 AgentCore Harness 워크플로를 실습하는 전체 과정이 담겨 있습니다.

**학습 내용:**
1. 필요한 권한이 있는 IAM 실행 역할 생성
2. AgentCore Harness 에이전트 생성
3. 프롬프트로 에이전트 호출
4. 에이전트의 격리된 microVM에서 셸 명령 실행
5. 리소스 정리

## 중요 사항

- 각 AgentCore Harness 세션은 격리된 Firecracker microVM에서 실행됩니다.
- 에이전트의 VM에서 셸 명령을 실행하려면 `execute_command`를 사용하세요. 로컬 `!` 명령은 사용하지 마세요.
- 에이전트에서는 기본적으로 `file_operations` 및 `shell` 도구를 사용할 수 있습니다.
- 세션은 고유한 `session_id`로 식별됩니다.

## 다음 단계

이 튜토리얼을 완료한 후 다음 내용을 살펴보세요.
- [**01-advanced-examples/**](../01-advanced-examples/) — 사용자 지정 컨테이너, CLI 스크립트, 고급 패턴
- [**02-use-cases/**](../02-use-cases/) — 여행 에이전트, 웹 애플리케이션 테스트 등의 실제 애플리케이션
