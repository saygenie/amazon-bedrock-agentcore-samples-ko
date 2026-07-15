"""
고객 query 도구 - Gateway용 모의 데이터베이스 query API

이 도구는 query 문자열을 받아 모의 고객 데이터를 반환하는 데이터베이스 query
인터페이스를 시뮬레이션합니다. 적절한 입력 정제 없이 실제 데이터베이스를 사용할 때
발생할 수 있는 동작을 보여 줍니다.

이 도구는 자연어, SQL 또는 기타 형식의 모든 query 문자열을 허용합니다.
Gateway 요청 인터셉터는 query 매개변수가 이 도구에 도달하기 전에 분석하여
SQL Injection을 방지합니다.

주의: Gateway 요청 인터셉터로 보호하지 않으면 이 도구는 SQL Injection에 취약합니다.

참고: 실제 데이터베이스를 사용하지 않는 모의 도구입니다. 인프라 설정 없이 보안
패턴을 시연할 수 있도록 시뮬레이션 데이터를 반환합니다.
"""

import json
import random


def lambda_handler(event, context):
    """
    고객 query 도구의 Lambda 핸들러입니다.

    예상 입력:
    {
        "query": "Show me customer with ID 12345"
    }

    데이터베이스 query 결과를 시뮬레이션한 모의 고객 데이터를 반환합니다.
    """
    print(f"Customer query tool received event: {json.dumps(event)}")

    # 입력 파싱
    body = event if isinstance(event, dict) else json.loads(event)
    query = body.get("query", None)

    if not query:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "tool": "customer_query_tool",
                    "error": "query parameter is required",
                    "success": False,
                }
            ),
        }

    print(f"Processing query: {query}")

    # 모의 고객 데이터 생성
    # 실제 구현에서는 다음을 실행: SELECT * FROM customers WHERE {query}
    # 적절히 정제하지 않으면 SQL Injection에 취약함

    customer_ids = [12345, 67890, 11111, 22222, 33333]
    first_names = ["Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry"]
    last_names = [
        "Smith",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Garcia",
        "Miller",
        "Davis",
    ]
    cities = [
        "Boston",
        "Seattle",
        "Austin",
        "Denver",
        "Portland",
        "Chicago",
        "New York",
        "San Francisco",
    ]

    # 모의 고객 레코드 1~3개 생성
    num_results = random.randint(1, 3)
    customers = []

    for _ in range(num_results):
        customer = {
            "customer_id": random.choice(customer_ids),
            "name": f"{random.choice(first_names)} {random.choice(last_names)}",
            "email": f"{random.choice(first_names).lower()}.{random.choice(last_names).lower()}@example.com",
            "city": random.choice(cities),
            "account_status": random.choice(["Active", "Inactive", "Pending"]),
            "total_orders": random.randint(0, 50),
            "lifetime_value": round(random.uniform(100, 10000), 2),
        }
        customers.append(customer)

    response = {
        "statusCode": 200,
        "body": {
            "tool": "customer_query_tool",
            "query": query,
            "data_source": "mock_database",
            "results": customers,
            "result_count": len(customers),
            "success": True,
            "note": "This is simulated data. In production, this would query a real database. The Gateway interceptor protects against SQL injection attacks.",
        },
    }

    print(f"Returning {len(customers)} customer records")
    return response


# Gateway 등록용 MCP 도구 정의
TOOL_DEFINITION = {
    "name": "customer_query_tool",
    "description": "Query customer database. Accepts query string parameter. Protected by Gateway interceptor against SQL injection attacks. Note: Uses mock data for demonstration.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Query string to search customers (e.g., 'Show me customer with ID 12345' or 'SELECT * FROM customers WHERE id = 12345')",
            }
        },
        "required": ["query"],
    },
}


if __name__ == "__main__":
    # 로컬에서 도구 테스트
    test_queries = [
        {"query": "Show me customer with ID 12345"},
        {"query": "Find customers in Boston"},
        {"query": "Get customer email for John Smith"},
        {},  # query 누락 테스트
    ]

    for test_event in test_queries:
        print(f"\n{'=' * 60}")
        print(f"Testing with: {test_event}")
        print(f"{'=' * 60}")
        result = lambda_handler(test_event, None)
        print(f"\nTest result:\n{json.dumps(result, indent=2)}")
