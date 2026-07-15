<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ACM Public Certificate 생성

> **참고:** 이 문서의 가이드는 **워크숍 및 학습 전용**입니다. 프로덕션 배포에서는 조직의 보안 정책 및 인증서 수명 주기 요구 사항을 준수하세요.

## 사전 요구 사항

- Route 53 hosted zone에 등록된 소유 도메인(또는 CNAME record를 추가할 수 있는 DNS 액세스)
- 구성된 AWS CLI

## 1단계: 인증서 요청

load balancer를 배포할 계정에서 다음 명령을 실행합니다.

```bash
aws acm request-certificate \
  --domain-name "*.your-domain.com" \
  --validation-method DNS \
  --region us-west-2 \
  --profile default
```

> 모든 하위 도메인을 포함하려면 wildcard 인증서(`*.your-domain.com`)를 사용하고, 그렇지 않으면 특정 도메인을 요청합니다. 도메인은 load balancer를 가리키도록 설정할 도메인과 일치해야 합니다.

응답의 `CertificateArn`을 기록합니다.

## 2단계: DNS validation record 가져오기

```bash
aws acm describe-certificate \
  --certificate-arn <certificate-arn> \
  --region us-west-2 \
  --profile default \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord'
```

다음과 같은 CNAME record를 반환합니다.

```json
{
  "Name": "_abc123.your-domain.com.",
  "Type": "CNAME",
  "Value": "_def456.acm-validations.aws."
}
```

## 3단계: validation CNAME 추가

도메인의 **public hosted zone**에 이 CNAME을 추가합니다.

**콘솔:** Route 53 → Hosted zones → 도메인 → Create record → CNAME → Name 및 Value 붙여넣기

**CLI:**

```bash
# Hosted zone ID 가져오기
aws route53 list-hosted-zones-by-name \
  --dns-name your-domain.com \
  --query 'HostedZones[0].Id' \
  --output text \
  --profile <profile-with-dns-access>

# 검증 record 추가
aws route53 change-resource-record-sets \
  --hosted-zone-id <hosted-zone-id> \
  --profile <profile-with-dns-access> \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "<Name from Step 2>",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [{"Value": "<Value from Step 2>"}]
      }
    }]
  }'
```

> 도메인이 다른 AWS 계정에 있다면 해당 계정의 Route 53 hosted zone에 CNAME을 추가합니다.

## 4단계: 검증 대기

```bash
aws acm describe-certificate \
  --certificate-arn <certificate-arn> \
  --region us-west-2 \
  --profile default \
  --query 'Certificate.Status'
```

`"ISSUED"`가 반환될 때까지 기다립니다. 일반적으로 몇 분 정도 걸립니다.

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](../LICENSE.txt) 파일을 참조하세요.
