"""
AWS 서비스 및 기타 공통 작업을 위한 유틸리티 함수입니다.
"""

import boto3
import json
from typing import Optional, Dict, Any
from botocore.exceptions import ClientError, NoCredentialsError


def get_ssm_parameter(
    parameter_name: str,
    decrypt: bool = True,
    region_name: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None,
) -> Optional[str]:
    """
    AWS Systems Manager Parameter Store에서 파라미터 값을 가져옵니다.

    인수:
        parameter_name (str): 가져올 파라미터 이름
        decrypt (bool): SecureString 파라미터의 복호화 여부(기본값: True)
        region_name (str, optional): AWS 리전 이름
        aws_access_key_id (str, optional): AWS 액세스 키 ID
        aws_secret_access_key (str, optional): AWS 보안 액세스 키
        aws_session_token (str, optional): AWS 세션 토큰

    반환:
        str: 파라미터 값. 찾지 못했거나 오류가 발생하면 None

    예외:
        NoCredentialsError: AWS 자격 증명이 구성되지 않은 경우
        ClientError: AWS 서비스 오류가 발생한 경우
    """
    try:
        # 선택적 자격 증명으로 SSM 클라이언트 생성
        session_kwargs = {}
        if region_name:
            session_kwargs["region_name"] = region_name
        if aws_access_key_id:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
        if aws_secret_access_key:
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key
        if aws_session_token:
            session_kwargs["aws_session_token"] = aws_session_token

        ssm_client = boto3.client("ssm", **session_kwargs)

        # 파라미터 가져오기
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=decrypt)

        return response["Parameter"]["Value"]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ParameterNotFound":
            print(f"Parameter '{parameter_name}' not found")
            return None
        else:
            print(f"AWS error retrieving parameter '{parameter_name}': {e}")
            raise
    except NoCredentialsError:
        print("AWS credentials not found. Please configure your credentials.")
        raise
    except Exception as e:
        print(f"Unexpected error retrieving parameter '{parameter_name}': {e}")
        return None


def get_ssm_parameters_by_path(
    parameter_path: str,
    recursive: bool = True,
    decrypt: bool = True,
    region_name: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None,
) -> Dict[str, str]:
    """
    AWS Systems Manager Parameter Store에서 경로를 기준으로 여러 파라미터를 가져옵니다.

    인수:
        parameter_path (str): 가져올 파라미터의 경로 접두사
        recursive (bool): 파라미터를 재귀적으로 가져올지 여부(기본값: True)
        decrypt (bool): SecureString 파라미터의 복호화 여부(기본값: True)
        region_name (str, optional): AWS 리전 이름
        aws_access_key_id (str, optional): AWS 액세스 키 ID
        aws_secret_access_key (str, optional): AWS 보안 액세스 키
        aws_session_token (str, optional): AWS 세션 토큰

    반환:
        Dict[str, str]: 파라미터 이름을 값에 매핑한 딕셔너리

    예외:
        NoCredentialsError: AWS 자격 증명이 구성되지 않은 경우
        ClientError: AWS 서비스 오류가 발생한 경우
    """
    try:
        # 선택적 자격 증명으로 SSM 클라이언트 생성
        session_kwargs = {}
        if region_name:
            session_kwargs["region_name"] = region_name
        if aws_access_key_id:
            session_kwargs["aws_access_key_id"] = aws_access_key_id
        if aws_secret_access_key:
            session_kwargs["aws_secret_access_key"] = aws_secret_access_key
        if aws_session_token:
            session_kwargs["aws_session_token"] = aws_session_token

        ssm_client = boto3.client("ssm", **session_kwargs)

        parameters = {}
        paginator = ssm_client.get_paginator("get_parameters_by_path")

        # 모든 파라미터를 페이지 단위로 조회
        for page in paginator.paginate(Path=parameter_path, Recursive=recursive, WithDecryption=decrypt):
            for param in page["Parameters"]:
                parameters[param["Name"]] = param["Value"]

        return parameters

    except ClientError as e:
        print(f"AWS error retrieving parameters from path '{parameter_path}': {e}")
        raise
    except NoCredentialsError:
        print("AWS credentials not found. Please configure your credentials.")
        raise
    except Exception as e:
        print(f"Unexpected error retrieving parameters from path '{parameter_path}': {e}")
        return {}


def get_ssm_parameter_as_json(
    parameter_name: str,
    decrypt: bool = True,
    region_name: Optional[str] = None,
    aws_access_key_id: Optional[str] = None,
    aws_secret_access_key: Optional[str] = None,
    aws_session_token: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    AWS Systems Manager Parameter Store에서 파라미터 값을 가져와 JSON으로 파싱합니다.

    인수:
        parameter_name (str): 가져올 파라미터 이름
        decrypt (bool): SecureString 파라미터의 복호화 여부(기본값: True)
        region_name (str, optional): AWS 리전 이름
        aws_access_key_id (str, optional): AWS 액세스 키 ID
        aws_secret_access_key (str, optional): AWS 보안 액세스 키
        aws_session_token (str, optional): AWS 세션 토큰

    반환:
        Dict[str, Any]: 파싱된 JSON 값. 찾지 못했거나 오류가 발생하면 None

    예외:
        NoCredentialsError: AWS 자격 증명이 구성되지 않은 경우
        ClientError: AWS 서비스 오류가 발생한 경우
        json.JSONDecodeError: 파라미터 값이 유효한 JSON이 아닌 경우
    """
    try:
        parameter_value = get_ssm_parameter(
            parameter_name=parameter_name,
            decrypt=decrypt,
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
        )

        if parameter_value is None:
            return None

        return json.loads(parameter_value)

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON from parameter '{parameter_name}': {e}")
        return None
    except Exception as e:
        print(f"Unexpected error retrieving JSON parameter '{parameter_name}': {e}")
        return None


# 사용 예:
if __name__ == "__main__":
    # 예제 1: 단일 파라미터 가져오기
    api_key = get_ssm_parameter("/myapp/api-key")

    # 예제 2: 경로를 기준으로 여러 파라미터 가져오기
    config_params = get_ssm_parameters_by_path("/myapp/config/")

    # 예제 3: JSON 파라미터 가져오기
    db_config = get_ssm_parameter_as_json("/myapp/database-config")
