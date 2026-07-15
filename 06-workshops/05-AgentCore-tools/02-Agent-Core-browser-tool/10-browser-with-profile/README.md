# Browser 프로필을 사용하는 AgentCore Browser Tool

이 예제에서는 Amazon Bedrock AgentCore Browser Tool에서 [Browser 프로필](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-profiles.html)을 사용하는 방법을 살펴봅니다. Browser 프로필을 사용하면 여러 브라우저 세션에서 세션 데이터(쿠키, 로컬 스토리지)를 유지하고 재사용할 수 있습니다.

## 개요

Browser 프로필을 사용하면 다음 작업을 수행할 수 있습니다.
- **세션 데이터 유지**: 쿠키와 로컬 스토리지 저장
- **사용자 행동 시뮬레이션**: 브라우저 상태를 유지해야 하는 워크플로 테스트
- **컨텍스트 공유**: 여러 브라우저 세션에서 동일한 프로필 사용

## 사용 사례

- 장바구니를 유지하는 전자상거래 테스트
- 다시 로그인하지 않고 인증된 워크플로 테스트
- 여러 세션에 걸친 다단계 사용자 여정

## 시작하기

### 사전 요구 사항

시작하기 전에 [샘플 전자상거래 사이트](sample-ecommerce/README.md)로 이동하여 이 예제에서 사용할 모의 전자상거래 사이트를 배포합니다.

### 설치

```bash
pip install -r requirements.txt
```

## 노트북 둘러보기

[browser-profile.ipynb 노트북](browser-profile.ipynb)에서는 다음 내용을 살펴봅니다.

### 1. 설정
- 브라우저 녹화물을 저장할 Amazon S3 버킷 생성
- 필수 권한이 있는 IAM 역할 생성
- 사용자 지정 AgentCore Browser 생성
- Browser 프로필 생성

### 2. 첫 번째 세션
- 브라우저 세션 시작
- 모의 전자상거래 사이트가 있는 Amazon S3 버킷을 가리키는 CloudFront 도메인으로 이동
- 장바구니에 상품 추가
- **세션을 프로필에 저장**
- 세션 중지

### 3. 두 번째 세션
- **저장된 프로필을 사용하여** 새 세션 시작
- 장바구니로 이동
- 이전 세션의 상품이 유지되는지 확인

### 4. 선택 사항: 녹화물 다운로드
- Amazon S3에서 세션 녹화물 다운로드
- rrweb 형식으로 변환
- 노트북에서 세션 재생

### 5. 문제 해결
- 프로필이 로드되지 않음: 세션을 중지하기 전에 프로필이 저장되었는지 확인
- 권한 오류: IAM 역할에 SaveBrowserSessionProfile 권한이 있는지 확인
- 세션 제한 시간 초과: 브라우저 세션에는 최대 지속 시간이 있으므로 제한 시간 전에 프로필 저장
- **만료된 쿠키:** 쿠키에는 웹사이트에서 설정한 자체 만료 시간이 있습니다. Browser 프로필은 쿠키를 유지하지만, 만료된 쿠키는 만료 날짜에 따라 브라우저에서 자동으로 제거됩니다.

## 파일

- **browser-profile.ipynb**: 단계별 예제가 포함된 전체 튜토리얼 노트북
- **browser_helper.py**: SigV4 서명 및 WebSocket URL 생성을 위한 도우미 함수
- **requirements.txt**: Python 종속성

## 주요 개념

### Browser 프로필
Browser 프로필에는 다음을 비롯한 세션 정보가 저장됩니다.
- 쿠키
- 로컬 스토리지

### 프로필 수명 주기
1. **프로필 생성**: `create_browser_profile()`
2. **세션 저장**: `save_browser_session_profile()` - 현재 세션 상태 캡처
3. **프로필 로드**: `start_browser_session(profileConfiguration={...})` - 저장된 상태 복원
4. **프로필 삭제**: `delete_browser_profile()` - 리소스 정리

## IAM 권한

실행 역할에는 다음 권한이 필요합니다.
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock-agentcore:StartBrowserSession",
    "bedrock-agentcore:SaveBrowserSessionProfile"
  ],
  "Resource": [
    "arn:aws:bedrock-agentcore:REGION:ACCOUNT:browser-profile/PROFILE_NAME",
    "arn:aws:bedrock-agentcore:REGION:ACCOUNT:browser-custom/BROWSER_NAME"
  ]
}
```

## 리소스 정리

모든 리소스를 제거하려면 다음 코드를 실행합니다.
```python
# Browser 삭제
browser_boto3.delete_browser(browserId=browser_id)

# Profile 삭제
browser_boto3.delete_browser_profile(profileId=profile_id)

# IAM 역할 삭제(Console 또는 CLI 사용)
# S3 bucket 삭제(Console 또는 CLI 사용)
```

## 보안 고려 사항

- Browser 프로필에는 민감한 세션 데이터가 포함될 수 있습니다.
- 적절한 IAM 정책을 사용하여 프로필 액세스를 제한합니다.
- 규정 준수를 위해 프로필 보존 정책을 고려합니다.
- Amazon S3에 저장된 녹화물에는 적절한 암호화 및 액세스 제어를 적용해야 합니다.

## 문제 해결

**프로필이 로드되지 않음**: 세션을 중지하기 전에 프로필이 저장되었는지 확인합니다.

**권한 오류**: IAM 역할에 `SaveBrowserSessionProfile` 권한이 있는지 확인합니다.

**세션 제한 시간 초과**: 브라우저 세션에는 최대 지속 시간이 있으므로 제한 시간 전에 프로필을 저장합니다.

## 추가 리소스

- [AgentCore Browser 문서](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore-browser.html)
- [Playwright 문서](https://playwright.dev/docs/intro)
- [rrweb Player](https://github.com/rrweb-io/rrweb)
