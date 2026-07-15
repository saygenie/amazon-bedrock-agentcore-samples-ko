# AgentCore Runtime의 Middleware 지원

## 개요

이 자습서에서는 Amazon Bedrock AgentCore Runtime에서 middleware를 구현하는 방법을 보여 줍니다. Middleware를 사용하면 요청이 에이전트에 도달하기 전과 응답이 클라이언트로 전송되기 전에 처리할 수 있습니다.

AgentCore Runtime은 Starlette의 ASGI middleware 시스템을 사용하므로 에이전트 코드를 수정하지 않고도 logging, 인증, header 조작 같은 공통 기능을 추가할 수 있습니다.

## 자습서 세부 정보

|정보| 세부 정보|
|:--------------------|:---------------------------------------------------------------------------------|
| 자습서 유형         | Middleware 구현|
| 에이전트 유형       | 단일           |
| 에이전틱 프레임워크 | Strands Agents |
| LLM 모델            | Anthropic Claude Haiku 4.5 |
| 자습서 구성 요소    | Middleware, 요청/응답 처리, AgentCore Runtime, Strands Agent 및 Amazon Bedrock 모델 |
| 자습서 분야         | 여러 산업 분야                                                                   |
| 예제 난이도         | 중급                                                                              |
| 사용 SDK            | Amazon BedrockAgentCore Python SDK 및 boto3|

## Middleware란?

Middleware는 애플리케이션을 감싸고 요청과 응답을 가로채는 ASGI 구성 요소입니다. 각 middleware는 다음 작업을 수행할 수 있습니다.

- 수신 요청 검사 또는 수정
- 에이전트 실행 전 로직 수행
- 발신 응답 검사 또는 수정
- Header, logging, metric 추가
- 인증 또는 rate limiting 처리

Middleware는 지정된 순서대로 위에서 아래로 평가되며 각 계층이 다음 계층을 감쌉니다.

## 작동 방식

BedrockAgentCoreApp은 초기화할 때 `middleware` 매개변수를 받습니다.

```python
from bedrock_agentcore import BedrockAgentCoreApp
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware

app = BedrockAgentCoreApp(
    middleware=[
        Middleware(CustomMiddleware),
    ]
)
```

각 middleware는 요청과 다음 계층을 호출하는 `call_next` 함수를 받는 비동기 `dispatch` 메서드를 구현합니다.

## 자습서 주요 기능

* **BaseHTTPMiddleware**: 요청/응답 인터페이스를 사용하는 middleware 작성
* **사용자 지정 Header**: 추적 및 디버깅 header 추가
* **요청 시간 측정**: 처리 소요 시간 측정
* **Logging**: 요청/응답 logging 중앙 집중화
* **Chaining**: 여러 middleware 구성 요소 쌓기
* **테스트**: TestClient를 사용한 로컬 테스트

## 사용 사례

- **Logging**: 요청/응답 시간과 metadata 추적
- **인증**: API key 또는 token 검증
- **Header**: 추적용 사용자 지정 header 추가
- **Metric**: 성능 데이터 수집
- **CORS**: Cross-origin 요청 처리
- **Rate Limiting**: 요청 빈도 제어
