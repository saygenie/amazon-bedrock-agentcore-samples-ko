"""
Lab 2 테스트용 모의 데이터 생성기
인프라를 배포하지 않고도 현실적인 CloudWatch 로그와 지표를 제공합니다.
"""

import datetime
import random

# EC2 애플리케이션 로그 - 정상 작업과 오류 혼합
EC2_APPLICATION_LOGS = [
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).timestamp() * 1000
        ),
        "message": "2024-11-03T14:55:00.123Z [INFO] Application started successfully",
        "logStreamName": "ec2-app-stream",
        "eventId": "1",
    },
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=4)).timestamp() * 1000
        ),
        "message": "2024-11-03T14:56:00.456Z [INFO] Database connection pool initialized. Size: 10",
        "logStreamName": "ec2-app-stream",
        "eventId": "2",
    },
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=3)).timestamp() * 1000
        ),
        "message": "2024-11-03T14:57:00.789Z [ERROR] Failed to connect to DynamoDB. Connection timeout after 30s",
        "logStreamName": "ec2-app-stream",
        "eventId": "3",
    },
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=2)).timestamp() * 1000
        ),
        "message": "2024-11-03T14:58:00.234Z [WARN] Retrying DynamoDB connection. Attempt 2/5",
        "logStreamName": "ec2-app-stream",
        "eventId": "4",
    },
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).timestamp() * 1000
        ),
        "message": "2024-11-03T14:59:00.567Z [ERROR] Connection attempt 3 failed. Response time: 45000ms (threshold: 30000ms)",
        "logStreamName": "ec2-app-stream",
        "eventId": "5",
    },
    {
        "timestamp": int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000),
        "message": "2024-11-03T15:00:00.890Z [CRITICAL] Multiple connection failures detected. Circuit breaker activated.",
        "logStreamName": "ec2-app-stream",
        "eventId": "6",
    },
]

# NGINX 접근/오류 로그 - 성공 및 오류 요청 혼합
NGINX_LOGS = [
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).timestamp() * 1000
        ),
        "message": '192.168.1.100 - - [03/Nov/2024:14:55:00 +0000] "GET /api/customers HTTP/1.1" 200 1245 "-" "Mozilla/5.0"',
        "logStreamName": "nginx-access",
        "eventId": "1",
    },
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=4)).timestamp() * 1000
        ),
        "message": '192.168.1.101 - - [03/Nov/2024:14:56:00 +0000] "POST /api/orders HTTP/1.1" 201 534 "-" "REST-Client"',
        "logStreamName": "nginx-access",
        "eventId": "2",
    },
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=3)).timestamp() * 1000
        ),
        "message": '192.168.1.102 - - [03/Nov/2024:14:57:00 +0000] "GET /api/customers HTTP/1.1" 502 162 "-" "Mozilla/5.0"',
        "logStreamName": "nginx-error",
        "eventId": "3",
    },
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=2)).timestamp() * 1000
        ),
        "message": "2024/11/03 14:58:00 [error] 1234#0: *567 upstream timed out (110: Connection timed out) while connecting to upstream",
        "logStreamName": "nginx-error",
        "eventId": "4",
    },
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).timestamp() * 1000
        ),
        "message": '192.168.1.103 - - [03/Nov/2024:14:59:00 +0000] "GET /health HTTP/1.1" 503 0 "-" "HealthChecker"',
        "logStreamName": "nginx-access",
        "eventId": "5",
    },
    {
        "timestamp": int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000),
        "message": "2024/11/03 15:00:00 [alert] 1234#0: worker process 5678 exited on signal 11 (core dumped)",
        "logStreamName": "nginx-error",
        "eventId": "6",
    },
]

# DynamoDB 작업 로그 - 성공 및 제한된 작업 혼합
DYNAMODB_LOGS = [
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).timestamp() * 1000
        ),
        "message": "2024-11-03T14:55:00.100Z [INFO] PutItem: table=Orders, latency=45ms, consumed_capacity=1",
        "logStreamName": "dynamodb-ops",
        "eventId": "1",
    },
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=4)).timestamp() * 1000
        ),
        "message": "2024-11-03T14:56:00.200Z [INFO] Query: table=Customers, latency=32ms, items_returned=15",
        "logStreamName": "dynamodb-ops",
        "eventId": "2",
    },
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=3)).timestamp() * 1000
        ),
        "message": "2024-11-03T14:57:00.300Z [WARN] ProvisionedThroughputExceededException: Orders table. Write capacity exceeded. Requested: 150, Available: 100",
        "logStreamName": "dynamodb-ops",
        "eventId": "3",
    },
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=2)).timestamp() * 1000
        ),
        "message": "2024-11-03T14:58:00.400Z [WARN] Batch write request throttled. Retry attempt 1/3 with exponential backoff",
        "logStreamName": "dynamodb-ops",
        "eventId": "4",
    },
    {
        "timestamp": int(
            (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).timestamp() * 1000
        ),
        "message": "2024-11-03T14:59:00.500Z [ERROR] Max retries exceeded for Orders table. Total backoff time: 5234ms",
        "logStreamName": "dynamodb-ops",
        "eventId": "5",
    },
    {
        "timestamp": int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000),
        "message": "2024-11-03T15:00:00.600Z [CRITICAL] Orders table unavailable. All operations failing with ServiceUnavailableException",
        "logStreamName": "dynamodb-ops",
        "eventId": "6",
    },
]


# CloudWatch 지표 - 현실적인 값과 급증이 포함된 CPU, Memory, Disk
def get_cpu_metrics():
    """현실적인 CPU 사용률 지표를 생성합니다."""
    now = datetime.datetime.now(datetime.timezone.utc)
    metrics = []

    # 정상 값(60~70%)
    for i in range(3):
        metrics.append(
            {
                "Timestamp": now - datetime.timedelta(minutes=(5 - i * 2)),
                "Average": 65.0 + random.uniform(-5, 5),
                "Maximum": 72.0 + random.uniform(-3, 5),
                "Minimum": 58.0 + random.uniform(-3, 3),
                "Unit": "Percent",
            }
        )

    # 급증(95% 이상)
    metrics.append(
        {
            "Timestamp": now - datetime.timedelta(minutes=1),
            "Average": 94.5,
            "Maximum": 98.2,
            "Minimum": 89.1,
            "Unit": "Percent",
        }
    )

    # 최근 급증 지속
    metrics.append(
        {
            "Timestamp": now,
            "Average": 96.8,
            "Maximum": 99.9,
            "Minimum": 91.2,
            "Unit": "Percent",
        }
    )

    return metrics


def get_memory_metrics():
    """현실적인 메모리 사용률 지표를 생성합니다."""
    now = datetime.datetime.now(datetime.timezone.utc)
    metrics = []

    # 정상 값(70~80%)
    for i in range(3):
        metrics.append(
            {
                "Timestamp": now - datetime.timedelta(minutes=(5 - i * 2)),
                "Average": 75.0 + random.uniform(-3, 4),
                "Maximum": 82.0 + random.uniform(-2, 4),
                "Minimum": 68.0 + random.uniform(-2, 3),
                "Unit": "Percent",
            }
        )

    # 상승(85% 이상)
    metrics.append(
        {
            "Timestamp": now - datetime.timedelta(minutes=1),
            "Average": 87.5,
            "Maximum": 92.1,
            "Minimum": 81.3,
            "Unit": "Percent",
        }
    )

    # 높은 메모리 사용률
    metrics.append(
        {
            "Timestamp": now,
            "Average": 89.2,
            "Maximum": 94.8,
            "Minimum": 83.5,
            "Unit": "Percent",
        }
    )

    return metrics


def get_disk_metrics():
    """현실적인 디스크 사용률 지표를 생성합니다."""
    now = datetime.datetime.now(datetime.timezone.utc)
    metrics = []

    # 정상 값(45~55%)
    for i in range(5):
        metrics.append(
            {
                "Timestamp": now - datetime.timedelta(minutes=(5 - i)),
                "Average": 50.0 + random.uniform(-3, 3),
                "Maximum": 55.0 + random.uniform(-2, 3),
                "Minimum": 45.0 + random.uniform(-2, 2),
                "Unit": "Percent",
            }
        )

    return metrics


# Public API 함수
def get_ec2_logs():
    """모의 EC2 애플리케이션 로그를 반환합니다."""
    return EC2_APPLICATION_LOGS


def get_nginx_logs():
    """모의 NGINX 로그를 반환합니다."""
    return NGINX_LOGS


def get_dynamodb_logs():
    """모의 DynamoDB 작업 로그를 반환합니다."""
    return DYNAMODB_LOGS


def get_metrics(metric_name="CPUUtilization"):
    """지표 이름에 따라 모의 지표를 반환합니다."""
    if metric_name == "CPUUtilization":
        return get_cpu_metrics()
    elif metric_name == "MemoryUtilization":
        return get_memory_metrics()
    elif metric_name == "DiskUtilization":
        return get_disk_metrics()
    else:
        return []
