#!/bin/bash

# 엄격한 오류 처리 활성화
set -euo pipefail

# 로깅 함수
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# ----- 구성 -----
INFRA_STACK_NAME=${1:-AsanaIntegrationStackInfra}
COGNITO_STACK_NAME=${2:-AsanaIntegrationStackCognito}
REGION=$(aws configure get region 2>/dev/null || echo "us-east-1")

log "🧹 Starting cleanup process..."
log "Region: $REGION"
log "Infrastructure Stack: $INFRA_STACK_NAME"
log "Cognito Stack: $COGNITO_STACK_NAME"

# AWS CLI 구성 여부 검증
if ! aws sts get-caller-identity >/dev/null 2>&1; then
    log "❌ AWS CLI not configured or credentials invalid"
    exit 1
fi

# CloudFormation 스택 삭제 함수
delete_stack() {
    local stack_name=$1
    
    log "🗑️  Checking if stack $stack_name exists..."
    
    # 스택이 있는지 확인하고 상태 가져오기
    local stack_status
    if stack_status=$(aws cloudformation describe-stacks --stack-name "$stack_name" --region "$REGION" --query 'Stacks[0].StackStatus' --output text 2>/dev/null); then
        log "📦 Stack $stack_name exists with status: $stack_status"
        
        # 스택이 삭제 가능한 상태인지 확인
        case "$stack_status" in
            "DELETE_IN_PROGRESS")
                log "⏳ Stack $stack_name is already being deleted, waiting..."
                ;;
            "DELETE_COMPLETE")
                log "ℹ️  Stack $stack_name is already deleted"
                return 0
                ;;
            "DELETE_FAILED"|"ROLLBACK_COMPLETE"|"ROLLBACK_FAILED"|"CREATE_FAILED")
                log "⚠️  Stack $stack_name is in state $stack_status, attempting deletion..."
                ;;
        esac
        
        # 스택 삭제 시도
        if aws cloudformation delete-stack --stack-name "$stack_name" --region "$REGION" 2>/dev/null; then
            log "📦 Deletion initiated for stack: $stack_name"
        else
            log "⚠️  Failed to initiate deletion for stack: $stack_name"
        fi
        
        log "⏳ Waiting for stack $stack_name to be deleted (timeout: 30 minutes)..."
        if aws cloudformation wait stack-delete-complete --stack-name "$stack_name" --region "$REGION" --cli-read-timeout 1800 --cli-connect-timeout 60; then
            log "✅ Stack $stack_name deleted successfully"
        else
            log "❌ Failed to delete stack $stack_name or operation timed out"
            return 1
        fi
    else
        log "ℹ️  Stack $stack_name does not exist or is already deleted"
    fi
}

# 역순으로 스택 삭제(인프라를 먼저 삭제한 다음 Cognito 삭제)
cleanup_failed=0

log "🔧 Deleting infrastructure stack first..."
if ! delete_stack "$INFRA_STACK_NAME"; then
    log "❌ Failed to delete infrastructure stack"
    cleanup_failed=1
fi

log "🔧 Deleting Cognito stack..."
if ! delete_stack "$COGNITO_STACK_NAME"; then
    log "❌ Failed to delete Cognito stack"
    cleanup_failed=1
fi

if [ $cleanup_failed -eq 0 ]; then
    log "🎉 Cleanup complete! Both stacks have been deleted successfully."
    exit 0
else
    log "⚠️  Cleanup completed with errors. Please check the logs above."
    exit 1
fi
