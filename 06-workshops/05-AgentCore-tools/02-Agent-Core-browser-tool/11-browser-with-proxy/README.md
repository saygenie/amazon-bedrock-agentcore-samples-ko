# Squid 프록시를 사용하는 AgentCore Browser

이 예제에서는 모든 웹 트래픽을 Amazon EC2에서 실행되는 Squid 정방향 프록시를 통해 라우팅하는 Amazon Bedrock AgentCore Browser를 배포합니다. 프록시는 AWS Secrets Manager를 통해 요청을 인증하고 액세스 로그를 Amazon S3로 전송하므로, 브라우저가 방문한 모든 URL의 전체 감사 추적을 확보할 수 있습니다.

## 아키텍처

```
┌─────────────────────────────────────────────────────┐
│  VPC (10.0.0.0/16)                                  │
│                                                     │
│  ┌─────────────────────┐  ┌──────────────────────┐  │
│  │  Private Subnet     │  │  Public Subnet       │  │
│  │                     │  │                      │  │
│  │  AgentCore Browser  │──│  Squid EC2 (:3128)   │──── Internet
│  │  (VPC mode)         │  │  ├─ basic auth       │  │
│  │                     │  │  ├─ access logs → S3 │  │
│  └─────────────────────┘  │  └─ creds ← Secrets Mgr │
│                           └──────────────────────┘  │
│                                                     │
│  S3 Bucket (squid-logs)    Secrets Manager (creds)  │
└─────────────────────────────────────────────────────┘
```

Browser 보안 그룹은 포트 3128을 통한 Squid 아웃바운드 트래픽만 허용합니다. NAT Gateway가 없으므로 프록시가 인터넷으로 연결되는 유일한 경로입니다.

## 빠른 배포

CloudFormation으로 스택을 생성하려면 다음 버튼을 사용합니다.

[![스택 시작](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](agentcore-browser-proxy.yaml)

### 파라미터

| 파라미터 | 기본값 | 설명 |
|-----------|---------|-------------|
| VpcCidr | `10.0.0.0/16` | VPC의 CIDR 블록 |
| AvailabilityZone | — | 모든 서브넷에 사용할 AZ |
| BrowserName | `proxy_browser` | AgentCore Browser 이름 |
| SquidInstanceType | `t3.micro` | Squid용 Amazon EC2 인스턴스 유형 |

프록시 자격 증명(사용자 이름 및 임의 암호)은 AWS Secrets Manager에서 자동으로 생성됩니다.

## 배포되는 리소스

| 리소스 | 용도 |
|----------|---------|
| VPC 및 서브넷 2개 | 네트워크 격리 |
| Amazon EC2(Squid) | 기본 인증을 사용하는 정방향 프록시 |
| AWS Secrets Manager 보안 암호 | 자동 생성되는 프록시 자격 증명 |
| Amazon S3 버킷 | Squid 액세스 로그(90일 수명 주기) |
| AgentCore Browser | VPC 모드, 아웃바운드 트래픽을 프록시로 제한 |
| IAM 역할 | Browser 및 Amazon EC2에 대한 최소 권한 |

## 프록시 검증

배포 후 스택 출력을 가져옵니다.

```bash
aws cloudformation describe-stacks \
  --stack-name agentcore-browser-proxy \
  --query 'Stacks[0].Outputs' --output table
```

### 옵션 A: 노트북

```bash
pip install -r requirements.txt
```

Kiro IDE 또는 원하는 IDE에서 `verify_proxy.ipynb`를 엽니다.

### 옵션 B: 스크립트

```bash
pip install -r requirements.txt
python verify_proxy.py
```

두 방식 모두 다음 작업을 수행합니다.
1. CloudFormation에서 Browser ID, Squid IP, 보안 암호 ARN 읽기
2. Squid를 가리키는 `proxyConfiguration`으로 브라우저 세션 시작
3. `icanhazip.com`으로 이동하여 확인된 IP와 Squid의 퍼블릭 IP 비교
4. 두 IP가 일치하면 PASS 출력

### 프록시 구성 구조

`proxyConfiguration`은 다음과 같은 구조로 `start_browser_session()`에 전달합니다.

```json
{
  "proxies": [{
    "externalProxy": {
      "server": "<squid-private-ip>",
      "port": 3128,
      "credentials": {
        "basicAuth": {
          "secretArn": "arn:aws:secretsmanager:..."
        }
      }
    }
  }]
}
```

`domainPatterns`를 추가하여 특정 도메인만 프록시를 통해 라우팅할 수도 있으며, `bypass.domainPatterns`를 사용하면 특정 도메인이 프록시를 우회하도록 설정할 수 있습니다.

## 액세스 로그

Squid 액세스 로그는 5분마다 Amazon S3에 동기화됩니다.

```
s3://<stack>-squid-logs-<account>/squid-logs/YYYY/MM/DD/HH/<instance>-access.log.<n>
```

최근 로그를 나열합니다.

```bash
BUCKET=$(aws cloudformation describe-stacks --stack-name agentcore-browser-proxy \
  --query 'Stacks[0].Outputs[?OutputKey==`LogBucketName`].OutputValue' --output text)
aws s3 ls "s3://$BUCKET/squid-logs/" --recursive
```

## 파일

| 파일 | 설명 |
|------|-------------|
| `agentcore-browser-proxy.yaml` | CloudFormation 템플릿 |
| `verify_proxy.py` | CLI 검증 스크립트 |
| `verify_proxy.ipynb` | Amazon S3 로그 확인을 포함한 노트북 버전 |
| `requirements.txt` | Python 종속성 |

## 리소스 정리

```bash
# 먼저 log bucket 비우기(스택 삭제 전에 필요)
BUCKET=$(aws cloudformation describe-stacks --stack-name agentcore-browser-proxy \
  --query 'Stacks[0].Outputs[?OutputKey==`LogBucketName`].OutputValue' --output text)
aws s3 rm "s3://$BUCKET" --recursive

aws cloudformation delete-stack --stack-name agentcore-browser-proxy
```

## 보안 고려 사항

- Browser는 인터넷에 직접 액세스할 수 없는 프라이빗 서브넷에서 실행됩니다.
- 모든 웹 트래픽은 인증된 Squid 프록시를 통과해야 합니다.
- 프록시 자격 증명은 AWS Secrets Manager에 저장되며 평문으로 저장되지 않습니다.
- Amazon S3 로그 버킷은 퍼블릭 액세스가 차단되고 서버 측 암호화가 적용됩니다.
- Squid 보안 그룹은 Browser 보안 그룹의 연결만 허용합니다.
