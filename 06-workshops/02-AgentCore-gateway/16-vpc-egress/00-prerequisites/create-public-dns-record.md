<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Public DNS Record 생성

> **참고:** 이 문서의 가이드는 **워크숍 및 학습 전용**입니다. 프로덕션 배포에서는 조직의 보안 정책 및 DNS 관리 방식을 준수하세요.

CDK 스택이 배포한 load balancer를 도메인이 가리키도록 **public hosted zone**에 DNS record를 생성합니다.

## 사전 요구 사항

- 도메인의 Route 53 public hosted zone(다른 계정에 있어도 됨)
- CDK 스택 출력의 load balancer DNS 이름(`AlbDnsName` 또는 `NlbDnsName`)

## Record 생성

```bash
aws route53 change-resource-record-sets \
  --hosted-zone-id <public-hosted-zone-id> \
  --profile <profile-with-dns-access> \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "your-domain.com",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [{"Value": "<load-balancer-dns-from-stack-outputs>"}]
      }
    }]
  }'
```

> load balancer DNS 이름은 CDK 스택 출력에 있습니다(예: `AlbDnsName` 또는 `NlbDnsName`).

## 확인

```bash
dig @8.8.8.8 your-domain.com A +short
# Private IP가 반환되어야 함(load balancer가 internal이기 때문)
```

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](../LICENSE.txt) 파일을 참조하세요.
