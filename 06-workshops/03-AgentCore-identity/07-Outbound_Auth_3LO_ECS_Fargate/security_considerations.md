# 추가 보안 고려 사항

## 저장 데이터 암호화

이 샘플은 AWS 관리형 및 고객 관리형 KMS 암호화를 사용합니다.

**고객 관리형 KMS 키(포함):**

- Amazon CloudWatch Logs(에이전트 및 Session Binding 서비스)
- Amazon S3 세션 버킷

**AWS 관리형 암호화 키:**

- Application Load Balancer 액세스 로그 S3 버킷(ALB는 SSE-S3만 지원)
- Amazon ECR 리포지토리(CDK가 기본 암호화인 AWS 관리형 KMS를 사용해 자동 생성)

- **Amazon Bedrock AgentCore Identity** 토큰 볼트: 고객 관리형 KMS가 필요한 경우 [`set-token-vault-cmk`](https://docs.aws.amazon.com/cli/latest/reference/bedrock-agentcore-control/set-token-vault-cmk.html)를 사용하세요.

- **AWS Secrets Manager**(SSO 자격 증명): 고객 관리형 KMS가 필요한 경우 보안 암호를 생성할 때 `--kms-key-id` 파라미터를 추가하세요.

### 네트워크 및 모니터링

- **VPC Flow Logs**: 이 샘플에서는 비용 절감을 위해 VPC Flow Logs를 활성화하지 않습니다. 프로덕션 배포에서는 네트워크 트래픽 모니터링과 보안 분석을 위해 VPC Flow Logs를 활성화하세요.

- **VPC 엔드포인트**: 이 샘플은 AWS 서비스(Bedrock, S3, Secrets Manager)에 VPC 엔드포인트를 사용하지 않습니다. 프로덕션 배포에서는 NAT 게이트웨이와 인터넷 게이트웨이를 통해 트래픽을 라우팅하지 않도록 VPC 엔드포인트를 추가하는 방안을 고려하세요. 이를 통해 비용을 절감할 수 있습니다.

- **WAF 및 CloudFront**: ALB는 공개적으로 액세스할 수 있으며(포트 443에서 0.0.0.0/0 인바운드) OIDC 인증으로 보호됩니다. 프로덕션 배포에서는 일반적인 웹 공격(SQL injection, XSS, DDoS)으로부터 보호하기 위한 AWS WAF와 콘텐츠 전송, 캐싱 및 엣지에서의 추가 DDoS 보호를 위한 CloudFront를 추가하는 방안을 고려하세요.

- **CloudWatch 경보**: 이 샘플에는 모니터링을 위한 CloudWatch 경보가 포함되어 있지 않습니다. 프로덕션 배포에서는 비정상적인 리소스 사용량과 지표(CPU, 메모리, 오류율, API 제한)에 CloudWatch 경보를 구현하여 운영 및 보안 문제를 감지하고 대응하세요.

### 액세스 제어

- **Amazon S3 버킷 정책**: S3 버킷 정책과 IAM 조건 키를 사용하면 사용자 ID, IP 주소 또는 요청 속성을 기준으로 세분화된 액세스 제어를 적용하여 액세스를 더욱 제한할 수 있습니다.

- **KMS 키 관리**: KMS 키 정책은 루트 계정에 모든 권한(`kms:*`)을 허용합니다. 프로덕션 배포에서는 최소 권한 원칙을 따르도록 키 관리 권한을 계정의 특정 IAM 보안 주체나 역할로 제한하는 방안을 고려하세요.

- **Amazon Bedrock Guardrails**: 이 샘플은 Bedrock Guardrails를 구성하지 않습니다. 프로덕션 배포에서는 요구 사항에 따라 유해 콘텐츠, PII 및 에이전트의 부적절한 입력과 출력을 필터링하는 가드레일 구현을 고려하세요.
