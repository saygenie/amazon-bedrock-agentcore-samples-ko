"""
AgentCore Gateway 대상용 간단한 주문 관리 Lambda 함수다.
get_order 및 update_order 도구를 제공한다.
"""

import json


# 모의 주문 데이터베이스
ORDERS = {
    "ORD-001": {
        "orderId": "ORD-001",
        "item": "Mechanical Keyboard",
        "status": "shipped",
        "amount": 149.99,
    },
    "ORD-002": {
        "orderId": "ORD-002",
        "item": "USB-C Hub",
        "status": "processing",
        "amount": 59.99,
    },
    "ORD-003": {
        "orderId": "ORD-003",
        "item": "Monitor Stand",
        "status": "delivered",
        "amount": 89.99,
    },
}


def lambda_handler(event, context):
    """AgentCore Gateway의 도구 호출을 처리한다.

    Gateway는 context.client_context.custom['bedrockAgentCoreToolName']에 도구 이름을 전달한다.
    이벤트 본문에는 도구 인자가 직접 포함된다.
    """
    import logging

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 디버깅을 위해 원시 이벤트와 컨텍스트를 기록한다.
    logger.info(f"Event: {json.dumps(event, default=str)}")
    client_context = {}
    if context and hasattr(context, "client_context") and context.client_context:
        client_context = {
            "custom": getattr(context.client_context, "custom", None),
            "env": getattr(context.client_context, "env", None),
        }
    logger.info(f"ClientContext: {json.dumps(client_context, default=str)}")

    # AgentCore Gateway가 설정한 클라이언트 컨텍스트에서 도구 이름을 가져온다.
    tool_name = ""
    if context and hasattr(context, "client_context") and context.client_context:
        custom = getattr(context.client_context, "custom", None) or {}
        tool_name = custom.get("bedrockAgentCoreToolName", "")

    # 대체 경로: 직접 호출이나 테스트에서는 이벤트 본문의 'name' 키를 확인한다.
    if not tool_name:
        tool_name = event.get("name", "")

    logger.info(f"Resolved tool_name: {tool_name}")

    # Gateway는 도구 이름에 "{targetName}___{toolName}" 형식의 접두사를 붙인다.
    # 접두사를 제거해 순수한 도구 이름을 가져온다.
    if "___" in tool_name:
        tool_name = tool_name.split("___", 1)[1]
        logger.info(f"Stripped prefix, bare tool_name: {tool_name}")

    arguments = event.get("arguments", event)

    if tool_name == "get_order":
        order_id = arguments.get("orderId", "")
        order = ORDERS.get(order_id)
        if order:
            return {"status": "success", "result": json.dumps(order)}
        return {"status": "error", "result": f"Order {order_id} not found"}

    elif tool_name == "update_order_status":
        order_id = arguments.get("orderId", "")
        new_status = arguments.get("status", "")
        order = ORDERS.get(order_id)
        if order:
            order["status"] = new_status
            return {
                "status": "success",
                "result": json.dumps({"orderId": order_id, "newStatus": new_status}),
            }
        return {"status": "error", "result": f"Order {order_id} not found"}

    return {"status": "error", "result": f"Unknown tool: {tool_name}"}
