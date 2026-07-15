# Amazon Bedrock AgentCore Code Interpreter

## 개요
Amazon Bedrock AgentCore Code Interpreter는 AI 에이전트가 코드를 직접 작성하고 실행하여 엔드 투 엔드 작업을 완료할 수 있는 안전한 서버리스 환경입니다. 이를 통해 복잡한 데이터 분석, 시뮬레이션 실행, 시각화 생성, 프로그래밍 작업 자동화를 수행할 수 있습니다.

## 작동 방식

코드 실행 샌드박스는 Code Interpreter, 셸, 파일 시스템을 갖춘 격리 환경을 생성하여 에이전트가 사용자 쿼리를 안전하게 처리하도록 지원합니다. 대규모 언어 모델이 도구 선택을 지원한 후 이 세션 안에서 코드가 실행되며, 그 결과는 종합을 위해 사용자 또는 에이전트에게 반환됩니다.

![로컬 아키텍처](../01-Agent-Core-code-interpreter/images/code-interpreter.png)

## 주요 기능

### 환경 내 세션

여러 실행에 걸쳐 세션을 유지할 수 있습니다.

### VPC 지원 및 인터넷 액세스

VPC 연결과 외부 인터넷 액세스를 비롯한 엔터프라이즈급 기능을 제공합니다.

### 다양한 사전 구축 환경 런타임

Python, NodeJS, TypeScript를 비롯한 다양한 사전 구축 런타임을 제공합니다(사용자 지정 라이브러리를 포함하는 사용자 지정 런타임 코드 실행 엔진 지원 예정).

### 통합

Amazon Bedrock AgentCore Code Interpreter는 통합 SDK를 통해 다음과 같은 다른 Amazon Bedrock AgentCore 기능과 연동됩니다.

- Amazon Bedrock AgentCore Runtime
- Amazon Bedrock AgentCore Identity
- Amazon Bedrock AgentCore Memory
- Amazon Bedrock AgentCore Observability

이 통합은 개발 프로세스를 간소화하고, 강력한 코드 실행 기능을 바탕으로 AI 에이전트를 구축, 배포, 관리할 수 있는 종합 플랫폼을 제공하는 것을 목표로 합니다.

### 사용 사례

Amazon Bedrock AgentCore Code Interpreter는 다음을 비롯한 다양한 애플리케이션에 적합합니다.

- 코드 실행 및 검토
- 데이터 분석 및 시각화

## 튜토리얼 개요

이 튜토리얼에서는 다음 기능을 다룹니다.

- [Amazon Bedrock AgentCore Code Interpreter를 사용한 파일 작업](01-file-operations-using-code-interpreter)
- [Amazon Bedrock AgentCore Code Interpreter를 사용하는 에이전트의 코드 실행](02-code-execution-with-agent-using-code-interpreter)
- [Amazon Bedrock AgentCore Code Interpreter를 사용하는 AI 에이전트의 고급 데이터 분석](03-advanced-data-analysis-with-agent-using-code-interpreter)
- [Amazon Bedrock AgentCore Code Interpreter를 사용한 명령 실행](04-run-commands-using-code-interpreter)
