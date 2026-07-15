<!-- Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved. -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Private Hosted Zone 생성

> **참고:** 이 문서의 가이드는 **워크숍 및 학습 전용**입니다. 프로덕션 배포에서는 조직의 보안 정책 및 DNS 관리 방식을 준수하세요.

도메인의 Route 53 private hosted zone을 생성하여 VPC에 연결합니다. 이 zone의 record는 연결된 VPC 내부에서만 확인할 수 있습니다.

> 이 워크숍의 일부 CDK 스택은 private hosted zone을 자동으로 생성합니다. 수동으로 생성하기 전에 실습 지침을 확인하세요.

## 사전 요구 사항

- VPC ID
- 구성된 AWS CLI

## 1단계: private hosted zone 생성

```bash
aws route53 create-hosted-zone \
  --name your-domain.com \
  --vpc VPCRegion=us-west-2,VPCId=<your-vpc-id> \
  --caller-reference $(date +%s) \
  --hosted-zone-config PrivateZone=true \
  --profile default
```

응답의 `HostedZoneId`를 기록합니다.

> public hosted zone과 동일한 도메인 이름을 사용할 수 있습니다. Route 53은 연결된 VPC에서 private zone을 먼저 확인하며 public zone은 영향을 받지 않습니다.

## 2단계: DNS record 추가

CDK 스택을 배포한 후 도메인에서 load balancer를 가리키는 Alias A record를 추가합니다.

```bash
aws route53 change-resource-record-sets \
  --hosted-zone-id <private-hosted-zone-id> \
  --profile default \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "internal-mcp.your-domain.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "<load-balancer-hosted-zone-id>",
          "DNSName": "<load-balancer-dns-from-stack-outputs>",
          "EvaluateTargetHealth": true
        }
      }
    }]
  }'
```

> load balancer에는 CNAME이 아닌 Alias A record를 사용하세요. 무료이며 zone apex를 지원합니다.

## 확인

**VPC 내부**(bastion 또는 CloudShell VPC mode)에서:
```bash
dig internal-mcp.your-domain.com A +short
# Load balancer의 private IP 반환
```

**VPC 외부**에서:
```bash
dig @8.8.8.8 internal-mcp.your-domain.com A +short
# 아무것도 반환하지 않음(NXDOMAIN)
```

## 정리

DNS record를 먼저 삭제한 다음 hosted zone을 삭제합니다.

```bash
# Record 삭제(Action: DELETE를 사용하여 동일한 change batch 적용)

# Hosted zone 삭제
aws route53 delete-hosted-zone \
  --id <private-hosted-zone-id> \
  --profile default
```

## 라이선스

이 프로젝트는 Apache License 2.0에 따라 라이선스가 부여됩니다. 자세한 내용은 [LICENSE](../LICENSE.txt) 파일을 참조하세요.
