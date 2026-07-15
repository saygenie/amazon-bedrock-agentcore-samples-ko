import boto3
import json
from datetime import datetime
from botocore.exceptions import ClientError
import logging
import re

# 로거 설정
logging.basicConfig(
    format="[%(asctime)s] p%(process)s {%(filename)s:%(lineno)d} %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# DynamoDB 리소스 초기화
dynamodb = boto3.resource("dynamodb")
smm_client = boto3.client("ssm")

# Parameter Store에서 보증 테이블 이름 가져오기
warranty_table = smm_client.get_parameter(
    Name="/app/customersupport/dynamodb/warranty_table_name", WithDecryption=False
)
warranty_table_name = warranty_table["Parameter"]["Value"]


def ensure_warranty_table_exists():
    """DynamoDB 보증 테이블이 없으면 생성한다."""
    try:
        table = dynamodb.Table(warranty_table_name)
        table.load()
        return table
    except ClientError as e:
        raise e


def validate_serial_number(serial_number: str) -> bool:
    """일련번호 형식을 검증한다."""
    pattern = r"^[A-Z0-9]{8,20}$"
    return bool(re.match(pattern, serial_number.upper()))


def calculate_days_remaining(end_date: str) -> int:
    """보증 만료일까지 남은 일수를 계산한다."""
    try:
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
        today = datetime.now()
        delta = end_date_obj - today
        return delta.days
    except ValueError:
        return 0


def get_warranty_status_text(days_remaining: int) -> str:
    """남은 일수에 따른 보증 상태 텍스트를 가져온다."""
    if days_remaining > 30:
        return "✅ Active"
    elif days_remaining > 0:
        return "⚠️ Expiring Soon"
    else:
        return "❌ Expired"


def check_warranty_status(serial_number: str, customer_email: str = None) -> str:
    """
    일련 번호를 사용하여 제품의 보증 상태를 확인한다.

    인수:
        serial_number (str): 제품 일련 번호(영숫자 8~20자).
        customer_email (str, optional): 확인에 사용할 고객 이메일.

    반환값:
        str: 보증 범위와 만료일을 포함해 형식화된 보증 상태 정보.

    예외:
        ValueError: 일련 번호 형식이 잘못된 경우.
        ClientError: DynamoDB 작업에 문제가 있는 경우.
    """
    logger.info(
        json.dumps(
            {
                "serial_number": serial_number,
                "customer_email": customer_email,
                "timestamp": datetime.now().isoformat(),
            },
            indent=2,
            default=str,
        )
    )

    if not validate_serial_number(serial_number):
        raise ValueError("Serial number must be 8-20 alphanumeric characters")

    serial_number = serial_number.upper()

    try:
        table = ensure_warranty_table_exists()

        response = table.get_item(Key={"serial_number": serial_number})

        if "Item" not in response:
            not_found_response = [
                "❌ Warranty Not Found",
                "====================",
                f"🔍 Serial Number: {serial_number}",
                "",
                "This serial number was not found in our warranty database.",
                "Please verify the serial number and try again.",
                "",
                "If you believe this is an error, please contact our support team",
                "with your purchase receipt for assistance.",
            ]
            return "\n".join(not_found_response)

        warranty_item = response["Item"]

        # 보증 정보 추출
        product_name = warranty_item.get("product_name", "Unknown Product")
        purchase_date = warranty_item.get("purchase_date", "Unknown")
        warranty_end_date = warranty_item.get("warranty_end_date", "Unknown")
        warranty_type = warranty_item.get("warranty_type", "Standard")
        customer_name = warranty_item.get("customer_name", "Unknown")
        coverage_details = warranty_item.get("coverage_details", "Standard coverage applies")

        # 남은 일수 계산
        days_remaining = calculate_days_remaining(warranty_end_date) if warranty_end_date != "Unknown" else 0
        status_text = get_warranty_status_text(days_remaining)

        # 보증 정보 형식 지정
        warranty_info = [
            "🛡️ Warranty Status Information",
            "===============================",
            f"📱 Product: {product_name}",
            f"🔢 Serial Number: {serial_number}",
            f"👤 Customer: {customer_name}",
            f"📅 Purchase Date: {purchase_date}",
            f"⏰ Warranty End Date: {warranty_end_date}",
            f"📋 Warranty Type: {warranty_type}",
            f"🔍 Status: {status_text}",
            "",
        ]

        # 남은 일수 정보 추가
        if days_remaining > 0:
            warranty_info.append(f"📆 Days Remaining: {days_remaining} days")
        elif days_remaining == 0:
            warranty_info.append("📆 Warranty expires today!")
        else:
            warranty_info.append(f"📆 Expired {abs(days_remaining)} days ago")

        warranty_info.extend(["", "🔧 Coverage Details:", f"   {coverage_details}", ""])

        # 상태에 따른 권장 사항 추가
        if days_remaining > 30:
            warranty_info.append("✨ Your warranty is active. Contact support for any issues.")
        elif days_remaining > 0:
            warranty_info.extend(
                [
                    "⚠️  Your warranty is expiring soon!",
                    "   Consider purchasing extended warranty coverage.",
                ]
            )
        else:
            warranty_info.extend(
                [
                    "❌ Your warranty has expired.",
                    "   Extended warranty options may be available.",
                    "   Contact support for repair service pricing.",
                ]
            )

        logger.info(json.dumps(warranty_item, indent=2, default=str))
        return "\n".join(warranty_info)

    except ClientError as e:
        logger.error("DynamoDB Error:", e)
        raise Exception(f"Failed to check warranty status: {e.response['Error']['Message']}")
    except Exception as e:
        logger.error("Unexpected Error:", str(e))
        raise Exception(f"Failed to check warranty status: {str(e)}")
