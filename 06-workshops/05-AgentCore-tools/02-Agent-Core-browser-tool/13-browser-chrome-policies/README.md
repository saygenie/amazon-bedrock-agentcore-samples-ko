# Chrome 엔터프라이즈 정책과 사용자 지정 루트 CA를 사용하는 AgentCore Browser

이 예제에서는 Amazon Bedrock AgentCore Browser 및 Code Interpreter에서 [Chrome 엔터프라이즈 정책](https://chromeenterprise.google/policies/)과 사용자 지정 루트 CA 인증서를 사용하는 방법을 살펴봅니다.

## 개요

Chrome 엔터프라이즈 정책을 사용하면 다음 작업을 수행할 수 있습니다.
- **에이전트 탐색 제한**: 에이전트가 탐색할 수 있는 위치를 제한하는 URL 허용 목록과 차단 목록 정의
- **위험한 기능 비활성화**: 암호 관리자 끄기, 다운로드 차단, DevTools 비활성화
- **규정 준수 적용**: 세션에서 재정의할 수 없는 관리형 정책을 브라우저 수준에 적용

사용자 지정 루트 CA 인증서를 사용하면 다음 작업을 수행할 수 있습니다.
- **내부 서비스에 연결**: 조직의 프라이빗 CA에서 서명한 인증서 신뢰(Jira, Artifactory, HR 포털)
- **기업 프록시 사용**: SSL을 가로채는 프록시의 루트 CA 신뢰(Zscaler, Palo Alto Networks)

## 사용 사례

- 데이터 입력 에이전트가 특정 기업 포털에만 액세스하도록 제한
- 에이전트가 자격 증명을 저장하거나 파일을 다운로드하지 못하도록 방지
- 에이전트가 프라이빗 PKI를 사용하는 내부 인프라에 연결하도록 지원
- SSL을 가로채는 기업 프록시를 통해 에이전트 트래픽 라우팅

## 시작하기

### 사전 요구 사항

- Python 3.10 이상
- Amazon Bedrock AgentCore 액세스가 활성화된 AWS 계정
- 구성된 AWS 자격 증명(`aws sts get-caller-identity`)
- Amazon Bedrock AgentCore를 사용할 수 있는 AWS 리전

> **참고:** 노트북에서 필요한 모든 리소스(Amazon S3 버킷, IAM 역할, AgentCore Browser, Code Interpreter)를 자동으로 생성합니다. 리소스를 미리 생성할 필요는 없습니다.

### 설치

```bash
pip install -r requirements.txt
```

### 실행

```bash
jupyter notebook browser-chrome-policies.ipynb
```

셀을 순서대로 실행합니다. 파트 1에서는 Chrome 엔터프라이즈 정책을, 파트 2에서는 사용자 지정 루트 CA 인증서를 다룹니다.

## 노트북 둘러보기

[browser-chrome-policies.ipynb 노트북](browser-chrome-policies.ipynb)에서는 다음 내용을 살펴봅니다.

### 설정

- 정책 파일과 세션 녹화물을 저장할 Amazon S3 버킷 생성
- `bedrock-agentcore.amazonaws.com`에 대한 신뢰 정책과 Amazon S3 권한이 있는 IAM 실행 역할 생성

### 파트 1: Chrome 엔터프라이즈 정책

1. **Chrome 정책 생성**: AWS 문서를 제외한 모든 URL을 차단하고 위험한 기능을 비활성화하는 정책 JSON을 정의한 후 Amazon S3에 업로드
2. **관리형 정책이 적용된 Browser 생성**: `enterprise_policies`에 `type: "MANAGED"`를 지정하여 정책을 적용하고 세션 녹화를 활성화한 사용자 지정 AgentCore Browser 생성
3. **Playwright로 시연**: 허용된 URL(페이지 로드)과 차단된 URL(Chrome에서 오류 페이지 표시)로 이동하여 에이전트 로직과 독립적으로 브라우저 수준에서 정책이 적용되는지 확인
4. **세션 녹화 검토**: AgentCore 콘솔에서 세션을 재생하여 정책 적용 확인
5. **선택 사항: Strands 에이전트 실행**: 제한된 Browser를 AI 에이전트 프레임워크와 함께 사용하여 정책 제한이 적용된 엔드 투 엔드 에이전트 동작 확인

### 파트 2: 사용자 지정 루트 CA 인증서

6. **AWS Secrets Manager에 루트 CA 저장**: 신뢰할 수 없는 [BadSSL](https://badssl.com) 루트 CA 인증서(공개 테스트 인증서)를 AWS Secrets Manager에 저장
7. **루트 CA가 없는 Code Interpreter**: 신뢰할 수 없는 인증서를 사용하는 사이트에 연결할 때 발생하는 `SSLCertVerificationError` 확인
8. **루트 CA가 있는 Code Interpreter**: `Certificate.from_secret_arn()`으로 사용자 지정 Code Interpreter를 생성하고 HTTP 200 연결 성공 확인

### 리소스 정리

사용자 지정 Browser, Code Interpreter, IAM 역할, AWS Secrets Manager 보안 암호, Amazon S3 정책 파일을 비롯한 모든 리소스를 삭제합니다.

## 주요 SDK 패턴

### 관리형 Chrome 정책(브라우저 수준)

```python
from bedrock_agentcore.tools import BrowserClient

client = BrowserClient(REGION)

response = client.create_browser(
    name="my_browser",
    execution_role_arn=EXECUTION_ROLE_ARN,
    network_configuration={"networkMode": "PUBLIC"},
    enterprise_policies=[
        {
            "location": {
                "s3": {
                    "bucket": POLICY_BUCKET,
                    "prefix": POLICY_KEY,
                }
            },
            "type": "MANAGED",
        }
    ],
)
```

### 사용자 지정 루트 CA 인증서

```python
from bedrock_agentcore.tools import CodeInterpreter, Certificate

ci_client = CodeInterpreter(REGION)

response = ci_client.create_code_interpreter(
    name="my_interpreter",
    execution_role_arn=EXECUTION_ROLE_ARN,
    network_configuration={"networkMode": "PUBLIC"},
    certificates=[
        Certificate.from_secret_arn(SECRET_ARN)
    ],
)
```

### 정책 적용 수준

| 수준 | 파라미터 | 설정 시점 | Chrome 디렉터리 | 재정의 가능 여부 |
|-------|-----------|----------|------------------|---------------|
| Managed | `type: "MANAGED"` | `create_browser()` | `/etc/chromium/policies/managed/` | 아니요 |
| Recommended | `type: "RECOMMENDED"` | `start()` / `browser_session()` | `/etc/chromium/policies/recommended/` | 예(Managed에서 재정의 가능) |

## 확인할 내용

- **터미널**: 허용된 페이지 제목과 차단된 URL 오류를 보여 주는 Playwright 출력
- **AgentCore 콘솔**: **Built-in tools** → 사용 중인 Browser → 활성 세션 → **View live session**으로 이동하여 실시간으로 확인
- **세션 재생**: 세션이 종료된 후 종료된 세션에서 **View Recording**을 선택하여 차단된 URL 접근 시도가 포함된 타임라인 확인
- **루트 CA 데모**: 인증서가 없을 때의 SSL 오류와 인증서가 있을 때의 200 성공 응답을 터미널 출력에서 확인

## 파일

| 파일 | 설명 |
|------|-------------|
| `browser-chrome-policies.ipynb` | 설정, Chrome 정책, 루트 CA 데모, 리소스 정리가 포함된 전체 튜토리얼 노트북 |
| `requirements.txt` | Python 종속성 |
| `README.md` | 현재 파일 |

## 보안 고려 사항

- Chrome 정책은 에이전트 프롬프트와 독립적으로 브라우저 수준에서 제한을 적용합니다.
- 관리형 정책은 세션 수준의 권장 정책으로 재정의할 수 없습니다.
- 루트 CA 인증서는 만료되기 전에 교체해야 합니다.
- Amazon S3 및 AWS Secrets Manager 액세스에는 최소 권한 IAM 정책을 사용합니다.
- 세션 녹화물에는 민감한 페이지 콘텐츠가 포함될 수 있으므로 적절한 Amazon S3 액세스 제어를 적용합니다.

## 추가 리소스

- [Amazon Bedrock AgentCore Browser 문서](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html)
- [Chrome Enterprise 정책 목록](https://chromeenterprise.google/policies/)
- [AWS Secrets Manager 문서](https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html)
- [Strands Agents 모델 공급자](https://strandsagents.com/latest/user-guide/concepts/model-providers/)
- [Amazon Bedrock AgentCore Python SDK](https://github.com/aws/bedrock-agentcore-sdk-python)
