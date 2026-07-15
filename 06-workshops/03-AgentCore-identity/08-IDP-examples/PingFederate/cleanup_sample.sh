#!/bin/bash
set -e

echo "=========================================="
echo "Cleaning up: PingFederate + VPC Lattice + AgentCore Identity"
echo "=========================================="
echo ""
echo "This will destroy ALL resources created by the sample."
echo ""
echo "Cleanup order:"
echo "  1. AgentCore Gateway (if exists)"
echo "  2. AgentCore credential provider (if exists)"
echo "  3. Agent runtime stack (if deployed)"
echo "  4. PrivateIdpLatticeStack (if deployed)"
echo "  5. PrivateIdpGatewayInfraStack"
echo "  6. PrivateIdpPingFederateStack"
echo "  7. PrivateIdpVpcStack (may require retry if Lattice ENIs not yet released)"
echo ""
read -p "Are you sure? (y/N) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

echo ""

# 1단계: Gateway 삭제(가능한 범위에서 시도)
echo "Deleting AgentCore Gateway..."
GATEWAY_ID=$(aws bedrock-agentcore-control list-gateways \
    --query 'items[?name==`PingGateway`].gatewayId' --output text 2>/dev/null || echo "")
if [ -n "$GATEWAY_ID" ] && [ "$GATEWAY_ID" != "None" ]; then
    aws bedrock-agentcore-control delete-gateway --gateway-identifier "$GATEWAY_ID" 2>/dev/null
    echo "  Gateway 'PingGateway' ($GATEWAY_ID) deleted."
else
    echo "  Gateway 'PingGateway' not found (skipping)."
fi
echo ""

# 2단계: 자격 증명 공급자 삭제(가능한 범위에서 시도)
echo "Deleting AgentCore credential provider..."
if aws bedrock-agentcore-control delete-oauth2-credential-provider \
    --name "ping-private-idp" 2>/dev/null; then
    echo "  Credential provider 'ping-private-idp' deleted."
else
    echo "  Credential provider 'ping-private-idp' not found or already deleted (skipping)."
fi
echo ""

# 3단계: 에이전트 런타임 스택 삭제(가능한 범위에서 시도)
AGENT_STACK="AgentCore-PrivateIdpPingAgent-default"
if aws cloudformation describe-stacks --stack-name "$AGENT_STACK" &>/dev/null; then
    echo "Deleting agent runtime stack ($AGENT_STACK)..."
    aws cloudformation delete-stack --stack-name "$AGENT_STACK"
    echo "  Waiting for stack deletion..."
    aws cloudformation wait stack-delete-complete --stack-name "$AGENT_STACK"
    echo "  Agent runtime stack deleted."
else
    echo "Agent runtime stack ($AGENT_STACK) not found (skipping)."
fi
echo ""

# 4단계: PrivateIdpLatticeStack이 있으면 삭제
if aws cloudformation describe-stacks --stack-name PrivateIdpLatticeStack &>/dev/null; then
    echo "Destroying PrivateIdpLatticeStack..."
    uv run cdk destroy PrivateIdpLatticeStack --force
fi

# 5단계: PrivateIdpGatewayInfraStack 삭제
if aws cloudformation describe-stacks --stack-name PrivateIdpGatewayInfraStack &>/dev/null; then
    echo "Destroying PrivateIdpGatewayInfraStack..."
    uv run cdk destroy PrivateIdpGatewayInfraStack --force
fi

# 6단계: PrivateIdpPingFederateStack 삭제
echo "Destroying PrivateIdpPingFederateStack..."
uv run cdk destroy PrivateIdpPingFederateStack --force

# 7단계: PrivateIdpVpcStack 삭제 시도(Lattice ENI가 아직 해제되지 않았다면 실패할 수 있음)
echo "Destroying PrivateIdpVpcStack..."
if uv run cdk destroy PrivateIdpVpcStack --force; then
    echo ""
    echo "=========================================="
    echo "Cleanup complete!"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "PrivateIdpVpcStack deletion failed"
    echo "=========================================="
    echo ""
    echo "VPC Lattice ENIs can take up to 8 hours to be released by AWS."
    echo "Wait and retry with: uv run cdk destroy PrivateIdpVpcStack --force"
    echo ""
    echo "To check ENI status:"
    echo "  VPC_ID=\$(aws cloudformation describe-stacks --stack-name PrivateIdpVpcStack \\"
    echo "      --query 'Stacks[0].Outputs[?OutputKey==\`VpcId\`].OutputValue' --output text)"
    echo "  aws ec2 describe-network-interfaces --filters Name=vpc-id,Values=\$VPC_ID"
    exit 1
fi
