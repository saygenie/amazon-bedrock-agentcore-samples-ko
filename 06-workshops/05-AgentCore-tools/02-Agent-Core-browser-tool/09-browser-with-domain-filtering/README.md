# AWS Network Firewall을 사용하는 AgentCore Browser Tool

이 예제에서는 AWS Network Firewall을 사용하여 도메인 기반 허용 목록과 차단 목록이 적용된 Amazon Bedrock AgentCore Browser Tool을 배포하는 방법을 살펴봅니다. 이를 통해 네트워크 수준에서 필터링되는 안전하고 통제된 브라우징 환경을 구축할 수 있습니다.

## 아키텍처 개요

이 솔루션은 다음 리소스를 배포합니다.
- **서브넷 3개가 있는 VPC**: 프라이빗(Browser), 퍼블릭(NAT Gateway), Firewall 서브넷
- **AWS Network Firewall**: 허용 목록과 차단 목록을 사용한 도메인 필터링
- **AgentCore Browser**: VPC 구성으로 프라이빗 서브넷에 배포
- **NAT Gateway**: 방화벽 검사를 거치는 아웃바운드 인터넷 액세스
- **CloudWatch Logs**: 모니터링을 위한 방화벽 경고 및 흐름 로그

## 빠른 배포

CloudFormation으로 스택을 생성하려면 다음 버튼을 사용합니다.

[![스택 시작](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](agentcore-browser-firewall.yaml)

### 파라미터

- **VpcCidr**: VPC의 CIDR 블록(기본값: `10.0.0.0/16`)
- **AvailabilityZone**: 모든 서브넷에 사용할 AZ
- **AllowedDomains**: 쉼표로 구분한 허용 도메인 목록(예: `.example.com,.wikipedia.org`)
- **DeniedDomains**: 쉼표로 구분한 차단 도메인 목록(예: `.facebook.com,.twitter.com`)
- **BrowserName**: Browser 이름(기본값: `secure_browser`)
- **BucketConfigForOutput**: 브라우저 녹화물을 저장할 Amazon S3 버킷 이름

## 테스트

### 옵션 1 - Jupyter Notebook

단계별로 진행하려면 [verify_domain_filtering.ipynb 노트북](verify_domain_filtering.ipynb)을 열고 각 단계를 실행합니다.


### 옵션 2 - Python 코드

코드로 바로 진행하려면 제공된 Python 파일을 사용합니다.

배포 후 AgentCore Browser 식별자를 가져옵니다. 명령줄에서는 다음과 같이 확인할 수 있습니다.

```bash
# CloudFormation 출력에서 Browser ID 가져오기
export BROWSER_ID=$(aws cloudformation describe-stacks \
  --stack-name agentcore-browser-firewall \
  --query 'Stacks[0].Outputs[?OutputKey==`BrowserToolCustomOutput`].OutputValue' \
  --output text)
```

또는 AWS Console의 CloudFormation 스택 출력 정보에서 확인할 수 있습니다.

![Browser 출력](img/cfn-output.png)

**중요: `verify_domain_filtering.py` 스크립트는 BROWSER_ID 환경 변수에 Browser 식별자가 설정되어 있어야 합니다.**

제공된 Python 스크립트로 도메인 필터링을 테스트합니다.

```bash
# 종속성 설치
pip install -r requirements.txt
playwright install chromium

# 테스트 실행
python verify_domain_filtering.py
```

### 테스트 스크립트

`verify_domain_filtering.py` 스크립트는 다음을 검증합니다.
- ✅ 허용된 도메인(example.com, wikipedia.org) - 성공해야 함
- ❌ 차단된 도메인(facebook.com, twitter.com) - 차단되어야 함
- ❌ 목록에 없는 도메인 - 차단되어야 함(기본 차단)

## 파일

- **agentcore-browser-firewall.yaml**: 전체 인프라를 정의하는 CloudFormation 템플릿
- **verify_domain_filtering.py**: Playwright를 사용하여 방화벽 규칙을 검증하는 자동 테스트 스크립트
- **verify_domain_filtering.ipynb**: 단계별 Jupyter Notebook

## 모니터링

CloudWatch에서 방화벽 로그를 확인합니다.
- 경고 로그: `/aws/network-firewall/{StackName}/alerts`
- 흐름 로그: `/aws/network-firewall/{StackName}/flow`

## 리소스 정리

```bash
aws cloudformation delete-stack --stack-name agentcore-browser-firewall
```

## 보안 고려 사항

- Browser는 인터넷에 직접 액세스할 수 없는 프라이빗 서브넷에서 실행됩니다.
- 모든 트래픽은 인터넷에 도달하기 전에 Network Firewall의 검사를 거칩니다.
- 기본 차단 정책에 따라 명시적으로 허용된 도메인에만 액세스할 수 있습니다.
- 녹화물은 적절한 IAM 권한이 적용된 Amazon S3에 저장됩니다.
