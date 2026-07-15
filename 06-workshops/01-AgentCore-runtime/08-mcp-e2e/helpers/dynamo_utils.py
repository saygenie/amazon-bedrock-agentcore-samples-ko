import boto3
from datetime import datetime
from typing import Dict, List
from decimal import Decimal


class FinanceDB:
    def __init__(self, table_name: str = "finance_tracker", region_name: str = "us-east-1"):
        self.dynamodb = boto3.resource("dynamodb", region_name=region_name)
        self.table_name = table_name
        self.table = self.dynamodb.Table(table_name)

    def create_table(self) -> str:
        """Finance tracker table이 없으면 생성합니다."""
        try:
            # Table이 이미 있는지 확인
            self.table.load()
            return f"Table {self.table_name} already exists"
        except self.dynamodb.meta.client.exceptions.ResourceNotFoundException:
            # Table이 없으므로 생성
            try:
                table = self.dynamodb.create_table(
                    TableName=self.table_name,
                    KeySchema=[
                        {"AttributeName": "pk", "KeyType": "HASH"},
                        {"AttributeName": "sk", "KeyType": "RANGE"},
                    ],
                    AttributeDefinitions=[
                        {"AttributeName": "pk", "AttributeType": "S"},
                        {"AttributeName": "sk", "AttributeType": "S"},
                    ],
                    BillingMode="PAY_PER_REQUEST",
                )
                table.wait_until_exists()
                return f"Table {self.table_name} created successfully"
            except Exception as e:
                return f"Error creating table: {str(e)}"
        except Exception as e:
            return f"Error checking table: {str(e)}"

    def delete_table(self) -> str:
        """Finance tracker table을 삭제합니다."""
        try:
            self.table.delete()
            self.table.wait_until_not_exists()
            return f"Table {self.table_name} deleted successfully"
        except Exception as e:
            return f"Error deleting table: {str(e)}"

    def add_transaction(
        self,
        user_alias: str,
        transaction_type: str,
        amount: float,
        description: str,
        category: str,
    ) -> str:
        """DynamoDB에 transaction을 추가합니다."""
        item = {
            "pk": f"USER#{user_alias}",
            "sk": f"TRANSACTION#{datetime.now().isoformat()}",
            "type": transaction_type,
            "amount": Decimal(str(amount)),  # float를 Decimal로 변환
            "description": description,
            "category": category,
            "date": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
        }

        self.table.put_item(Item=item)
        return f"{transaction_type.title()} of ${abs(amount):.2f} added for {user_alias}"

    def set_budget(self, user_alias: str, category: str, monthly_limit: float) -> str:
        """Category의 budget을 설정합니다."""
        item = {
            "pk": f"USER#{user_alias}",
            "sk": f"BUDGET#{category}",
            "category": category,
            "monthly_limit": Decimal(str(monthly_limit)),  # float를 Decimal로 변환
            "set_date": datetime.now().isoformat(),
        }

        self.table.put_item(Item=item)
        return f"Budget set for {category}: ${monthly_limit:.2f}/month"

    def get_transactions(self, user_alias: str) -> List[Dict]:
        """사용자의 모든 transaction을 가져옵니다."""
        response = self.table.query(
            KeyConditionExpression="pk = :pk AND begins_with(sk, :sk)",
            ExpressionAttributeValues={
                ":pk": f"USER#{user_alias}",
                ":sk": "TRANSACTION#",
            },
        )
        return response.get("Items", [])

    def get_budgets(self, user_alias: str) -> List[Dict]:
        """사용자의 모든 budget을 가져옵니다."""
        response = self.table.query(
            KeyConditionExpression="pk = :pk AND begins_with(sk, :sk)",
            ExpressionAttributeValues={":pk": f"USER#{user_alias}", ":sk": "BUDGET#"},
        )
        return response.get("Items", [])

    def get_balance(self, user_alias: str) -> Dict:
        """Transaction에서 balance를 계산합니다."""
        transactions = self.get_transactions(user_alias)

        total = sum(float(t["amount"]) for t in transactions)  # Decimal을 float로 변환
        income = sum(float(t["amount"]) for t in transactions if t["type"] == "income")
        expenses = sum(abs(float(t["amount"])) for t in transactions if t["type"] == "expense")

        return {"balance": total, "income": income, "expenses": expenses}
