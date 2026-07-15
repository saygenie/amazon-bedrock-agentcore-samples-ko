# Amazon Bedrock AgentCore Tools

## 개요
Amazon Bedrock AgentCore Tools는 AI 에이전트가 복잡한 작업을 안전하고 효율적으로 수행할 수 있도록 엔터프라이즈급 기능을 제공합니다. 이 도구 모음에는 다음이 포함됩니다.

- Amazon Bedrock AgentCore Code Interpreter
- Amazon Bedrock AgentCore Browser Tool

## Amazon Bedrock AgentCore Code Interpreter

### 주요 기능

1. **안전한 코드 실행**: 격리된 샌드박스 환경에서 코드를 실행하여 내부 데이터 소스에 액세스할 때도 보안을 유지합니다.

2. **완전 관리형 AWS 네이티브 솔루션**: Strands Agents, LangGraph, CrewAI 같은 프레임워크와 원활하게 통합됩니다.

3. **고급 구성 지원**: 입력 및 출력용 대용량 파일과 인터넷 액세스를 지원합니다.

4. **다양한 언어 지원**: JavaScript, TypeScript, Python을 비롯한 여러 프로그래밍 언어용 사전 구축 런타임 모드를 제공합니다.

### 이점

- **향상된 에이전트 정확도**: 에이전트가 복잡한 계산과 데이터 처리를 수행할 수 있습니다.
- **엔터프라이즈급 보안**: 격리된 환경을 통해 엄격한 보안 요구 사항을 충족합니다.
- **효율적인 데이터 처리**: Amazon S3의 파일을 참조하여 기가바이트 규모의 데이터를 처리할 수 있습니다.

## Amazon Bedrock AgentCore Browser Tool

### 주요 기능

1. **모델 독립적 유연성**: Anthropic Claude, OpenAI 모델, Amazon Nova 모델 등 다양한 AI 모델의 명령 구문을 지원합니다.

2. **엔터프라이즈급 보안**: VM 수준 격리, VPC 연결, 엔터프라이즈 SSO 시스템 통합을 제공합니다.

3. **포괄적인 감사 기능**: 모든 브라우저 명령에 대한 CloudTrail 로깅과 세션 녹화 기능을 제공합니다.

### 이점

- **엔드 투 엔드 자동화**: 이전에는 수동 개입이 필요했던 복잡한 웹 워크플로를 AI 에이전트가 자동화할 수 있습니다.
- **강화된 보안**: 폭넓은 보안 및 감사 기능으로 엔터프라이즈 요구 사항을 충족합니다.
- **실시간 모니터링**: 즉시 개입할 수 있는 Live View와 디버깅 및 감사를 위한 Session Replay를 제공합니다.

## 사용 사례

- 안전한 환경에서 복잡한 데이터 분석 및 시각화
- 양식 작성, 데이터 추출, 다단계 프로세스를 위한 웹 상호 작용 자동화
- 대규모 데이터 처리 및 모니터링
- 엔터프라이즈 환경에서 AI 에이전트를 위한 안전한 코드 실행

## 튜토리얼 개요

1. [Amazon Bedrock AgentCore Code Interpreter](01-Agent-Core-code-interpreter)
2. [Amazon Bedrock AgentCore Browser Tool](02-Agent-Core-browser-tool)
