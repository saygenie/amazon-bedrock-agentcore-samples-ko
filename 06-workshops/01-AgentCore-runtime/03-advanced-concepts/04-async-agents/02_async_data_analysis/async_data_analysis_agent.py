# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import re
import os
import time
import json
import boto3
import logging
import threading
import tempfile
import html
import ast
import concurrent.futures
import atexit

from strands import Agent, tool
from strands.models import BedrockModel
from bedrock_agentcore.runtime import BedrockAgentCoreApp


def sanitize_task_id(task_id):
    # 영숫자와 하이픈만 허용
    if not re.match(r"^[a-zA-Z0-9\-]+$", str(task_id)):
        raise ValueError("Invalid task_id format")
    return str(task_id)


def validate_prompt_with_guardrails(prompt: str, region: str = "us-east-2") -> bool:
    """
    Amazon Bedrock Guardrails Standard Tier를 사용해 사용자 prompt를 검증합니다.

    인자:
        prompt: 검증할 사용자 입력 prompt
        region: Amazon Bedrock 서비스의 AWS 리전

    반환:
        bool: prompt가 안전하면 True, 차단되면 False
    """
    try:
        import boto3

        bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)

        # 코드 도메인 보호를 위해 Standard Tier의 Amazon Bedrock Guardrails 적용
        guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID", "async-data-analysis-code-safety")

        response = bedrock_runtime.apply_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion="DRAFT",
            source="INPUT",
            content=[{"text": {"text": prompt}}],
        )

        # Guardrail이 콘텐츠를 차단했는지 확인
        if response["action"] == "GUARDRAIL_INTERVENED":
            outputs = response.get("outputs", [])
            blocked_categories = []
            for output in outputs:
                if "type" in output:
                    blocked_categories.append(output["type"])

            logging.warning(f"Prompt blocked by Bedrock Guardrails: {blocked_categories}")
            return False

        logging.info("Prompt passed Bedrock Guardrails validation")
        return True

    except Exception as e:
        logging.warning(f"Bedrock Guardrails validation failed: {e}")
        # 정상적인 분석을 위해 장애 허용 방식 적용 - 서비스 오류로 차단하지 않음
        return True


def validate_generated_code_with_guardrails(code: str, region: str = "us-east-2") -> bool:
    """
    Amazon Bedrock Guardrails Standard Tier를 사용해 생성된 코드를 검증합니다.
    코드 도메인 보호를 위해 특별히 설계되었습니다.

    인자:
        code: 검증할 Python 코드
        region: Amazon Bedrock 서비스의 AWS 리전

    반환:
        bool: 코드가 안전하면 True, 위험하면 False
    """
    try:
        import boto3

        bedrock_runtime = boto3.client("bedrock-runtime", region_name=region)

        # 생성된 코드에 Amazon Bedrock Guardrails 적용
        guardrail_id = os.environ.get("BEDROCK_GUARDRAIL_ID", "async-data-analysis-code-safety")

        response = bedrock_runtime.apply_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion="DRAFT",
            source="OUTPUT",  # 모델 출력(생성된 코드) 검증
            content=[{"text": {"text": code}}],
        )

        # 코드가 차단되었는지 확인
        if response["action"] == "GUARDRAIL_INTERVENED":
            outputs = response.get("outputs", [])
            blocked_reasons = []
            for output in outputs:
                if "type" in output:
                    blocked_reasons.append(output["type"])

            logging.warning(f"Generated code blocked by Bedrock Guardrails: {blocked_reasons}")
            return False

        logging.info("Generated code passed Bedrock Guardrails validation")
        return True

    except Exception as e:
        logging.warning(f"Code validation with Bedrock Guardrails failed: {e}")
        # 장애 허용 방식 적용 - Guardrails 서비스를 사용할 수 없으면 실행 허용
        return True


def validate_s3_bucket_access(bucket_name: str) -> bool:
    """
    S3 버킷 소유권과 접근 권한을 검증합니다.

    인자:
        bucket_name: 검증할 S3 버킷 이름

    반환:
        bool: 현재 계정이 소유하고 접근할 수 있는 버킷이면 True

    예외:
        ValueError: 버킷 접근이 거부되거나 버킷이 존재하지 않는 경우
    """
    try:
        import boto3

        s3_client = boto3.client("s3")

        # 버킷 위치 조회를 시도해 버킷 소유권 확인
        s3_client.get_bucket_location(Bucket=bucket_name)

        # 필요한 권한이 있는지 확인
        s3_client.head_bucket(Bucket=bucket_name)

        return True
    except Exception as e:
        raise ValueError(f"S3 bucket access denied or bucket doesn't exist: {bucket_name}. Error: {e}")


os.environ["BYPASS_TOOL_CONSENT"] = "true"

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler()],
)
logging.getLogger("strands.multiagent").setLevel(logging.DEBUG)

# 적절한 동기화와 함께 스레드 풀 사용
# 환경 변수로 스레드 풀 크기를 구성할 수 있도록 설정
THREAD_POOL_SIZE = int(os.environ.get("ASYNC_TASK_THREAD_POOL_SIZE", "5"))
executor = concurrent.futures.ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE)
lock = threading.Lock()


# 정리 핸들러 등록
def cleanup_executor():
    logging.info("Shutting down thread pool executor...")
    executor.shutdown(wait=True)
    logging.info("Thread pool executor shut down complete")


atexit.register(cleanup_executor)

# 코드 보안 검증
DANGEROUS_IMPORTS = {
    "os",
    "subprocess",
    "sys",
    "shutil",
    "glob",
    "pathlib",
    "socket",
    "urllib",
    "requests",
    "http",
    "ftplib",
    "smtplib",
    "eval",
    "exec",
    "__import__",
    "compile",
    "open",
}

ALLOWED_IMPORTS = {
    "pandas",
    "numpy",
    "matplotlib",
    "seaborn",
    "json",
    "math",
    "datetime",
    "time",
    "random",
    "statistics",
    "csv",
    "re",
}

DANGEROUS_PATTERNS = [
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__\s*\(",
    r"open\s*\(",
    r"file\s*\(",
    r"input\s*\(",
    r"raw_input\s*\(",
    r"compile\s*\(",
    r"getattr\s*\(",
    r"setattr\s*\(",
    r"delattr\s*\(",
    r"globals\s*\(",
    r"locals\s*\(",
    r"vars\s*\(",
    r"dir\s*\(",
]


def validate_generated_code(code: str) -> tuple[bool, str]:
    """코드에 보안 문제가 있는지 검증합니다."""
    try:
        # 위험한 패턴 확인
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                return False, f"Dangerous function detected: {pattern}"

        # import를 확인하기 위해 AST 파싱
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in DANGEROUS_IMPORTS:
                            return False, f"Dangerous import blocked: {alias.name}"
                        if alias.name not in ALLOWED_IMPORTS:
                            return False, f"Import not in whitelist: {alias.name}"

                elif isinstance(node, ast.ImportFrom):
                    if node.module in DANGEROUS_IMPORTS:
                        return False, f"Dangerous module import blocked: {node.module}"
                    if node.module and node.module not in ALLOWED_IMPORTS:
                        return False, f"Module not in whitelist: {node.module}"

        except SyntaxError:
            return False, "Code contains syntax errors"

        return True, ""

    except Exception as e:
        logging.error(f"Code validation error: {e}")
        return False, f"Validation failed: {str(e)}"


# 모델 초기화
sonnet = BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0")

haiku = BedrockModel(model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")


class CodeInterpreterClient:
    """Amazon Bedrock AgentCore CodeInterpreter용 직접 boto3 클라이언트입니다."""

    def __init__(self, region="us-east-1"):
        self.client = boto3.client(
            "bedrock-agentcore",
            region_name=region,
            endpoint_url=f"https://bedrock-agentcore.{region}.amazonaws.com",
        )
        self.session_id = None
        self._start_session()

    def _start_session(self):
        """새 CodeInterpreter 세션을 시작합니다."""
        try:
            response = self.client.start_code_interpreter_session(
                codeInterpreterIdentifier="aws.codeinterpreter.v1",
                name=f"analysis-session-{int(time.time())}",
                sessionTimeoutSeconds=3600,
            )
            self.session_id = response["sessionId"]
            logging.info(f"Started CodeInterpreter session: {self.session_id}")
        except Exception as e:
            logging.error(f"Failed to start CodeInterpreter session: {e}")
            raise

    def execute_code(self, code: str) -> str:
        """Python 코드를 실행하고 결과를 반환합니다."""
        if not self.session_id:
            raise RuntimeError("No active session")

        response = self.client.invoke_code_interpreter(
            codeInterpreterIdentifier="aws.codeinterpreter.v1",
            sessionId=self.session_id,
            name="executeCode",
            arguments={"language": "python", "code": code},
        )

        # 이벤트 스트림 응답 처리
        result_text = ""
        for event in response.get("stream", []):
            if "result" in event:
                result = event["result"]
                if "content" in result:
                    for content_item in result["content"]:
                        if content_item["type"] == "text":
                            result_text += content_item["text"]

        return result_text or str(response)


app = BedrockAgentCoreApp()


# ============================================================================
# SYSTEM PROMPT
# ============================================================================

CODING_AGENT_SYSTEM_PROMPT = """
You are a Python code generator. Generate ONLY executable Python code with NO
markdown formatting.

CRITICAL RULES:
- Output raw Python code ONLY - no ```python blocks, no explanations, no
  comments outside the code
- The data file 'data.csv' is ALREADY AVAILABLE in the current directory -
  DO NOT try to download it from S3
- ALWAYS start by reading the data: df = pd.read_csv('data.csv')
- DO NOT use boto3 or try to access S3 - the data is already local
- Use print() statements to output all results, analysis, and reports
- Import all required libraries (pandas, numpy, etc.) at the top of your code
- Format output clearly with labels and structure using print statements

EXAMPLE OUTPUT FORMAT:
import pandas as pd
import numpy as np

# Read the data that's already available
df = pd.read_csv('data.csv')

print("Dataset Overview:")
print(f"Rows: {len(df)}, Columns: {len(df.columns)}")
print()

print("Analysis Results:")
result = df.groupby('product')['price'].mean()
print(result.to_string())

IMPORTANT: DO NOT import boto3 or try to read from S3. The data is already
in 'data.csv'.
"""

PRIMARY_AGENT_SYSTEM_PROMPT = """
You are a helpful assistant. You receive a request from the user and answer  and answer immediately
if it is a generic question, or route to a background function async_analysis_task.
If you route to the background function, reply to the user mentioning that the task is running and you can answer other questions, do not wait for the results.
Tell the user the task id when routing to background function. While tasks run, you remain available.
to help the user. You can check task status and retrieve results when user asks for it.
"""

# ============================================================================
# S3 유틸리티 함수
# ============================================================================


def extract_s3_uri_from_text(text: str) -> str:
    """
    정규식을 사용해 텍스트에서 S3 URI를 추출합니다.

    인자:
        text: S3 URI가 포함될 수 있는 텍스트

    반환:
        str: 찾은 경우 S3 URI, 그렇지 않으면 None
    """
    if not text:
        return None

    # S3 URI 일치: s3://bucket/path/file.ext
    # 버킷 이름, 경로 및 확장자가 있는 파일 캡처
    pattern = r"s3://[a-zA-Z0-9\-_]+/[a-zA-Z0-9\-_/]+\.[a-zA-Z0-9]+"
    match = re.search(pattern, text)

    return match.group(0) if match else None


def parse_s3_uri(s3_uri: str) -> tuple:
    """
    S3 URI를 버킷과 키 구성 요소로 파싱합니다.

    인자:
        s3_uri: s3://bucket-name/path/to/file 형식의 S3 URI

    반환:
        tuple: (bucket, key), 유효하지 않으면 (None, None)
    """
    if not s3_uri or not s3_uri.startswith("s3://"):
        return None, None

    s3_path = s3_uri[5:]  # 's3://' 제거
    parts = s3_path.split("/", 1)

    if len(parts) < 2:
        return None, None

    bucket = parts[0]
    key = parts[1]

    return bucket, key


def build_s3_output_uri(s3_input_uri: str, task_id: str) -> str:
    """
    입력 URI와 작업 ID를 기반으로 S3 출력 URI를 구성합니다.
    입력과 같은 버킷 및 디렉터리를 사용하되 파일 이름을 변경합니다.

    인자:
        s3_input_uri: 입력 S3 URI
        task_id: 작업 식별자

    반환:
        str: 작업 결과 파일 이름이 포함된 출력 S3 URI
    """
    if not s3_input_uri:
        return None

    bucket, key = parse_s3_uri(s3_input_uri)
    if not bucket or not key:
        return None

    safe_task_id = sanitize_task_id(task_id)
    safe_bucket = html.escape(str(bucket))

    # 입력 키에서 디렉터리 경로 가져오기
    path_parts = key.rsplit("/", 1)
    if len(path_parts) > 1:
        output_prefix = path_parts[0]
        safe_output_prefix = html.escape(str(output_prefix))
        return f"s3://{safe_bucket}/{safe_output_prefix}/task_{safe_task_id}_result.json"
    else:
        return f"s3://{safe_bucket}/task_{safe_task_id}_result.json"


def upload_to_s3(local_file: str, s3_uri: str, task_id: str = None) -> bool:
    """
    로컬 파일을 S3에 업로드합니다.

    인자:
        local_file: 로컬 파일 경로
        s3_uri: 대상 S3 URI
        task_id: 로깅에 사용할 선택적 작업 ID

    반환:
        bool: 성공하면 True, 그렇지 않으면 False
    """
    try:
        import boto3

        bucket, key = parse_s3_uri(s3_uri)
        if not bucket or not key:
            log_prefix = f"[BACKGROUND] Task {task_id} - " if task_id else ""
            logging.warning(f"{log_prefix}Invalid S3 URI format: {s3_uri}")
            return False

        # 업로드 전에 버킷 접근 검증
        validate_s3_bucket_access(bucket)

        s3_client = boto3.client("s3")
        s3_client.upload_file(local_file, bucket, key)

        log_prefix = f"[BACKGROUND] Task {task_id} - " if task_id else ""
        logging.info(f"{log_prefix}Successfully uploaded to S3: {s3_uri}")
        return True

    except Exception as e:
        log_prefix = f"[BACKGROUND] Task {task_id} - " if task_id else ""
        logging.error(f"{log_prefix}S3 upload failed: {e}")
        return False


@tool(
    name="async_analysis_task",
    description=(
        "Execute Python code asynchronously for data analysis tasks. "
        "Automatically detects S3 URIs in the request, downloads data, "
        "executes code in Code Interpreter, and saves results back to S3 "
        "in the same location."
    ),
)
def async_analysis_task(request: str):
    """
    Write and execute Python code asynchronously for data analysis tasks.

    This tool:
    1. Automatically detects S3 URIs in your request
    2. Downloads the data and loads it into a Code Interpreter session as 'data.csv'
    3. Generates Python code based on your request
    4. Executes the code in an isolated Code Interpreter environment
    5. Saves results locally and to S3 (same bucket/path as input, different filename)

    Args:
        request: A clear description of the data analysis task. Include the S3 URI of your data
                 if you want to load and analyze it. Be specific about what analysis to perform.

                 Examples:
                 - "Load data from s3://my-bucket/data/sales.csv and calculate average price by product"
                 - "Using s3://my-bucket/reports/data.csv, find the top 5 products by revenue"
                 - "Write code that generates the first 20 prime numbers" (no S3 data needed)

    Returns:
        str: Confirmation message with task ID and S3 output location (if applicable)

    Notes:
        - If an S3 URI is detected, results are automatically saved to the same S3 location
          with filename: task_{task_id}_result.json
        - Results are always saved locally to /tmp/task_{task_id}_result.json
        - Use get_task_results(task_id) to retrieve completed results
    """

    # 요청에 S3 입력 URI가 있으면 추출
    s3_input_uri = extract_s3_uri_from_text(request)
    if s3_input_uri:
        logging.info(f"[ASYNC_TASK] Detected S3 input URI: {s3_input_uri}")

    logging.info(f"[ASYNC_TASK] Starting async task for request: {request}")

    # 잠금을 사용해 적절한 스레드 안전성 구현
    with lock:
        task_id = app.add_async_task("async_analysis_task")
        logging.info(f"[ASYNC_TASK] Created task with ID: {task_id}")

    # 입력과 같은 경로를 사용해 S3 출력 URI 구성(파일 이름만 변경)
    s3_output_uri = build_s3_output_uri(s3_input_uri, str(task_id))
    if s3_output_uri:
        logging.info(f"[ASYNC_TASK] Will save results to: {s3_output_uri}")

    # 원시 스레드를 생성하는 대신 스레드 풀에 제출
    try:
        executor.submit(_run_async_analysis_task, request, task_id, s3_input_uri, s3_output_uri)
        logging.info(f"[ASYNC_TASK] Task {task_id} submitted to thread pool")
    except Exception as e:
        logging.error(f"[ASYNC_TASK] Failed to submit task {task_id} to thread pool: {e}")
        raise

    response = f"Code writing started in the background. Task ID: {task_id}. Results will be available in the future."
    if s3_output_uri:
        response += f" Results will also be saved to {s3_output_uri}"
    return response


def _extract_text_from_stream(response) -> str:
    """Code Interpreter 스트리밍 응답에서 텍스트 콘텐츠를 추출하는 헬퍼입니다."""
    output_parts = []
    error_parts = []

    for event in response.get("stream", []):
        if "result" in event:
            result = event["result"]
            if "content" in result:
                for content_item in result["content"]:
                    if content_item.get("type") == "text":
                        output_parts.append(content_item["text"])

        # 오류 이벤트도 캡처
        if "error" in event:
            error_parts.append(str(event["error"]))

    # 출력과 오류 결합
    all_output = "\n".join(output_parts)
    if error_parts:
        all_output += "\n\nERRORS:\n" + "\n".join(error_parts)

    return all_output


def _has_execution_error(result: str) -> bool:
    """코드 실행 결과에 오류가 포함되어 있는지 확인합니다."""
    error_indicators = ("Traceback", "Error", "Exception")
    return any(indicator in result for indicator in error_indicators)


def _has_execution_error(result: str) -> bool:
    """실행 결과에 오류 표시가 포함되어 있는지 확인합니다."""
    error_indicators = [
        "Traceback",
        "Error:",
        "Exception:",
        "SyntaxError",
        "NameError",
        "TypeError",
    ]
    return any(indicator in str(result) for indicator in error_indicators)


def _build_retry_prompt(request: str, error_context: str) -> str:
    """오류 컨텍스트가 포함된 상세 재시도 prompt를 구성합니다."""
    return (
        f"Your previous code failed with this error:\n\n"
        f"ERROR OUTPUT:\n{error_context}\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Carefully read the error message above\n"
        f"2. Identify what went wrong (missing import, wrong column name, syntax error, etc.)\n"
        f"3. Fix the specific issue\n"
        f"4. Generate corrected Python code\n\n"
        f"ORIGINAL REQUEST: {request}\n\n"
        f"Generate the FIXED Python code now:"
    )


def _save_task_result(task_id: str, data: dict, s3_output_uri: str = None) -> str:
    """작업 결과를 로컬 파일에 저장하고 선택적으로 S3에 업로드합니다."""
    temp_dir = tempfile.gettempdir()
    safe_task_id = sanitize_task_id(task_id)
    local_file = os.path.join(temp_dir, f"task_{safe_task_id}_result.json")
    with open(local_file, "w") as f:
        json.dump(data, f, indent=2)

    if s3_output_uri:
        logging.info(f"[BACKGROUND] Task {task_id} - Uploading result to S3: {s3_output_uri}")
        if upload_to_s3(local_file, s3_output_uri, task_id):
            data["s3_uri"] = s3_output_uri

    return local_file


def _download_s3_data(task_id: str, s3_input_uri: str, code_client) -> None:
    """S3에서 데이터를 다운로드하고 Code Interpreter 세션에 씁니다."""
    logging.info(f"[BACKGROUND] Task {task_id} - Downloading data from S3: {s3_input_uri}")
    bucket, key = parse_s3_uri(s3_input_uri)

    if not bucket or not key:
        raise ValueError(f"Invalid S3 URI: {s3_input_uri}")

    # 다운로드 전에 버킷 접근 검증
    validate_s3_bucket_access(bucket)

    s3_client = boto3.client("s3")
    response = s3_client.get_object(Bucket=bucket, Key=key)
    csv_content = response["Body"].read().decode("utf-8")

    logging.info(f"[BACKGROUND] Task {task_id} - Writing data to Code Interpreter session")

    # 코드 실행을 사용해 CSV 데이터 쓰기
    write_code = f'''
import os
with open("data.csv", "w") as f:
    f.write("""{csv_content}""")
print("Data file written successfully")
'''

    result = code_client.execute_code(write_code)
    logging.info(f"[BACKGROUND] Task {task_id} - Data write result: {result}")


def _execute_with_retry(task_id: str, request: str, coding_agent, code_client, max_retries: int = 3):
    """재시도 로직으로 코드 생성 및 실행을 수행합니다."""
    error_context = ""
    region = os.environ.get("AWS_REGION", "us-east-2")

    # 먼저 Amazon Bedrock Guardrails로 사용자 요청 검증
    if not validate_prompt_with_guardrails(request, region):
        raise Exception("Request blocked by security guardrails - potential code injection detected")

    for attempt in range(max_retries):
        # 시도 횟수에 따라 prompt 구성
        if attempt == 0:
            prompt = f"Write Python code to accomplish the following: {request}"
        else:
            prompt = _build_retry_prompt(request, error_context)
            safe_prompt = html.escape(str(prompt)[:300])
            logging.info(f"[BACKGROUND] Task {task_id} - Retry prompt preview: {safe_prompt}...")

        # 코드 생성
        logging.info(f"[BACKGROUND] Task {task_id} - Attempt {attempt + 1}/{max_retries}: Calling coding agent")
        coding_agent_response = coding_agent(prompt)
        python_code = coding_agent_response.message["content"][0]["text"]
        logging.info(f"[BACKGROUND] Task {task_id} - Code generated, length: {len(python_code)} chars")

        # Amazon Bedrock Guardrails로 생성된 코드 검증
        if not validate_generated_code_with_guardrails(python_code, region):
            error_context = "Generated code blocked by Bedrock Guardrails for security violations"
            logging.warning(f"[BACKGROUND] Task {task_id} - Code blocked by Bedrock Guardrails")

            if attempt < max_retries - 1:
                logging.info(f"[BACKGROUND] Task {task_id} - Retrying with security feedback...")
                continue
            else:
                raise Exception("Unable to generate safe code after maximum retries - blocked by Bedrock Guardrails")

        # 검증을 통과하면 코드 실행
        try:
            logging.info(f"[BACKGROUND] Task {task_id} - Executing code in secure environment")

            # 새 CodeInterpreter 클라이언트 사용
            result = code_client.execute_code(python_code)

            logging.info(f"[BACKGROUND] Task {task_id} - Execution completed successfully")

            # 실행 오류 확인
            if _has_execution_error(result):
                error_context = f"Execution error: {result}"
                logging.warning(f"[BACKGROUND] Task {task_id} - Execution failed: {result}")

                if attempt < max_retries - 1:
                    continue
                else:
                    return (
                        python_code,
                        f"Code execution failed after {max_retries} attempts: {result}",
                    )
            else:
                logging.info(f"[BACKGROUND] Task {task_id} - Code executed successfully")
                return python_code, result

        except Exception as e:
            error_context = f"Execution exception: {str(e)}"
            logging.error(f"[BACKGROUND] Task {task_id} - Execution exception: {e}")

            if attempt < max_retries - 1:
                continue
            else:
                return python_code, f"Code execution failed with exception: {str(e)}"

    return "", "Failed to generate and execute code after maximum retries"


def _mark_task_failed(task_id: str, s3_output_uri: str, error: Exception) -> None:
    """작업을 실패로 표시하고 오류 세부 정보를 저장합니다."""
    import traceback

    error_trace = traceback.format_exc()
    logging.error(f"[BACKGROUND] Task {task_id} - ERROR: {error}")
    logging.error(error_trace)

    error_data = {
        "status": "failed",
        "error": str(error),
        "traceback": error_trace,
        "task_id": task_id,
    }

    _save_task_result(task_id, error_data, s3_output_uri)

    # AgentCore에서 작업을 실패로 표시
    logging.info(f"[BACKGROUND] Task {task_id} - Marking task as failed in AgentCore")
    try:
        app.fail_async_task(task_id)
    except AttributeError:
        logging.warning(f"[BACKGROUND] Task {task_id} - fail_async_task method not available")
    except Exception as fail_error:
        logging.error(f"[BACKGROUND] Task {task_id} - Error marking as failed: {fail_error}")


def _run_async_analysis_task(request: str, task_id: str, s3_input_uri: str = None, s3_output_uri: str = None):
    """코드 생성 및 실행을 포함한 비동기 분석 작업을 수행합니다."""
    logging.info(f"[BACKGROUND] Task {task_id} - Starting execution")
    code_client = None

    try:
        # 코딩 Agent 초기화
        logging.info(f"[BACKGROUND] Task {task_id} - Creating coding agent")
        coding_agent = Agent(name="coding_agent", system_prompt=CODING_AGENT_SYSTEM_PROMPT, model=haiku)

        # 네트워크 격리를 사용하는 Secure Code Interpreter 초기화
        logging.info(f"[BACKGROUND] Task {task_id} - Initializing Secure Code Interpreter")
        region = os.environ.get("AWS_REGION", "us-west-2")

        # 입력 URI에서 허용된 S3 버킷 추출
        allowed_buckets = []
        if s3_input_uri:
            bucket, _ = parse_s3_uri(s3_input_uri)
            if bucket:
                allowed_buckets.append(bucket)

        # 직접 boto3 CodeInterpreter 클라이언트 사용
        try:
            code_client = CodeInterpreterClient(region=region)
            logging.info(f"[BACKGROUND] Task {task_id} - CodeInterpreter session started: {code_client.session_id}")

        except Exception as e:
            logging.error(f"[BACKGROUND] Task {task_id} - CodeInterpreter initialization failed: {e}")
            raise Exception(
                f"CodeInterpreter service unavailable. This service may be in preview and require AWS support to enable. Error: {e}"
            )

        # S3 입력 URI가 제공되면 데이터 파일 다운로드 및 쓰기
        if s3_input_uri:
            _download_s3_data(task_id, s3_input_uri, code_client)

        # 재시도 로직으로 실행
        python_code, result = _execute_with_retry(task_id, request, coding_agent, code_client)

        # 결과 저장
        result_data = {
            "status": "completed",
            "task_id": task_id,
            "code": python_code,
            "result": result,
            "s3_input_uri": s3_input_uri,
        }

        _save_task_result(task_id, result_data, s3_output_uri)

        # AgentCore에서 작업을 완료로 표시
        logging.info(f"[BACKGROUND] Task {task_id} - Marking task as complete in AgentCore")
        app.complete_async_task(task_id)
        logging.info(f"[BACKGROUND] Task {task_id} - Successfully completed")

    except Exception as e:
        _mark_task_failed(task_id, s3_output_uri, e)

    finally:
        # 항상 Code Interpreter 세션 중지
        if code_client:
            try:
                code_client.stop()
                logging.info(f"[BACKGROUND] Task {task_id} - Code Interpreter session stopped")
            except Exception as e:
                logging.error(f"[BACKGROUND] Task {task_id} - Error stopping Code Interpreter: {e}")


@tool(
    name="get_task_results",
    description=(
        "Retrieve the results of a completed async analysis task using its task ID. "
        "Returns the generated code, analysis results, and status. "
        "call get_task_status function to check the status of the running task and only call this function after getting the confirmation that task is completed"
    ),
)
def get_task_results(task_id: str):
    """
    Get results of a completed task from file system.

    This function retrieves the results of an asynchronous task that was previously
    started using async_analysis_task. Results are stored as JSON files in the
    temporary directory with the naming pattern: task_{task_id}_result.json
    Args:
        task_id (str): The unique identifier of the task whose results to retrieve.
                      This ID is returned when starting a task with async_analysis_task.

    Returns:
        dict: A dictionary containing the task results.

    Notes:
        - Tasks that are still running will return a "not_found" status
        - Results files are stored locally in temp directory and may be cleaned up by the system
        - For tasks that processed S3 data, results may also be available in S3
    """
    import json
    import tempfile

    try:
        temp_dir = tempfile.gettempdir()
        safe_task_id = sanitize_task_id(task_id)
        result_file = os.path.join(temp_dir, f"task_{safe_task_id}_result.json")
        with open(result_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "status": "not_found",
            "message": f"No results found for task {task_id}. Task may still be running or hasn't started yet.",
        }
    except Exception as e:
        return {"status": "error", "message": f"Error reading results: {str(e)}"}


@tool(name="get_task_status", description=("Get the status of the running tasks"))
def get_task_status():
    """Get status of running tasks"""
    # 작업 정보 가져오기
    task_info = app.get_async_task_info()
    logging.debug(task_info)

    tasks_result = {
        "message": "Current task information",
        "task_info": task_info,
    }
    return tasks_result


# 기본 Agent 구성
primary_agent = Agent(
    name="primary_agent",
    system_prompt=PRIMARY_AGENT_SYSTEM_PROMPT,
    tools=[async_analysis_task, get_task_results, get_task_status],
    model=sonnet,
)


@app.entrypoint
def handler(payload, context):
    result = primary_agent(payload.get("prompt"))
    return {"result": result.message}


# 애플리케이션 실행
if __name__ == "__main__":
    app.run()
