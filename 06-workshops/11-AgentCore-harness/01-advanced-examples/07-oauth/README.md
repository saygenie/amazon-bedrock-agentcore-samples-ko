# OAuth 인바운드 인증 및 OAuth로 보호되는 Gateway를 사용하는 AgentCore Harness

이 샘플은 AgentCore Harness와 OAuth의 엔드 투 엔드 통합을 보여 줍니다.

- **인바운드 인증**: 사용자가 Cognito JWT (USER_PASSWORD_AUTH)를 통해 AgentCore Harness에 인증
- **아웃바운드 인증**: AgentCore Harness가 Cognito M2M(클라이언트 자격 증명 흐름)을 통해 AgentCore Gateway에 인증
- **Gateway 대상**: AgentCore Gateway를 통해 공개되는 Lambda 함수

전체 AgentCore Harness 문서는 [AgentCore Harness 개발자 가이드](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html)를 참조하세요.

## 아키텍처

<img src="images/architecture.jpg" alt="아키텍처" width="800"/>

## 학습 내용

- AgentCore Harness에 `CUSTOM_JWT` 인바운드 인증 구성(모든 OIDC 공급자 지원)
- Gateway 도구에 `outboundAuth.oauth` 구성(클라이언트 자격 증명 권한 부여)
- AgentCore Identity에 OAuth2 자격 증명 공급자 설정
- JWT 인바운드 인증과 Lambda 대상이 있는 AgentCore Gateway 생성
- 전달자 토큰으로 AgentCore Harness 호출(Secret은 Token Vault 외부로 노출되지 않음)

## 프로젝트 구조

```
├── harness_oauth_gateway.ipynb   ← main notebook
├── utils/
│   ├── setup_helpers.py          ← idempotent infra setup & cleanup
│   └── lambda_function_code.py   ← order management Lambda handler
├── images/
│   └── architecture.jpg          ← architecture diagram
├── requirements.txt
└── README.md
```

## 사전 요구 사항

- Bedrock AgentCore에 액세스할 수 있는 AWS 계정
- 구성된 AWS 자격 증명(`aws configure` 또는 환경 변수)
- Python 3.10+, `boto3 >= 1.42.80`, `requests`, `jupyter`
- 활성화된 Bedrock 모델 액세스

## 실행 방법

```bash
pip install -r requirements.txt
jupyter notebook harness_oauth_gateway.ipynb
```

셀을 위에서 아래로 실행하세요. 사용자 자격 증명은 `getpass`를 통해 입력하므로 노트북에 표시되지 않습니다. 모든 셀은 멱등성을 가지므로 안전하게 다시 실행할 수 있습니다.

## 정리

노트북의 마지막 셀은 모든 리소스를 삭제합니다. 이름으로 리소스를 검색하고 리소스가 없으면 문제없이 건너뛰므로 커널을 다시 시작한 후에도 사용할 수 있습니다.
