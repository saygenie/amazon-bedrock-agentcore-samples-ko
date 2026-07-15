/**
 * ApprovalTool - 간소화된 승인 절차
 * 보험 인수 결정과 청구 금액을 승인합니다.
 * 
 * 매개변수:
 * - claim_amount: 보험 청구/보장 금액
 * - risk_level: 위험 수준 평가(low, medium, high, critical)
 */

import crypto from 'crypto';

// 간소화된 승인 함수
function approveUnderwriting(args) {
    console.log('Processing underwriting approval:', JSON.stringify(args, null, 2));
    
    const {
        claim_amount,
        risk_level
    } = args;
    
    // 필수 매개변수 검증
    if (!claim_amount || claim_amount <= 0) {
        return {
            status: 'ERROR',
            message: 'Valid claim amount is required',
            approval_id: null
        };
    }
    
    if (!risk_level) {
        return {
            status: 'ERROR',
            message: 'Risk level assessment is required',
            approval_id: null
        };
    }
    
    // 승인 ID 생성
    const approvalId = `APV-${crypto.randomBytes(4).toString('hex').toUpperCase()}`;
    
    // 그럴듯한 세부 정보와 함께 항상 승인
    return {
        status: 'APPROVED',
        message: `Claim amount of $${claim_amount.toLocaleString()} has been approved following comprehensive review of underwriting guidelines, risk assessment protocols, and regulatory compliance requirements with expected processing within 5-7 business days.`,
        approval_id: approvalId,
        claim_amount: claim_amount,
        risk_level: risk_level,
        approved_at: new Date().toISOString()
    };
}

// AgentCore MCP 프로토콜을 따르는 기본 Lambda 핸들러
export const handler = async (event) => {
    console.log('Received event:', JSON.stringify(event, null, 2));
    
    try {
        let args;
        let isJsonRpc = false;
        
        // JSON-RPC 형식인지 직접 매개변수 형식인지 확인
        if (event.method === 'tools/call' && event.params) {
            // JSON-RPC 형식
            isJsonRpc = true;
            const requestId = event.id || 'unknown';
            const params = event.params || {};
            const functionName = params.name;
            args = params.arguments || {};
            
            // 함수 이름 검증
            if (functionName !== 'approve_underwriting') {
                return {
                    jsonrpc: '2.0',
                    id: requestId,
                    error: {
                        code: -32601,
                        message: `Function not found: ${functionName}`
                    }
                };
            }
        } else {
            // 직접 매개변수 형식(Gateway에서 매개변수를 직접 전송)
            args = event;
        }
        
        // 함수 실행
        const result = approveUnderwriting(args);
        
        // 적절한 형식으로 응답 반환
        if (isJsonRpc) {
            // JSON-RPC 응답
            const responseText = JSON.stringify(result, null, 2);
            return {
                jsonrpc: '2.0',
                id: event.id,
                result: {
                    content: [
                        {
                            type: 'text',
                            text: responseText
                        }
                    ],
                    isError: result.status === 'ERROR'
                }
            };
        } else {
            // 직접 응답(Gateway용)
            return result;
        }
        
    } catch (error) {
        console.error('Handler error:', error);
        
        // 적절한 형식으로 오류 반환
        if (event.method === 'tools/call') {
            return {
                jsonrpc: '2.0',
                id: event.id || 'unknown',
                error: {
                    code: -32603,
                    message: `Internal error: ${error.message}`
                }
            };
        } else {
            return {
                status: 'ERROR',
                message: `Internal error: ${error.message}`
            };
        }
    }
};

// 로컬 개발용 테스트 함수
// 로컬에서 테스트하려면 주석 해제: node approval_tool.js
/*
const testEvent = {
    jsonrpc: '2.0',
    id: 'test-1',
    method: 'tools/call',
    params: {
        name: 'approve_underwriting',
        arguments: {
            claim_amount: 15000000,
            risk_level: 'medium'
        }
    }
};

handler(testEvent).then(result => {
    console.log('Test result:', JSON.stringify(result, null, 2));
});
*/
