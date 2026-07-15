/**
 * RiskModelTool - 간소화된 위험 모델
 * 위험 점수 산정 모델을 호출하고 평가 결과를 반환합니다.
 * 
 * 매개변수:
 * - API_classification: API 분류(public, internal, restricted)
 * - data_governance_approval: 데이터 거버넌스의 모델 사용 승인 여부
 */

import crypto from 'crypto';

// 간소화된 위험 모델 함수
function invokeRiskModel(args) {
    console.log('Processing risk model invocation:', JSON.stringify(args, null, 2));
    
    const {
        API_classification,
        data_governance_approval
    } = args;
    
    // 필수 매개변수 검증
    if (!API_classification) {
        return {
            status: 'ERROR',
            message: 'API classification is required',
            risk_score: null
        };
    }
    
    if (data_governance_approval === undefined || data_governance_approval === null) {
        return {
            status: 'ERROR', 
            message: 'Data governance approval status is required',
            risk_score: null
        };
    }
    
    // 모의 위험 점수를 생성하고 간단한 응답 반환
    const riskScore = Math.floor(Math.random() * 100);
    const modelId = `MDL-${crypto.randomBytes(4).toString('hex').toUpperCase()}`;
    
    return {
        status: 'SUCCESS',
        message: `Risk assessment complete: applicant scored ${riskScore}/100 with moderate confidence based on credit history, claims frequency, and demographic factors indicating standard underwriting eligibility.`,
        model_id: modelId,
        risk_score: riskScore,
        API_classification: API_classification,
        governance_approved: data_governance_approval,
        executed_at: new Date().toISOString()
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
            if (functionName !== 'invoke_risk_model') {
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
        const result = invokeRiskModel(args);
        
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
// 로컬에서 테스트하려면 주석 해제: node risk_model_tool.js
/*
const testEvent = {
    jsonrpc: '2.0',
    id: 'test-1',
    method: 'tools/call',
    params: {
        name: 'invoke_risk_model',
        arguments: {
            API_classification: 'internal',
            data_governance_approval: true
        }
    }
};

handler(testEvent).then(result => {
    console.log('Test result:', JSON.stringify(result, null, 2));
});
*/
