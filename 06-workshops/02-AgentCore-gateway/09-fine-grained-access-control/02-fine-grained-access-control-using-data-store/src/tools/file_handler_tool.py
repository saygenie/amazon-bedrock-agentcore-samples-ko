"""
File Handler Tool - Gateway용 모의 파일 작업 도구입니다.

이 도구는 파일 시스템 작업(list, read, write, delete)을 시뮬레이션합니다.
"""

import json
from datetime import datetime


# 모의 파일 시스템
MOCK_FILE_SYSTEM = {
    "/": {"type": "directory", "contents": ["documents", "images", "config"]},
    "/documents": {
        "type": "directory",
        "contents": ["readme.txt", "report.pdf", "notes.md"],
    },
    "/documents/readme.txt": {
        "type": "file",
        "content": "This is a sample README file with important information.",
        "size": 56,
        "created": "2024-01-15T10:30:00Z",
        "modified": "2024-03-20T14:22:00Z",
    },
    "/documents/report.pdf": {
        "type": "file",
        "content": "PDF_BINARY_DATA_PLACEHOLDER",
        "size": 245678,
        "created": "2024-02-10T09:15:00Z",
        "modified": "2024-02-10T09:15:00Z",
    },
    "/documents/notes.md": {
        "type": "file",
        "content": "# Meeting Notes\n\n- Discussed project timeline\n- Reviewed requirements\n- Assigned tasks",
        "size": 95,
        "created": "2024-03-15T16:45:00Z",
        "modified": "2024-03-18T11:30:00Z",
    },
    "/images": {"type": "directory", "contents": ["logo.png", "banner.jpg"]},
    "/config": {"type": "directory", "contents": ["settings.json"]},
    "/config/settings.json": {
        "type": "file",
        "content": '{"theme": "dark", "language": "en", "notifications": true}',
        "size": 62,
        "created": "2024-01-01T00:00:00Z",
        "modified": "2024-03-01T12:00:00Z",
    },
}


def list_files(path="/"):
    """지정된 경로의 파일과 디렉터리를 나열합니다."""
    if path not in MOCK_FILE_SYSTEM:
        return None

    item = MOCK_FILE_SYSTEM[path]

    if item["type"] == "directory":
        return {
            "path": path,
            "type": "directory",
            "items": [
                {
                    "name": name,
                    "type": MOCK_FILE_SYSTEM.get(f"{path}/{name}" if path != "/" else f"/{name}", {}).get(
                        "type", "unknown"
                    ),
                }
                for name in item["contents"]
            ],
        }
    else:
        return {
            "path": path,
            "type": "file",
            "size": item["size"],
            "created": item["created"],
            "modified": item["modified"],
        }


def read_file(path):
    """지정된 경로의 파일 내용을 읽습니다."""
    if path not in MOCK_FILE_SYSTEM:
        return None

    item = MOCK_FILE_SYSTEM[path]

    if item["type"] != "file":
        return None

    return {
        "path": path,
        "type": "file",
        "content": item["content"],
        "size": item["size"],
        "encoding": "utf-8",
        "created": item["created"],
        "modified": item["modified"],
    }


def write_file(path, content):
    """파일에 내용을 씁니다(모의 작업)."""
    # 모의 파일 크기 계산
    size = len(content)

    # 모의 파일 항목 생성
    timestamp = datetime.utcnow().isoformat() + "Z"

    MOCK_FILE_SYSTEM[path] = {
        "type": "file",
        "content": content,
        "size": size,
        "created": timestamp,
        "modified": timestamp,
    }

    return {"path": path, "operation": "write", "size": size, "created": timestamp}


def delete_file(path):
    """파일을 삭제합니다(모의 작업)."""
    if path not in MOCK_FILE_SYSTEM:
        return None

    item = MOCK_FILE_SYSTEM[path]

    if item["type"] != "file":
        return None

    # 실제 구현에서는 파일을 삭제함
    # 모의 구현에서는 성공만 반환

    return {
        "path": path,
        "operation": "delete",
        "status": "success",
        "deleted_at": datetime.utcnow().isoformat() + "Z",
    }


def lambda_handler(event, context):
    """
    file handler tool용 Lambda 핸들러입니다.

    예상 입력:
    {
        "operation": "list" | "read" | "write" | "delete",
        "path": "/path/to/file",
        "content": "file content" (for write operation)
    }

    파일 작업 결과를 반환합니다.
    """
    print(f"File handler tool received event: {json.dumps(event)}")

        # 입력 파싱
    body = event if isinstance(event, dict) else json.loads(event)
    operation = body.get("operation", "").lower()
    path = body.get("path", "/")
    content = body.get("content", "")

        # operation 검증
    valid_operations = ["list", "read", "write", "delete"]

    if operation not in valid_operations:
        return {
            "statusCode": 400,
            "body": json.dumps(
                {
                    "tool": "file_handler_tool",
                    "error": f"Invalid operation: {operation}. Valid operations: {valid_operations}",
                    "success": False,
                }
            ),
        }

    try:
        result = None

        if operation == "list":
            result = list_files(path)
            if result is None:
                raise ValueError(f"Path not found: {path}")

        elif operation == "read":
            result = read_file(path)
            if result is None:
                raise ValueError(f"File not found or is not a file: {path}")

        elif operation == "write":
            if not content:
                raise ValueError("Content is required for write operation")
            result = write_file(path, content)

        elif operation == "delete":
            result = delete_file(path)
            if result is None:
                raise ValueError(f"File not found or cannot be deleted: {path}")

        file_result = {
            "operation": operation,
            "path": path,
            "result": result,
            "timestamp": datetime.utcnow().isoformat(),
        }

        response = {
            "statusCode": 200,
            "body": json.dumps({"tool": "file_handler_tool", "result": file_result, "success": True}),
        }

        print(f"File handler operation '{operation}' completed successfully")
        return response

    except ValueError as e:
        return {
            "statusCode": 400,
            "body": json.dumps({"tool": "file_handler_tool", "error": str(e), "success": False}),
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps(
                {
                    "tool": "file_handler_tool",
                    "error": f"File operation error: {str(e)}",
                    "success": False,
                }
            ),
        }


# Gateway 등록용 MCP Tool Definition
TOOL_DEFINITION = {
    "name": "file_handler_tool",
    "description": "Perform file system operations: list directories, read files, write files, and delete files.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "description": "The file operation to perform: 'list', 'read', 'write', or 'delete'",
            },
            "path": {
                "type": "string",
                "description": "File or directory path (e.g., '/documents/readme.txt')",
            },
            "content": {
                "type": "string",
                "description": "File content (required for write operation)",
            },
        },
        "required": ["operation", "path"],
    },
}


if __name__ == "__main__":
# 로컬에서 도구 테스트
    test_cases = [
        {"operation": "list", "path": "/"},
        {"operation": "list", "path": "/documents"},
        {"operation": "read", "path": "/documents/readme.txt"},
        {"operation": "read", "path": "/config/settings.json"},
        {
            "operation": "write",
            "path": "/documents/new_file.txt",
            "content": "This is new content",
        },
        {"operation": "delete", "path": "/documents/readme.txt"},
    ]

    for i, test_event in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"Test Case {i}: {test_event}")
        print(f"{'=' * 80}")
        result = lambda_handler(test_event, None)
        print(f"{json.dumps(result, indent=2)}")
