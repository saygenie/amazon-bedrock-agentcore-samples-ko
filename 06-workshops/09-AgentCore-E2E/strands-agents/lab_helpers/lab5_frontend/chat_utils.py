import json
import os
import re
from typing import Any, Dict

import boto3
import yaml


def get_ssm_parameter(name: str, with_decryption: bool = True) -> str:
    ssm = boto3.client("ssm")

    response = ssm.get_parameter(Name=name, WithDecryption=with_decryption)

    return response["Parameter"]["Value"]


def put_ssm_parameter(name: str, value: str, parameter_type: str = "String", with_encryption: bool = False) -> None:
    ssm = boto3.client("ssm")

    put_params = {
        "Name": name,
        "Value": value,
        "Type": parameter_type,
        "Overwrite": True,
    }

    if with_encryption:
        put_params["Type"] = "SecureString"

    ssm.put_parameter(**put_params)


def delete_ssm_parameter(name: str) -> None:
    ssm = boto3.client("ssm")
    try:
        ssm.delete_parameter(Name=name)
    except ssm.exceptions.ParameterNotFound:
        pass


def load_api_spec(file_path: str) -> list:
    with open(file_path, "r") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Expected a list in the JSON file")
    return data


def get_aws_region() -> str:
    session = boto3.session.Session()
    return session.region_name


def get_aws_account_id() -> str:
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Account"]


def get_cognito_client_secret() -> str:
    client = boto3.client("cognito-idp")
    response = client.describe_user_pool_client(
        UserPoolId=get_ssm_parameter("/app/customersupport/agentcore/pool_id"),
        ClientId=get_ssm_parameter("/app/customersupport/agentcore/client_id"),
    )
    return response["UserPoolClient"]["ClientSecret"]


def read_config(file_path: str) -> Dict[str, Any]:
    """
    파일 경로에서 설정을 읽는다. JSON, YAML 및 YML 형식을 지원한다.

    인수:
        file_path (str): 설정 파일 경로

    반환:
        Dict[str, Any]: 딕셔너리 형태의 설정 데이터

    예외:
        FileNotFoundError: 파일이 없는 경우
        ValueError: 파일 형식이 지원되지 않거나 유효하지 않은 경우
        yaml.YAMLError: YAML 파싱에 실패한 경우
        json.JSONDecodeError: JSON 파싱에 실패한 경우
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Configuration file not found: {file_path}")

    # 형식을 판별하기 위해 파일 확장자 가져오기
    _, ext = os.path.splitext(file_path.lower())

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            if ext == ".json":
                return json.load(file)
            elif ext in [".yaml", ".yml"]:
                return yaml.safe_load(file)
            else:
                # JSON을 먼저 시도한 다음 YAML을 시도하여 형식 자동 감지
                content = file.read()
                file.seek(0)

                # JSON 먼저 시도
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    # YAML 시도
                    try:
                        return yaml.safe_load(content)
                    except yaml.YAMLError:
                        raise ValueError(
                            f"Unsupported configuration file format: {ext}. Supported formats: .json, .yaml, .yml"
                        )

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in configuration file {file_path}: {e}")
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in configuration file {file_path}: {e}")
    except Exception as e:
        raise ValueError(f"Error reading configuration file {file_path}: {e}")


def make_urls_clickable(text):
    """텍스트의 URL을 클릭할 수 있는 HTML 링크로 변환한다."""
    url_pattern = r"https?://(?:[-\w.])+(?:\:[0-9]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:\#(?:[\w.])*)?)?"

    def replace_url(match):
        url = match.group(0)
        return f'<a href="{url}" target="_blank" style="color:#4fc3f7;text-decoration:underline;">{url}</a>'

    return re.sub(url_pattern, replace_url, text)


def create_safe_markdown_text(text, message_placeholder):
    """적절한 인코딩과 줄 바꿈 처리를 적용한 안전한 Markdown 텍스트를 생성한다."""
    # 안전을 위해 먼저 인코딩 및 디코딩
    safe_text = text.encode("utf-16", "surrogatepass").decode("utf-16")

    # 올바르게 렌더링되도록 줄 바꿈을 HTML 줄 바꿈으로 변환
    # 실제 줄 바꿈과 남아 있는 이스케이프된 줄 바꿈을 모두 처리함
    safe_text = safe_text.replace("\n", "<br>")
    safe_text = safe_text.replace("\\n", "<br>")

    message_placeholder.markdown(safe_text, unsafe_allow_html=True)
