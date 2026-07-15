"""
Lab 02: ZIP 기반 Lambda 배포 패키저

Docker 기반 배포를 순수 Python ZIP 패키징으로 대체합니다.
SageMaker VPC 모드에서 기본적으로 작동하며 Docker 데몬이 필요하지 않습니다.

함수:
- create_deployment_package()      # 종속성을 포함한 ZIP 생성
- upload_package_to_s3()           # S3에 업로드
- create_lambda_function_from_zip() # ZIP에서 Lambda 배포
- get_package_info()                # 크기 및 내용 검증
- setup_s3_bucket()                 # S3 버킷 생성/확인
"""

import os
import sys
import zipfile
import subprocess
import shutil
from typing import Dict, Optional, Tuple
import boto3

from lab_helpers.constants import PARAMETER_PATHS, LAMBDA_CONFIG
from lab_helpers.parameter_store import put_parameter, get_parameter
from lab_helpers.config import MODEL_ID, AWS_REGION


# ============================================================================
# 유틸리티
# ============================================================================


def get_dir_size(path: str) -> int:
    """디렉터리의 전체 크기를 바이트 단위로 계산합니다."""
    total = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total += os.path.getsize(filepath)
    return total


def get_zip_size(zip_path: str) -> int:
    """압축된 ZIP 파일 크기를 바이트 단위로 반환합니다."""
    return os.path.getsize(zip_path)


def format_size(size_bytes: int) -> str:
    """바이트를 읽기 쉬운 크기 형식으로 변환합니다."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def validate_requirements(build_dir: str) -> bool:
    """빌드 디렉터리에 requirements.txt가 있는지 확인합니다."""
    req_file = os.path.join(build_dir, "requirements.txt")
    if not os.path.exists(req_file):
        print(f"❌ requirements.txt not found in {build_dir}")
        return False
    return True


# ============================================================================
# 패키지 생성
# ============================================================================


def install_dependencies(build_dir: str, requirements_content: str) -> Tuple[bool, Dict]:
    """
    pip을 사용해 lib/ 디렉터리에 종속성을 설치합니다.

    인자:
        build_dir: 종속성을 설치할 디렉터리
        requirements_content: requirements.txt의 내용

    반환:
        (success: bool, stats: 설치 정보가 포함된 dict)
    """
    print("\n📦 Installing dependencies...")

    # requirements.txt 쓰기
    req_file = os.path.join(build_dir, "requirements.txt")
    with open(req_file, "w") as f:
        f.write(requirements_content)
    print(f"✓ Wrote requirements.txt ({len(requirements_content)} bytes)")

    # lib 디렉터리 생성
    lib_dir = os.path.join(build_dir, "lib")
    os.makedirs(lib_dir, exist_ok=True)

    # 종속성 설치
    print("✓ Installing to lib/...")
    print("  Target: Python 3.11 Linux x86_64 (Lambda runtime)")
    try:
        result = subprocess.run(  # noqa: F841
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-r",
                req_file,
                "-t",
                lib_dir,
                "--upgrade",
                "--quiet",
                "--disable-pip-version-check",
                "--platform",
                "manylinux2014_x86_64",
                "--implementation",
                "cp",
                "--python-version",
                "3.11",
                "--only-binary",
                ":all:",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=300,  # 5분 제한 시간
        )

        # 패키지 수 계산
        installed_packages = [d for d in os.listdir(lib_dir) if os.path.isdir(os.path.join(lib_dir, d))]

        lib_size = get_dir_size(lib_dir)

        print(f"✓ Installed {len(installed_packages)} packages")
        print(f"  lib/ size: {format_size(lib_size)}")

        return True, {
            "packages_count": len(installed_packages),
            "lib_size": lib_size,
            "packages": installed_packages,
        }

    except subprocess.TimeoutExpired:
        print("❌ Installation timeout after 5 minutes")
        return False, {}
    except subprocess.CalledProcessError as e:
        print(f"❌ Installation failed: {e.stderr}")
        return False, {}
    except Exception as e:
        print(f"❌ Unexpected error during installation: {e}")
        return False, {}


def create_lambda_zip(build_dir: str, handler_code: str, output_zip: str) -> Tuple[bool, Dict]:
    """
    올바른 구조로 Lambda 배포 ZIP을 생성합니다.

    구조:
    ├── app.py (handler)
    ├── lab_helpers/ (utilities)
    ├── lib/ (dependencies)
    │   ├── boto3/
    │   ├── botocore/
    │   ├── strands/
    │   └── ...
    └── requirements.txt

    인자:
        build_dir: 소스 빌드 디렉터리
        handler_code: app.py용 Python 코드
        output_zip: 출력 ZIP 파일 경로

    반환:
        (success: bool, stats: dict)
    """
    print("\n📦 Creating Lambda ZIP package...")

    # app.py 쓰기
    app_py = os.path.join(build_dir, "app.py")
    with open(app_py, "w") as f:
        f.write(handler_code)
    print(f"✓ Wrote app.py ({len(handler_code)} bytes)")

    # ZIP 생성
    try:
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            total_files = 0

            # lib/ 추가(종속성)
            lib_dir = os.path.join(build_dir, "lib")
            if os.path.exists(lib_dir):
                for root, dirs, files in os.walk(lib_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, build_dir)
                        zf.write(file_path, arcname)
                        total_files += 1
                print(f"✓ Added {total_files} files from lib/")

            # lab_helpers/ 추가(유틸리티)
            lab_helpers_dir = os.path.join(build_dir, "lab_helpers")
            if os.path.exists(lab_helpers_dir):
                helpers_start = total_files
                for root, dirs, files in os.walk(lab_helpers_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, build_dir)
                        zf.write(file_path, arcname)
                        total_files += 1
                print(f"✓ Added {total_files - helpers_start} files from lab_helpers/")

            # 루트에 app.py 및 requirements.txt 추가
            zf.write(app_py, "app.py")
            req_file = os.path.join(build_dir, "requirements.txt")
            if os.path.exists(req_file):
                zf.write(req_file, "requirements.txt")
            total_files += 2
            print("✓ Added app.py and requirements.txt at root")

        zip_size = get_zip_size(output_zip)

        print(f"✓ ZIP created: {output_zip}")
        print(f"  Compressed size: {format_size(zip_size)}")
        print(f"  Total files: {total_files}")

        return True, {
            "zip_path": output_zip,
            "zip_size": zip_size,
            "total_files": total_files,
        }

    except Exception as e:
        print(f"❌ ZIP creation failed: {e}")
        return False, {}


def create_deployment_package(
    handler_code: str,
    requirements_content: str,
    build_dir: str = "lambda_diagnostic_agent_zip",
) -> Dict:
    """
    전체 워크플로: 종속성이 포함된 배포 패키지를 생성합니다.

    인자:
        handler_code: Lambda 핸들러용 Python 코드(app.py)
        requirements_content: pip 요구 사항 텍스트
        build_dir: 빌드 디렉터리 이름

    반환:
        패키지 정보 또는 오류 세부 정보가 포함된 딕셔너리
    """
    print("=" * 70)
    print("CREATING LAMBDA ZIP DEPLOYMENT PACKAGE")
    print("=" * 70)

    # 기존 빌드가 있으면 정리
    if os.path.exists(build_dir):
        print("\n🧹 Cleaning up existing build directory...")
        shutil.rmtree(build_dir)

    os.makedirs(build_dir, exist_ok=True)
    print(f"✓ Created build directory: {build_dir}")

    # 리포지토리 루트의 lab_helpers를 빌드 디렉터리로 복사
    lab_helpers_src = "lab_helpers"
    if os.path.exists(lab_helpers_src):
        lab_helpers_dest = os.path.join(build_dir, "lab_helpers")
        print("\n📂 Copying lab_helpers to build directory...")
        shutil.copytree(
            lab_helpers_src,
            lab_helpers_dest,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
        )
        print(f"✓ Copied lab_helpers/ to {build_dir}/lab_helpers/")
    else:
        print("⚠️  lab_helpers directory not found in repository root")

    # 1단계: 종속성 설치
    success, install_stats = install_dependencies(build_dir, requirements_content)
    if not success:
        return {"status": "error", "error": "Failed to install dependencies"}

    # 2단계: ZIP 생성
    output_zip = f"{build_dir}.zip"
    success, zip_stats = create_lambda_zip(build_dir, handler_code, output_zip)
    if not success:
        return {"status": "error", "error": "Failed to create ZIP"}

    # 3단계: 크기 검증
    print("\n✅ Validating package size...")
    zip_size = zip_stats["zip_size"]
    uncompressed_size = get_dir_size(build_dir)

    # Lambda 제한과 비교
    DIRECT_UPLOAD_LIMIT = 50 * 1024 * 1024  # 50 MB
    S3_UPLOAD_LIMIT = 250 * 1024 * 1024  # 250 MB
    UNCOMPRESSED_LIMIT = 250 * 1024 * 1024  # 250 MB

    size_status = "✅"
    upload_method = "direct"

    if zip_size > DIRECT_UPLOAD_LIMIT:
        upload_method = "S3"
        size_status = "⚠️"

    if zip_size > S3_UPLOAD_LIMIT or uncompressed_size > UNCOMPRESSED_LIMIT:
        return {
            "status": "error",
            "error": f"Package too large: {format_size(zip_size)} (limit: 250MB)",
            "size_compressed": zip_size,
            "size_uncompressed": uncompressed_size,
        }

    print(f"{size_status} Compressed: {format_size(zip_size)} (50 MB direct / 250 MB S3 limit)")
    print(f"✓ Uncompressed: {format_size(uncompressed_size)} (250 MB limit)")
    print(f"✓ Deployment method: {upload_method}")

    print("\n" + "=" * 70)
    print("✅ PACKAGE CREATION SUCCESSFUL")
    print("=" * 70)

    return {
        "status": "success",
        "zip_path": output_zip,
        "build_dir": build_dir,
        "size_compressed": zip_size,
        "size_uncompressed": uncompressed_size,
        "size_formatted": format_size(zip_size),
        "upload_method": upload_method,
        "install_stats": install_stats,
        "zip_stats": zip_stats,
    }


# ============================================================================
# S3 작업
# ============================================================================


def setup_s3_bucket(bucket_name: str, region_name: Optional[str] = None) -> Dict:
    """
    Lambda 배포 패키지용 S3 버킷을 생성하거나 확인합니다.

    인자:
        bucket_name: S3 버킷 이름
        region_name: AWS 리전

    반환:
        버킷 정보가 포함된 딕셔너리
    """
    if region_name is None:
        region_name = AWS_REGION

    print("\n📦 Setting up S3 bucket for deployment packages...")

    s3 = boto3.client("s3", region_name=region_name)

    try:
        # 버킷이 존재하는지 확인
        s3.head_bucket(Bucket=bucket_name)
        print(f"✓ S3 bucket already exists: {bucket_name}")
        bucket_arn = f"arn:aws:s3:::{bucket_name}"

    except Exception as e:
        # head_bucket은 NoSuchBucket이 아니라 오류 코드가 '404'인 ClientError를 발생시킴
        # 버킷이 존재하지 않는지 확인(404/NotFound 오류)
        is_not_found = False

        if hasattr(e, "response"):
            # ClientError 응답에서 오류 코드 추출
            error_code = e.response.get("Error", {}).get("Code", "")
            http_status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0)
            is_not_found = error_code == "404" or http_status == 404

        if is_not_found:
            # 버킷 생성
            print(f"✓ Creating S3 bucket: {bucket_name}")

            try:
                if region_name == "us-east-1":
                    s3.create_bucket(Bucket=bucket_name)
                else:
                    s3.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={"LocationConstraint": region_name},
                    )

                bucket_arn = f"arn:aws:s3:::{bucket_name}"
                print(f"✓ Bucket created: {bucket_arn}")
            except Exception as create_error:
                # 버킷 생성이 실패해도(예: 동시 요청으로 이미 존재) 계속 진행
                create_error_str = str(create_error)
                if any(err in create_error_str for err in ["BucketAlreadyExists", "BucketAlreadyOwnedByYou"]):
                    print(f"✓ S3 bucket exists (concurrent creation): {bucket_name}")
                    bucket_arn = f"arn:aws:s3:::{bucket_name}"
                else:
                    print(f"❌ Error creating bucket: {create_error}")
                    raise
        else:
            # 그 밖의 오류는 다시 발생시킴
            print(f"❌ Error checking/setting up bucket: {e}")
            raise

    return {"bucket_name": bucket_name, "bucket_arn": bucket_arn, "region": region_name}


def upload_package_to_s3(
    zip_path: str,
    s3_bucket: str,
    s3_key: str = "lambda-packages/diagnostic-agent.zip",
    region_name: Optional[str] = None,
) -> Dict:
    """
    ZIP 패키지를 S3에 업로드합니다.

    인자:
        zip_path: 로컬 ZIP 파일 경로
        s3_bucket: S3 버킷 이름
        s3_key: S3 객체 키
        region_name: AWS 리전

    반환:
        S3 URI 및 업로드 정보가 포함된 딕셔너리
    """
    if region_name is None:
        region_name = AWS_REGION

    if not os.path.exists(zip_path):
        return {"status": "error", "error": f"ZIP file not found: {zip_path}"}

    zip_size = get_zip_size(zip_path)

    print("\n📤 Uploading package to S3...")
    print(f"   Local file: {zip_path} ({format_size(zip_size)})")
    print(f"   Destination: s3://{s3_bucket}/{s3_key}")

    s3 = boto3.client("s3", region_name=region_name)

    try:
        # 메타데이터와 함께 업로드
        s3.upload_file(
            zip_path,
            s3_bucket,
            s3_key,
            ExtraArgs={"Metadata": {"creator": "aiml301-lambda-packager", "model-id": MODEL_ID}},
        )

        s3_uri = f"s3://{s3_bucket}/{s3_key}"
        s3_url = f"https://{s3_bucket}.s3.{region_name}.amazonaws.com/{s3_key}"

        print("✓ Upload complete")
        print(f"  S3 URI: {s3_uri}")
        print(f"  HTTPS URL: {s3_url}")

        return {
            "status": "success",
            "s3_uri": s3_uri,
            "s3_bucket": s3_bucket,
            "s3_key": s3_key,
            "s3_url": s3_url,
            "size": zip_size,
        }

    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return {"status": "error", "error": str(e)}


# ============================================================================
# LAMBDA 배포
# ============================================================================


def create_lambda_function_from_zip(
    function_name: str,
    zip_path: str,
    s3_uri: Optional[str],
    role_arn: str,
    region_name: Optional[str] = None,
) -> Dict:
    """
    ZIP 패키지에서 Lambda 함수를 생성하거나 업데이트합니다.

    인자:
        function_name: Lambda 함수 이름
        zip_path: 로컬 ZIP 파일 경로(직접 업로드용, <50MB)
        s3_uri: S3 URI(S3 업로드용, >50MB). 형식: s3://bucket/key
        role_arn: Lambda 실행 역할 ARN
        region_name: AWS 리전

    반환:
        Lambda 함수 정보가 포함된 딕셔너리
    """
    if region_name is None:
        region_name = AWS_REGION

    print("\n⚡ Deploying Lambda function...")
    print(f"   Function: {function_name}")
    print(f"   Role: {role_arn}")

    lambda_client = boto3.client("lambda", region_name=region_name)

    # 코드 인자 준비
    code_arg = {}
    if s3_uri:
        # S3 기반 업로드(큰 패키지용)
        # 형식: s3://bucket/key
        parts = s3_uri.replace("s3://", "").split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""
        code_arg = {"S3Bucket": bucket, "S3Key": key}
        upload_method = "S3"
        print("   Upload method: S3")
    elif zip_path and os.path.exists(zip_path):
        # ZIP 직접 업로드(작은 패키지용)
        with open(zip_path, "rb") as f:
            code_arg = {"ZipFile": f.read()}
        upload_method = "Direct"
        print("   Upload method: Direct ZIP")
    else:
        return {"status": "error", "error": "No valid zip_path or s3_uri provided"}

    try:
        # 함수가 존재하는지 확인
        try:
            func = lambda_client.get_function(FunctionName=function_name)  # noqa: F841

            # 함수가 존재하면 업데이트
            print("✓ Function exists, updating...")

            response = lambda_client.update_function_code(FunctionName=function_name, **code_arg)

            # 업데이트 완료 대기
            print("  Waiting for update to complete...")
            waiter = lambda_client.get_waiter("function_updated")
            waiter.wait(FunctionName=function_name)

            # 구성 업데이트
            config_response = lambda_client.update_function_configuration(  # noqa: F841
                FunctionName=function_name,
                Runtime="python3.11",
                Handler="app.lambda_handler",
                Timeout=LAMBDA_CONFIG["timeout"],
                MemorySize=LAMBDA_CONFIG["memory_size"],
                Environment={"Variables": {"MODEL_ID": MODEL_ID, "REGION": region_name}},
            )

            print("✓ Configuration updated")

            function_arn = response["FunctionArn"]

        except lambda_client.exceptions.ResourceNotFoundException:
            # 함수가 없으면 생성
            print("✓ Creating new function...")

            response = lambda_client.create_function(
                FunctionName=function_name,
                Runtime="python3.11",
                Role=role_arn,
                Handler="app.lambda_handler",
                Code=code_arg,
                Timeout=LAMBDA_CONFIG["timeout"],
                MemorySize=LAMBDA_CONFIG["memory_size"],
                Environment={"Variables": {"MODEL_ID": MODEL_ID, "REGION": region_name}},
                Description="AIML301 Workshop - Diagnostics Agent (ZIP-based)",
            )

            # 생성 완료 대기
            print("  Waiting for function to become active...")
            waiter = lambda_client.get_waiter("function_active")
            waiter.wait(FunctionName=function_name)

            print("✓ Function created and active")

            function_arn = response["FunctionArn"]  # noqa: F841

        # 최종 함수 세부 정보 조회
        final_func = lambda_client.get_function(FunctionName=function_name)
        config = final_func["Configuration"]

        print("\n" + "=" * 70)
        print("✅ LAMBDA DEPLOYMENT SUCCESSFUL")
        print("=" * 70)
        print(f"Function: {config['FunctionName']}")
        print(f"ARN: {config['FunctionArn']}")
        print(f"Runtime: {config['Runtime']}")
        print(f"Memory: {config['MemorySize']} MB")
        print(f"Timeout: {config['Timeout']} s")
        print(f"State: {config['State']}")
        print(f"Upload method: {upload_method}")

        return {
            "status": "success",
            "function_name": config["FunctionName"],
            "function_arn": config["FunctionArn"],
            "runtime": config["Runtime"],
            "memory": config["MemorySize"],
            "timeout": config["Timeout"],
            "state": config["State"],
            "upload_method": upload_method,
        }

    except Exception as e:
        print(f"❌ Lambda deployment failed: {e}")
        import traceback

        traceback.print_exc()
        return {"status": "error", "error": str(e)}


# ============================================================================
# 전체 워크플로
# ============================================================================


def setup_lambda_zip_deployment(
    handler_code: str, requirements_content: str, region_name: Optional[str] = None
) -> Dict:
    """
    전체 워크플로: 패키지 생성 → (선택 사항) S3 업로드 → Lambda 배포

    인자:
        handler_code: Lambda 핸들러용 Python 코드
        requirements_content: pip 요구 사항 텍스트
        region_name: AWS 리전

    반환:
        전체 배포 결과
    """
    if region_name is None:
        region_name = AWS_REGION

    # 1단계: 패키지 생성
    package_result = create_deployment_package(handler_code, requirements_content)

    if package_result.get("status") == "error":
        return package_result

    # 2단계: 직접 업로드하는 경우 S3 생략(50MB 미만 패키지)
    zip_path = package_result["zip_path"]
    upload_method = package_result.get("upload_method", "direct")
    s3_result = {
        "status": "success",
        "upload_method": "direct",
    }  # 직접 업로드의 기본값

    if upload_method == "S3":
        # 큰 패키지에 필요한 경우에만 S3 버킷 설정
        bucket_result = setup_s3_bucket("aiml301-lambda-packages", region_name)

        # 3단계: S3에 업로드
        s3_result = upload_package_to_s3(zip_path, bucket_result["bucket_name"], region_name=region_name)

        if s3_result.get("status") == "error":
            return s3_result

    # 4단계: Parameter Store에서 Lambda 역할 조회
    try:
        role_arn = get_parameter(PARAMETER_PATHS["lab_02"]["lambda_role_arn"], region_name=region_name)
    except Exception as e:
        print("❌ Could not retrieve Lambda role ARN from Parameter Store")
        return {"status": "error", "error": f"Lambda role not found: {e}"}

    # 5단계: Lambda 배포
    lambda_result = create_lambda_function_from_zip(
        function_name="aiml301-diagnostic-agent",
        zip_path=zip_path if package_result["upload_method"] == "direct" else None,
        s3_uri=s3_result.get("s3_uri") if package_result["upload_method"] == "S3" else None,
        role_arn=role_arn,
        region_name=region_name,
    )

    if lambda_result.get("status") == "error":
        return lambda_result

    # 6단계: Lambda ARN을 Parameter Store에 저장
    print("\n📝 Saving Lambda ARN to Parameter Store...")
    put_parameter(
        PARAMETER_PATHS["lab_02"]["lambda_function_arn"],
        lambda_result["function_arn"],
        description="Lambda function ARN for Lab 02 diagnostic agent",
        region_name=region_name,
    )

    return {
        "status": "success",
        "package": package_result,
        "s3": s3_result,
        "lambda": lambda_result,
        "region": region_name,
    }


# ============================================================================
# 유틸리티 함수
# ============================================================================


def get_package_info(zip_path: str) -> Dict:
    """
    ZIP 패키지의 상세 정보를 반환합니다.

    인자:
        zip_path: ZIP 파일 경로

    반환:
        패키지 정보가 포함된 딕셔너리
    """
    if not os.path.exists(zip_path):
        return {"status": "error", "error": f"ZIP not found: {zip_path}"}

    zip_size = get_zip_size(zip_path)

    # 내용 나열
    files = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = zf.namelist()
    except Exception as e:
        return {"status": "error", "error": f"Invalid ZIP: {e}"}

    # 파일 분류
    has_app = "app.py" in files
    has_handler = any(f.endswith(".py") for f in files)
    lib_files = [f for f in files if f.startswith("lib/")]
    helper_files = [f for f in files if f.startswith("lab_helpers/")]

    return {
        "status": "success",
        "zip_path": zip_path,
        "zip_size": zip_size,
        "zip_size_formatted": format_size(zip_size),
        "total_files": len(files),
        "has_app_py": has_app,
        "has_handlers": has_handler,
        "lib_files_count": len(lib_files),
        "helper_files_count": len(helper_files),
        "files": {
            "total": len(files),
            "lib": len(lib_files),
            "helpers": len(helper_files),
            "root": len([f for f in files if "/" not in f]),
        },
    }


if __name__ == "__main__":
    # 사용 예
    print("Lambda Packager - Example Usage\n")
    print("from lab_helpers.lab_02.lambda_packager import:")
    print("  - create_deployment_package()")
    print("  - setup_s3_bucket()")
    print("  - upload_package_to_s3()")
    print("  - create_lambda_function_from_zip()")
    print("  - get_package_info()")
