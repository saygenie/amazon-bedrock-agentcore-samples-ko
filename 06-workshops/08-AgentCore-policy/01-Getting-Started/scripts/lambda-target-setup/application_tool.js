/**
 * ApplicationTool - 간소화된 신청서 생성
 * 신청자 지역과 보장 금액을 사용해 보험 신청서를 생성합니다.
 * 
 * 매개변수:
 * - applicant_region: 고객의 지역
 * - coverage_amount: 요청한 보험 보장 금액
 */

import crypto from 'crypto';

// 간소화된 신청서 생성 함수
function createApplication(args) {
    console.log('Processing application creation:', JSON.stringify(args, null, 2));
    
    const {
        applicant_region,
        coverage_amount
    } = args;
    
    // 필수 매개변수 검증
    if (!applicant_region) {
        return {
            status: 'ERROR',
            message: 'Applicant region is required',
            application_id: null
        };
    }
    
    if (!coverage_amount || coverage_amount <= 0) {
        return {
            status: 'ERROR',
            message: 'Coverage amount must be positive',
            application_id: null
        };
    }
    
    // 신청서 ID 생성
    const applicationId = `APP-${applicant_region}-${crypto.randomBytes(4).toString('hex').toUpperCase()}`;
    
    // 제공된 값과 함께 항상 성공 메시지 반환
    return {
        status: 'SUCCESS',
        message: `Application has been successfully created for applicant region ${applicant_region} and coverage amount $${coverage_amount.toLocaleString()}`,
        application_id: applicationId,
        coverage_amount: coverage_amount,
        region: applicant_region,
        created_at: new Date().toISOString()
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
            if (functionName !== 'create_application') {
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
        const result = createApplication(args);
        
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
// 로컬에서 테스트하려면 주석 해제: node application_tool.js
/*
const testEvent = {
    jsonrpc: '2.0',
    id: 'test-1',
    method: 'tools/call',
    params: {
        name: 'create_application',
        arguments: {
            applicant_region: 'US',
            coverage_amount: 2000000
        }
    }
};

handler(testEvent).then(result => {
    console.log('Test result:', JSON.stringify(result, null, 2));
});
*/
