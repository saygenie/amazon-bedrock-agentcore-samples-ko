"""
AWS Systems Manager Parameter Store 추상화 계층
Workshop 파라미터의 모든 읽기/쓰기 작업을 처리합니다.

여러 AWS 계정과 리전에서 배포 값을 저장하고 가져오는 간결한 인터페이스를 제공합니다.
"""

import boto3
from lab_helpers.constants import PARAMETER_PATHS
from lab_helpers.config import AWS_REGION as DEFAULT_AWS_REGION


# SSM 클라이언트 초기화(필요하면 호출별로 리전 지정)
def get_ssm_client(region_name=None):
    """지정된 리전의 SSM 클라이언트를 가져오며 기본값은 config의 AWS_REGION입니다."""
    if region_name:
        return boto3.client("ssm", region_name=region_name)
    return boto3.client("ssm", region_name=DEFAULT_AWS_REGION)


def put_parameter(key, value, description="", region_name=None, overwrite=True):
    """
    Parameter Store에 파라미터를 저장합니다.

    인자:
        key: 파라미터 경로(예: "/aiml301/lab-02/ecr-repository-uri")
        value: 파라미터 값(문자열)
        description: 사람이 읽을 수 있는 설명
        region_name: AWS 리전(None이면 config.py의 AWS_REGION 사용)
        overwrite: 기존 파라미터 교체 여부(기본값: True)

    반환:
        파라미터 버전
    """
    try:
        ssm = get_ssm_client(region_name)

        # 민감한 파라미터인지 확인
        sensitive_keywords = ["password", "secret", "token", "key", "credential"]
        is_sensitive = any(keyword in key.lower() for keyword in sensitive_keywords)

        # DEBUG: 파라미터 쓰기 시도 로깅
        effective_region = region_name if region_name else DEFAULT_AWS_REGION
        print("🔍 DEBUG: put_parameter() called")
        print(f"   Key: {key}")  # codeql[py/clear-text-logging-sensitive-data]
        if is_sensitive:
            print("   Value: ****")
        else:
            print(f"   Value length: {len(str(value))} chars")
        print(f"   Region: {effective_region}")
        print(f"   Overwrite: {overwrite}")

        # 파라미터가 이미 있는지 확인
        parameter_exists = False
        try:
            existing = ssm.get_parameter(Name=key)
            parameter_exists = True
            existing_value = existing["Parameter"]["Value"]
            if is_sensitive:
                print("   Existing value: ****")
            else:
                print(f"   Existing value found: {len(existing_value)} chars")
        except ssm.exceptions.ParameterNotFound:
            parameter_exists = False
            print("   Existing value: None")
        except Exception as e:
            # 확인 중 오류가 나면 put_parameter를 계속 진행하고 필요하면 실패 처리
            print(f"   Error checking existence: {e}")
            pass

        # 작업을 결정하고 피드백 제공
        if parameter_exists:
            if str(value) == existing_value:
                print("   → Action: SKIP (same value)")
                print(f"✓ Parameter already exists with same value: {key}")
                return existing["Parameter"]["Version"]  # codeql[py/clear-text-logging-sensitive-data]
            elif not overwrite:
                print("   → Action: SKIP (overwrite=False)")
                print(f"⚠ Parameter exists but overwrite=False: {key}")
                return existing["Parameter"]["Version"]  # codeql[py/clear-text-logging-sensitive-data]
            else:
                action = "UPDATED"
                print("   → Action: UPDATED")
        else:
            action = "CREATED"
            print("   → Action: CREATED")

        # 파라미터 저장
        print("   🔄 Calling ssm.put_parameter()...")
        response = ssm.put_parameter(
            Name=key,
            Value=str(value),
            Description=description,
            Type="String",
            Overwrite=overwrite,
        )
        version = response["Version"]
        print("   ✅ put_parameter() succeeded")
        print(f"   Version: {version}")
        print(f"✓ Parameter {action}: {key}")
        return version  # codeql[py/clear-text-logging-sensitive-data]
    except Exception as e:
        print(f"❌ Error storing parameter {key}: {e}")  # codeql[py/clear-text-logging-sensitive-data]
        import traceback

        print("Traceback:")
        traceback.print_exc()
        raise


def get_parameter(key, default=None, region_name=None):
    """
    Parameter Store에서 파라미터를 가져옵니다.

    인자:
        key: 파라미터 경로
        default: 파라미터를 찾지 못했을 때의 기본값
        region_name: AWS 리전(None이면 config.py의 AWS_REGION 사용)

    반환:
        파라미터 값 또는 기본값
    """
    try:
        ssm = get_ssm_client(region_name)
        response = ssm.get_parameter(Name=key, WithDecryption=True)
        return response["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        if default is not None:
            print(f"⚠ Parameter not found: {key}, using default")
            return default  # codeql[py/clear-text-logging-sensitive-data]
        else:
            effective_region = region_name if region_name else DEFAULT_AWS_REGION
            print(f"❌ Parameter not found: {key}")  # codeql[py/clear-text-logging-sensitive-data]
            print(f"   Region: {effective_region}")
            print("   Check:")
            print("     • Is this parameter stored in Parameter Store?")
            print("     • Was the prerequisite lab (Lab-01) run first?")
            print("     • Is it in a different region?")
            raise
    except Exception as e:
        effective_region = region_name if region_name else DEFAULT_AWS_REGION
        print(f"❌ Error retrieving parameter {key}: {e}")
        print(f"   Region: {effective_region}")  # codeql[py/clear-text-logging-sensitive-data]
        raise


def delete_parameter(key, region_name=None):
    """
    Parameter Store에서 파라미터를 삭제합니다.

    인자:
        key: 파라미터 경로
        region_name: AWS 리전(None이면 기본값 사용)
    """
    try:
        ssm = get_ssm_client(region_name)
        ssm.delete_parameter(Name=key)
        print(f"✓ Deleted parameter: {key}")
    except ssm.exceptions.ParameterNotFound:
        print(f"⚠ Parameter not found: {key}")
    except Exception as e:
        print(f"❌ Error deleting parameter {key}: {e}")
        raise


def get_parameters_by_path(path_prefix, region_name=None, recursive=True):
    """
    경로 접두사 아래의 모든 파라미터를 가져옵니다.

    인자:
        path_prefix: 파라미터 경로 접두사(예: "/aiml301/lab-02")
        region_name: AWS 리전(None이면 기본값 사용)
        recursive: 모든 하위 경로 포함 여부

    반환:
        {parameter_name: value} 딕셔너리
    """
    try:
        ssm = get_ssm_client(region_name)
        parameters = {}
        paginator = ssm.get_paginator("get_parameters_by_path")

        for page in paginator.paginate(Path=path_prefix, Recursive=recursive, WithDecryption=True):
            for param in page.get("Parameters", []):
                param_name = param["Name"].split("/")[-1]  # 경로의 마지막 부분 가져오기
                parameters[param_name] = param["Value"]

        return parameters
    except Exception as e:
        print(f"❌ Error retrieving parameters from {path_prefix}: {e}")
        raise


def delete_parameters_by_path(path_prefix, region_name=None, recursive=True):
    """
    경로 접두사 아래의 모든 파라미터를 삭제합니다.

    인자:
        path_prefix: 파라미터 경로 접두사
        region_name: AWS 리전(None이면 기본값 사용)
        recursive: 모든 하위 경로 포함 여부
    """
    try:
        ssm = get_ssm_client(region_name)  # noqa: F841
        params = get_parameters_by_path(path_prefix, region_name, recursive)

        for param_name in params.keys():
            full_path = f"{path_prefix}/{param_name}".replace("//", "/")
            delete_parameter(full_path, region_name)

        print(f"✓ Cleaned up {len(params)} parameters under {path_prefix}")
    except Exception as e:
        print(f"❌ Error during cleanup: {e}")
        raise


# 일반 작업용 편의 함수


def store_workshop_metadata(account_id, region, region_name=None):
    """Workshop 수준 메타데이터를 저장합니다."""
    put_parameter(
        PARAMETER_PATHS["workshop"]["account_id"],
        account_id,
        description="AWS Account ID for this workshop deployment",
        region_name=region_name,
    )
    put_parameter(
        PARAMETER_PATHS["workshop"]["region"],
        region,
        description="AWS Region for this workshop deployment",
        region_name=region_name,
    )


def get_lab_02_config(region_name=None):
    """Parameter Store에서 Lab 02 구성을 모두 가져옵니다."""
    return get_parameters_by_path("/aiml301/lab-02", region_name=region_name, recursive=False)


def get_lab_03_config(region_name=None):
    """Parameter Store에서 Lab 03 구성을 모두 가져옵니다."""
    return get_parameters_by_path("/aiml301/lab-03", region_name=region_name, recursive=False)


def get_all_workshop_parameters(region_name=None):
    """모든 Workshop 파라미터를 가져옵니다."""
    return get_parameters_by_path("/aiml301", region_name=region_name, recursive=True)


def check_lab_prerequisites(lab_number, region_name=None):
    """
    Lab 사전 요구 사항을 사용할 수 있는지 확인합니다.

    인자:
        lab_number: Lab 번호(1, 2, 3 등)
        region_name: AWS 리전(None이면 config.py의 AWS_REGION 사용)

    반환:
        'ready'(bool)와 'missing'(누락된 파라미터 목록)이 포함된 딕셔너리
    """
    prerequisites = {
        1: [],  # Lab-01에는 사전 요구 사항 없음
        2: [PARAMETER_PATHS["cognito"]["user_pool_id"]],  # Lab-02에는 Lab-01의 Cognito가 필요
        3: [  # Lab-03에는 Lab-01의 Cognito와 선택적으로 Lab-02가 필요
            PARAMETER_PATHS["cognito"]["user_pool_id"],
            PARAMETER_PATHS["cognito"]["m2m_client_id"],
            PARAMETER_PATHS["cognito"]["user_auth_client_id"],
        ],
        4: [PARAMETER_PATHS["cognito"]["user_pool_id"]],  # Lab-04에는 Cognito가 필요
    }

    required_params = prerequisites.get(lab_number, [])
    missing = []

    for param_path in required_params:
        try:
            get_parameter(param_path, region_name=region_name)
        except Exception:
            missing.append(param_path)

    return {
        "ready": len(missing) == 0,
        "missing": missing,
        "lab": lab_number,
        "required": required_params,
    }
