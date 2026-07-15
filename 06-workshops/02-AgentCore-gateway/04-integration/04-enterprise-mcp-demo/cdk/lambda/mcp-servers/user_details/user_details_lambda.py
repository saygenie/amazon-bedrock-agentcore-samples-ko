# Lambda 함수에서 컨텍스트 속성에 접근
def lambda_handler(event, context):
    print(event)
    print(context)
# 표시되는 도구 이름에는 target 이름이 접두사로 포함되므로 이 구분자로 접두사를 제거할 수 있음
    delimiter = "___"

# 컨텍스트에서 도구 이름 가져오기
    originalToolName = context.client_context.custom["bedrockAgentCoreToolName"]
    tool_name = originalToolName[originalToolName.index(delimiter) + len(delimiter) :]

# 다른 컨텍스트 속성 가져오기
    _message_version = context.client_context.custom["bedrockAgentCoreMessageVersion"]
    _aws_request_id = context.client_context.custom["bedrockAgentCoreAwsRequestId"]
    _mcp_message_id = context.client_context.custom["bedrockAgentCoreMcpMessageId"]
    _gateway_id = context.client_context.custom["bedrockAgentCoreGatewayId"]
    target_id = context.client_context.custom["bedrockAgentCoreTargetId"]

# 도구 이름에 따라 요청 처리
    if tool_name == "get_user_email":
# get_user_email 도구 처리
        print("Processing get_user_email tool")
        user_id = event.get("userId", target_id)
        print(f"User ID: {user_id}")
        return f"User email for user {user_id} retrieved! Email: john.doe@example.com"
    elif tool_name == "get_user_cc_number":
# get_user_cc_number 도구 처리
        print("Processing get_user_cc_number tool")
        user_id = event.get("userId", target_id)
        print(f"User ID: {user_id}")
        return f"User credit card number for user {user_id} retrieved! CC Number: 1234-5678-9012-3456"
    else:
# 알 수 없는 도구 처리
        pass
