"""
직원 데이터 도구 - Gateway용 모의 직원 정보 API

이 도구는 연락처 및 위치 PII를 포함한 모의 직원 정보를 제공합니다.
주의: 이 도구는 민감한 PII 데이터를 처리하므로 접근을 제한해야 합니다.
"""

import json
import random


def lambda_handler(event, context):
    """
    직원 데이터 도구의 Lambda 핸들러입니다.

    예상 입력:
    {
        "employee_id": "EMP-98765"
    }

    PII(이메일, 주소)가 포함된 모의 직원 데이터를 반환합니다.
    """
    print(f"Employee data tool received event: {json.dumps(event)}")

    # 입력 파싱
    body = event if isinstance(event, dict) else json.loads(event)
    employee_id = body.get("employee_id", None)

    if not employee_id:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "tool": "employee_data_tool",
                    "error": "employee_id is required",
                    "success": False,
                }
            ),
        }

    # 모의 직원 데이터 생성
    # 필드 이름에는 민감도가 드러나지 않지만 콘텐츠에는 PII가 포함됨
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
    departments = [
        "Engineering",
        "Marketing",
        "Sales",
        "Operations",
        "Finance",
        "Human Resources",
    ]
    cities = ["Boston", "Seattle", "Austin", "Denver", "Portland", "Chicago"]
    streets = [
        "Oak Avenue",
        "Maple Street",
        "Pine Road",
        "Elm Drive",
        "Cedar Lane",
        "Birch Way",
    ]

    first_name = random.choice(first_names)
    last_name = random.choice(last_names)
    department = random.choice(departments)
    city = random.choice(cities)
    street = random.choice(streets)

    # 민감한 필드 2개와 민감하지 않은 필드 3개가 포함된 직원 데이터 생성
    employee_data = {
        # 민감하지 않음: 비즈니스 식별자
        "employee_id": employee_id,
        # 민감하지 않음: 조직 정보
        "department": department,
        # 민감함: 필드 이름에는 드러나지 않지만 이메일이 포함됨
        # EMAIL - Guardrails에서 탐지하여 익명화
        "contact_info": f"{first_name.lower()}.{last_name.lower()}@company.com",
        # 민감함: 필드 이름에는 직접 드러나지 않지만 주소가 포함됨
        # ADDRESS - 필드 이름이 아닌 콘텐츠를 기반으로 Guardrails에서 탐지하여 익명화
        "mailing_info": f"{random.randint(100, 9999)} {street}, {city}, MA {random.randint(10000, 99999)}",
        # 민감하지 않음: 고용 상태
        "status": random.choice(["Active", "On Leave", "Remote"]),
        "financial_info": {
            # 민감함 - Guardrails에서 마스킹
            # US_BANK_ACCOUNT_NUMBER - Guardrails에서 탐지
            "bank_account": f"{random.randint(100000000, 999999999)}",
            # US_BANK_ROUTING_NUMBER - Guardrails에서 탐지
            "routing_number": f"{random.randint(100000000, 999999999)}",
            # CREDIT_DEBIT_CARD_NUMBER - Guardrails에서 탐지
            "credit_card": f"{random.randint(4000, 4999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}",
            # CREDIT_DEBIT_CARD_CVV - Guardrails에서 탐지
            "cvv": f"{random.randint(100, 999)}",
            # CREDIT_DEBIT_CARD_EXPIRY - Guardrails에서 탐지
            "card_expiry": f"{random.randint(1, 12):02d}/{random.randint(25, 30)}",
            # PIN - Guardrails에서 탐지
            "pin": f"{random.randint(1000, 9999)}",
            # US_INDIVIDUAL_TAX_IDENTIFICATION_NUMBER - Guardrails에서 탐지
            "tax_id": f"{random.randint(900, 999)}-{random.randint(70, 99)}-{random.randint(1000, 9999)}",
            # 민감하지 않음 - 마스킹하지 않음
            "account_balance": round(random.uniform(1000, 50000), 2),
            "credit_score": random.randint(600, 850),
            "currency": "USD",
            "payment_terms": random.choice(["Net 30", "Net 60", "Immediate"]),
            "credit_limit": round(random.uniform(5000, 50000), 2),
            "available_credit": round(random.uniform(1000, 25000), 2),
        },
    }

    response = {
        "statusCode": 200,
        "body": {
            "tool": "employee_data_tool",
            "result": employee_data,
            "success": True,
            "note": "Sensitive fields (contact_info, mailing_info) will be anonymized by Bedrock Guardrails based on content, not field names.",
        },
    }

    print("Employee data tool response generated")
    return response


# Gateway 등록용 MCP 도구 정의
TOOL_DEFINITION = {
    "name": "employee_data_tool",
    "description": "Retrieve employee information by Employee ID. Returns employee record with contact and location information. Sensitive data will be automatically anonymized by Bedrock Guardrails.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "The unique employee identifier (e.g., 'EMP-98765')",
            }
        },
        "required": ["employee_id"],
    },
}


if __name__ == "__main__":
    # 로컬에서 도구 테스트
    test_events = [
        {"employee_id": "EMP-98765"},
        {"employee_id": "EMP-12345"},
        {},  # employee_id 누락 테스트
    ]

    for test_event in test_events:
        print(f"\n{'=' * 60}")
        print(f"Testing with: {test_event}")
        print(f"{'=' * 60}")
        result = lambda_handler(test_event, None)
        print(f"\nTest result:\n{json.dumps(result, indent=2)}")  # codeql[py/clear-text-logging-sensitive-data]
