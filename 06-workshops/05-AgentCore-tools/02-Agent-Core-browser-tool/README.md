# Amazon Bedrock AgentCore Browser Tool

## 개요

Amazon Bedrock AgentCore Browser Tool은 AI 에이전트가 사람처럼 웹사이트와 상호 작용할 수 있는 안전한 완전 관리형 방식을 제공합니다. 개발자가 사용자 지정 자동화 스크립트를 작성하고 유지 관리하지 않아도 에이전트가 웹 페이지를 탐색하고, 양식을 작성하고, 복잡한 작업을 완료할 수 있습니다.

## 작동 방식

Browser Tool 샌드박스는 AI 에이전트가 웹 브라우저와 안전하게 상호 작용할 수 있게 해 주는 보안 실행 환경입니다. 사용자가 요청하면 대규모 언어 모델(LLM)이 적절한 도구를 선택하고 명령으로 변환합니다. 이러한 명령은 헤드리스 브라우저와 호스팅된 라이브러리 서버를 포함하는 제어된 샌드박스 환경에서 Playwright 같은 도구를 사용해 실행됩니다. 샌드박스는 웹 상호 작용을 제한된 공간에 격리하여 무단 시스템 액세스를 방지하고 보안을 제공합니다. 에이전트는 스크린샷을 통해 피드백을 받아 시스템 보안을 유지하면서 자동화 작업을 수행할 수 있습니다. 이 구성으로 AI 에이전트의 안전한 웹 자동화가 가능합니다.

![로컬 아키텍처](images/browser-tool.png)

## 주요 기능

### 안전한 관리형 웹 상호 작용

AI 에이전트가 사람처럼 웹사이트와 상호 작용할 수 있는 안전한 완전 관리형 방식을 제공합니다. 사용자 지정 자동화 스크립트 없이 탐색, 양식 작성, 복잡한 작업 완료가 가능합니다.

### 엔터프라이즈 보안 기능

사용자 세션과 브라우저 세션을 1:1로 매핑하고 VM 수준에서 격리하여 엔터프라이즈급 보안을 제공합니다. 각 브라우저 세션은 엔터프라이즈 보안 요구 사항을 충족하도록 격리된 샌드박스 환경에서 실행됩니다.

### 모델 독립적 통합

다양한 AI 모델과 프레임워크를 지원하며, interact(), parse(), discover() 같은 도구를 통해 브라우저 작업을 자연어로 추상화하므로 엔터프라이즈 환경에 특히 적합합니다. 모든 라이브러리의 브라우저 명령을 실행할 수 있고 Playwright, Puppeteer 같은 다양한 자동화 프레임워크를 지원합니다.

### 통합

Amazon Bedrock AgentCore Browser Tool은 통합 SDK를 통해 다음과 같은 다른 Amazon Bedrock AgentCore 기능과 연동됩니다.

- Amazon Bedrock AgentCore Runtime
- Amazon Bedrock AgentCore Identity
- Amazon Bedrock AgentCore Memory
- Amazon Bedrock AgentCore Observability

이 통합은 개발 프로세스를 간소화하고, 강력한 브라우저 기반 작업 수행 기능을 바탕으로 AI 에이전트를 구축, 배포, 관리할 수 있는 종합 플랫폼을 제공하는 것을 목표로 합니다.

### 사용 사례

Amazon Bedrock AgentCore Browser Tool은 다음을 비롯한 다양한 애플리케이션에 적합합니다.

- 웹 탐색 및 상호 작용
- 양식 작성을 포함한 워크플로 자동화

## 튜토리얼 개요

이 튜토리얼에서는 다양한 프레임워크와 구성에서 Amazon Bedrock AgentCore Browser Tool의 기능을 살펴봅니다.

### 시작하기

**Browser Use 예제**
- [Amazon Bedrock AgentCore Browser Tool 및 Browser Use 시작하기](02-browser-with-browserUse/getting_started-agentcore-browser-tool-with-browser-use.ipynb)
- [Amazon Bedrock AgentCore Browser Tool Live View 및 Browser Use](02-browser-with-browserUse/agentcore-browser-tool-live-view-with-browser-use.ipynb)

**Nova Act 예제**
- [Amazon Bedrock AgentCore Browser Tool 및 Nova Act 시작하기](01-browser-with-NovaAct/01_getting_started-agentcore-browser-tool-with-nova-act.ipynb)
- [Amazon Bedrock AgentCore Browser Tool Live View 및 Nova Act](01-browser-with-NovaAct/02_agentcore-browser-tool-live-view-with-nova-act.ipynb)

**Strands 예제**
- [Amazon Bedrock AgentCore Browser Tool 및 Strands 시작하기](04-browser-with-Strands/01_getting_started-agentcore-browser-tool-with-strands.ipynb)

### 고급 기능

**Observability**
- [Amazon Bedrock AgentCore Browser Tool Observability 살펴보기](03-browser-observability/01_browser_observability.ipynb)

**Live View**
- [Amazon Bedrock AgentCore Browser Tool DCV Live View 살펴보기](05-browser-live-view/01-embed-dcv-live-view-tutorial.ipynb)

**웹 봇 인증**
- [Amazon Bedrock AgentCore Browser Tool Web Bot Auth 살펴보기](06-Web-Bot-Auth-Signing/01_agentcore-browser-tool-with-web-bot-auth.ipynb)

### VPC 통합

**VPC 구성**
- [프라이빗 VPC에서 퍼블릭 Browser 연결하기](07-connecting-public-browser-from-private-vpc/01-connecting-public-browser-from-private-vpc-runtime.ipynb)
- [VPC에서 VPC 기반 Browser와 상호 작용하기](08-Interacting-with-vpc-based-browser-from-vpc/01-Interacting-with-vpc-based-browser-from-vpc.ipynb)

### 보안 및 구성

**도메인 필터링**
- [AWS Network Firewall을 사용한 Browser 도메인 필터링](09-browser-with-domain-filtering/) - 허용 목록/차단 목록 기반 도메인 필터링을 위해 Network Firewall이 있는 VPC에 AgentCore Browser 배포

**프록시 라우팅**
- [Squid 프록시를 사용하는 Browser](11-browser-with-proxy/) - 인증된 Squid 프록시를 통해 브라우저 트래픽을 라우팅하고 액세스 로그를 Amazon S3로 전송

**Browser 프로필**
- [영구 프로필을 사용하는 Browser](10-browser-with-profile/browser-profile.ipynb) - 여러 세션에서 브라우저 세션 데이터(쿠키, 로컬 스토리지)를 유지하고 재사용
