# Amazon EKS에 Strands Agents 배포

이 예제에서는 [Strands Agents SDK](https://github.com/strands-agents/sdk-python)로 구축한 Python 애플리케이션을 Amazon EKS에 배포하는 방법을 살펴봅니다. Application Load Balancer와 함께 Amazon EKS에서 컨테이너형 서비스로 실행되는 여행 조사 에이전트 애플리케이션을 배포합니다.

이 애플리케이션은 FastAPI로 구축되며 제공된 프롬프트를 기반으로 여행 정보를 반환하는 `/travel` 엔드포인트를 제공합니다.

## 사전 요구 사항

- [AWS CLI](https://aws.amazon.com/cli/) 설치 및 구성
- [eksctl](https://eksctl.io/installation/) v0.208.x 이상 설치
- [Helm](https://helm.sh/) v3 이상 설치
- [kubectl](https://docs.aws.amazon.com/eks/latest/userguide/install-kubectl.html) 설치
- 다음 중 하나:
    - [Podman](https://podman.io/) 설치 및 실행
    - 또는 [Docker](https://www.docker.com/) 설치 및 실행
- AWS 환경에서 Amazon Bedrock Anthropic Claude 모델 활성화

## 빠른 시작(자동 배포)

자동 배포를 진행하려면 포함된 Jupyter 노트북을 사용합니다.

```bash
# 이 디렉터리로 이동
cd strands-travel-agent-eks

# Jupyter 시작
jupyter notebook deploy.ipynb
```

노트북은 다음을 포함한 전체 배포 프로세스를 자동화합니다.
- CloudWatch 로그 그룹 생성
- EKS 클러스터 생성
- Docker 이미지 빌드 및 ECR로 푸시
- IAM 정책 및 Pod Identity 구성
- Helm 차트 배포
- 포트 포워딩 및 에이전트 테스트

> **참고:** CloudWatch Observability 추가 기능(노트북의 섹션 8)은 **선택 사항**입니다. Bedrock AgentCore Observability에 필수적이지 **않습니다**. AgentCore는 Dockerfile의 OTEL 구성을 사용하여 텔레메트리를 CloudWatch로 직접 전송합니다.

**환경 변수(선택 사항):**

노트북을 실행하기 전에 다음 환경 변수를 설정하여 배포를 사용자 지정할 수 있습니다.

| 변수 | 기본값 | 설명 |
|----------|---------|-------------|
| `AWS_REGION` | `us-east-1` | 배포할 AWS 리전 |
| `CLUSTER_NAME` | `eks-strands-agents-demo` | EKS 클러스터 이름 |
| `SERVICE_NAME` | `strands-agents-travel` | Helm 릴리스의 서비스 이름 |
| `LOG_GROUP_NAME` | `/strands-agents/travel` | CloudWatch 로그 그룹 |
| `LOG_STREAM_NAME` | `agent-logs` | CloudWatch 로그 스트림 |
| `METRIC_NAMESPACE` | `StrandsAgents/Travel` | CloudWatch 지표 네임스페이스 |
| `LOCAL_PORT` | `8080` | 포트 포워딩을 위한 로컬 포트 |

## 프로젝트 구조

```
.
├── README.md
├── deploy.ipynb              # 자동 배포 노트북
├── chart/                    # Kubernetes 배포용 Helm chart
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
└── docker/                   # Docker container 파일
    ├── Dockerfile
    ├── app/
    │   └── app.py           # FastAPI travel agent 애플리케이션
    └── requirements.txt
```

## 수동 배포

다음 섹션에서는 수동 배포 단계를 설명합니다. 자동화된 notebook보다 CLI 명령을 선호하는 경우 이 단계를 사용하세요.

### 구성

Docker 이미지를 빌드하기 전에 `docker/Dockerfile`에서 다음 값을 업데이트합니다.

| 변수 | 설명 | 필요한 작업 |
|----------|-------------|-----------------|
| `OTEL_RESOURCE_ATTRIBUTES` | AgentCore Observability용 서비스 이름 | `<YOUR_SERVICE_NAME>`을 사용할 서비스 이름으로 대체 |
| `OTEL_EXPORTER_OTLP_LOGS_HEADERS` | OpenTelemetry 관측성 구성 | `<YOUR_LOG_GROUP>`, `<YOUR_LOG_STREAM>`, `<YOUR_METRIC_NAMESPACE>`를 사용할 값으로 대체 |

이 애플리케이션은 다음 런타임 환경 변수도 지원합니다(기본값은 `docker/app/app.py`에 설정됨).

| 변수 | 설명 | 기본값 |
|----------|-------------|---------|
| `MODEL_ID` | Amazon Bedrock 모델 ID | `us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `MODEL_TEMPERATURE` | 응답의 모델 온도 | `0` |
| `MODEL_MAX_TOKENS` | 응답의 최대 토큰 수 | `1028` |

### EKS Auto Mode 클러스터 생성

환경 변수를 설정합니다.
```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
export AWS_REGION=us-east-1
export CLUSTER_NAME=eks-strands-agents-demo
```

EKS Auto Mode 클러스터를 생성합니다.
```bash
eksctl create cluster --name $CLUSTER_NAME --enable-auto-mode
```

kubeconfig 컨텍스트를 구성합니다.
```bash
aws eks update-kubeconfig --name $CLUSTER_NAME
```

### Docker 이미지 빌드 및 ECR로 푸시

다음 단계에 따라 Docker 이미지를 빌드하고 Amazon ECR로 푸시합니다.

1. Amazon ECR에 인증합니다.
```bash
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com
```

2. ECR 저장소가 없으면 생성합니다.
```bash
aws ecr create-repository --repository-name strands-agents-travel --region ${AWS_REGION}
```

3. Docker 이미지를 빌드합니다.
```bash
docker build --platform linux/amd64 -t strands-agents-travel:latest docker/
```

4. ECR용 이미지 태그를 지정합니다.
```bash
docker tag strands-agents-travel:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/strands-agents-travel:latest
```

5. 이미지를 ECR로 푸시합니다.
```bash
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/strands-agents-travel:latest
```

### Amazon Bedrock 액세스를 위한 EKS Pod Identity 구성

모든 Amazon Bedrock 모델에 대해 InvokeModel 및 InvokeModelWithResponseStream을 허용하는 IAM 정책을 생성합니다.
```bash
cat > bedrock-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    }
  ]
}
EOF

aws iam create-policy \
  --policy-name strands-agents-travel-bedrock-policy \
  --policy-document file://bedrock-policy.json
rm -f bedrock-policy.json
```

EKS Pod Identity 연결을 생성합니다.
```bash
eksctl create podidentityassociation --cluster $CLUSTER_NAME \
  --namespace default \
  --service-account-name strands-agents-travel \
  --permission-policy-arns arn:aws:iam::$AWS_ACCOUNT_ID:policy/strands-agents-travel-bedrock-policy \
  --role-name eks-strands-agents-travel
```

### strands-agents-travel 애플리케이션 배포

ECR의 이미지로 Helm 차트를 배포합니다.
```bash
helm install strands-agents-travel ./chart \
  --set image.repository=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/strands-agents-travel \
  --set image.tag=latest
```

Deployment를 사용할 수 있을 때까지 기다립니다(Pod 실행 중).
```bash
kubectl wait --for=condition=available deployments strands-agents-travel --all
```

### 에이전트 테스트

Kubernetes 포트 포워딩을 사용합니다.
```bash
kubectl --namespace default port-forward service/strands-agents-travel 8080:80 &
```

여행 서비스를 호출합니다.
```bash
curl -X POST \
  http://localhost:8080/travel \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "What are the best places to visit in Tokyo in March?"}'
```

### Application Load Balancer를 통해 에이전트 공개

[IngressClass를 생성하여 Application Load Balancer를 구성합니다](https://docs.aws.amazon.com/eks/latest/userguide/auto-configure-alb.html).
```bash
cat <<EOF | kubectl apply -f -
apiVersion: eks.amazonaws.com/v1
kind: IngressClassParams
metadata:
  name: alb
spec:
  scheme: internet-facing
EOF
```

```bash
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: IngressClass
metadata:
  name: alb
  annotations:
    ingressclass.kubernetes.io/is-default-class: "true"
spec:
  controller: eks.amazonaws.com/alb
  parameters:
    apiGroup: eks.amazonaws.com
    kind: IngressClassParams
    name: alb
EOF
```

생성한 IngressClass를 사용하여 Ingress를 생성하도록 Helm 배포를 업데이트합니다.
```bash
helm upgrade strands-agents-travel ./chart \
  --set image.repository=${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/strands-agents-travel \
  --set image.tag=latest \
  --set ingress.enabled=true \
  --set ingress.className=alb
```

ALB URL을 가져옵니다.
```bash
export ALB_URL=$(kubectl get ingress strands-agents-travel -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "The shared ALB is available at: http://$ALB_URL"
```

ALB가 활성화될 때까지 기다립니다.
```bash
aws elbv2 wait load-balancer-available --load-balancer-arns $(aws elbv2 describe-load-balancers --query 'LoadBalancers[?DNSName==`'"$ALB_URL"'`].LoadBalancerArn' --output text)
```

Application Load Balancer를 통해 여행 서비스를 호출합니다.
```bash
curl -X POST \
  http://$ALB_URL/travel \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "What are the top attractions in Barcelona?"}'
```

### 고가용성 및 복원력 구성

고가용성을 구성하려면 다음을 수행합니다.
- 복제본을 3개로 늘림
- [Topology Spread Constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/): 여러 가용 영역에 워크로드 분산
- [Pod Disruption Budgets](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/#pod-disruption-budgets): minAvailable 값 1 허용

```bash
helm upgrade strands-agents-travel ./chart -f - <<EOF
image:
  repository: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/strands-agents-travel
  tag: latest

ingress:
  enabled: true
  className: alb

replicaCount: 3

topologySpreadConstraints:
  - maxSkew: 1
    minDomains: 3
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        app.kubernetes.io/name: strands-agents-travel
  - maxSkew: 1
    topologyKey: kubernetes.io/hostname
    whenUnsatisfiable: ScheduleAnyway
    labelSelector:
      matchLabels:
        app.kubernetes.io/instance: strands-agents-travel

podDisruptionBudget:
  enabled: true
  minAvailable: 1
EOF
```

## 정리

Helm 차트를 제거합니다.
```bash
helm uninstall strands-agents-travel
```

EKS Auto Mode 클러스터를 삭제합니다.
```bash
eksctl delete cluster --name $CLUSTER_NAME --wait
```

IAM 정책을 삭제합니다.
```bash
aws iam delete-policy --policy-arn arn:aws:iam::$AWS_ACCOUNT_ID:policy/strands-agents-travel-bedrock-policy
```

## 라이선스

이 프로젝트에는 Apache License 2.0이 적용됩니다. 자세한 내용은 LICENSE 파일을 참조하세요.
