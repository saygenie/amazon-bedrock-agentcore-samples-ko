#!/bin/bash

#######################################################################
# build-and-push.sh
#
# Docker 이미지를 빌드하여 Amazon ECR에 푸시
#
# 이 스크립트는 Spring Boot 에이전트 애플리케이션을 Docker 이미지로
# 빌드하여 Amazon ECR에 푸시합니다.
#######################################################################

set -e

# 출력용 색상
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # 색상 없음

#######################################################################
# 사용법
#######################################################################
usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Build Docker image and push to Amazon ECR.

Required:
  -r, --region          AWS region (e.g., us-east-1)
  -u, --ecr-uri         ECR repository URI (e.g., 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-repo)

Optional:
  -t, --tag             Image tag (default: latest)
  -b, --build-only      Build image only, do not push to ECR
  -h, --help            Show this help message

Examples:
  # Build and push with default tag 'latest'
  $(basename "$0") -r us-east-1 -u 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-agent

  # Build and push with custom tag
  $(basename "$0") -r us-east-1 -u 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-agent -t v1.0.0

  # Build only (no push)
  $(basename "$0") -r us-east-1 -u 123456789012.dkr.ecr.us-east-1.amazonaws.com/my-agent -b

EOF
    exit 1
}

#######################################################################
# 로깅 함수
#######################################################################
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

#######################################################################
# 인수 파싱
#######################################################################
AWS_REGION=""
ECR_URI=""
IMAGE_TAG="latest"
BUILD_ONLY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--region)
            AWS_REGION="$2"
            shift 2
            ;;
        -u|--ecr-uri)
            ECR_URI="$2"
            shift 2
            ;;
        -t|--tag)
            IMAGE_TAG="$2"
            shift 2
            ;;
        -b|--build-only)
            BUILD_ONLY=true
            shift
            ;;
        -h|--help)
            usage
            ;;
        *)
            log_error "Unknown option: $1"
            usage
            ;;
    esac
done

#######################################################################
# 필수 인수 검증
#######################################################################
if [[ -z "$AWS_REGION" ]]; then
    log_error "AWS region is required (-r, --region)"
    usage
fi

if [[ -z "$ECR_URI" ]]; then
    log_error "ECR repository URI is required (-u, --ecr-uri)"
    usage
fi

#######################################################################
# 필수 조건 검증
#######################################################################
log_info "Validating prerequisites..."

# Docker 설치 및 실행 여부 확인
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker info &> /dev/null; then
    log_error "Docker daemon is not running. Please start Docker first."
    exit 1
fi

# AWS CLI 설치 여부 확인
if ! command -v aws &> /dev/null; then
    log_error "AWS CLI is not installed. Please install AWS CLI first."
    exit 1
fi

log_info "Prerequisites validated successfully"

#######################################################################
# Docker 이미지 빌드
#######################################################################
FULL_IMAGE_URI="${ECR_URI}:${IMAGE_TAG}"

log_info "Building Docker image..."
log_info "  Image: $FULL_IMAGE_URI"

# 이 스크립트가 있는 디렉터리 확인
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

docker build \
    --tag "$FULL_IMAGE_URI" \
    "$SCRIPT_DIR"

log_info "Docker image built successfully"

#######################################################################
# 빌드 전용 모드가 아니면 ECR에 푸시
#######################################################################
if [[ "$BUILD_ONLY" == true ]]; then
    log_info "Build-only mode: Skipping ECR push"
    log_info "Local image available as: $FULL_IMAGE_URI"
    exit 0
fi

log_info "Logging into Amazon ECR..."

# URI에서 ECR 레지스트리 추출(첫 번째 / 앞부분)
ECR_REGISTRY="${ECR_URI%%/*}"

# ECR에 로그인
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "$ECR_REGISTRY"

log_info "ECR login successful"

log_info "Pushing image to ECR..."
log_info "  Destination: $FULL_IMAGE_URI"

docker push "$FULL_IMAGE_URI"

log_info "Image pushed successfully to ECR"

#######################################################################
# 요약
#######################################################################
echo ""
log_info "=========================================="
log_info "Build and push completed successfully!"
log_info "=========================================="
log_info "Image URI: $FULL_IMAGE_URI"
log_info "Region: $AWS_REGION"
echo ""
