#!/usr/bin/env python3
"""
데모 데이터의 날짜를 현재 주차에 맞게 업데이트하고 S3에 업로드합니다.

이 스크립트는 demo_data 디렉터리의 모든 날짜에 현재 주차가 반영되도록
동적으로 업데이트하여 데모 데이터가 항상 최신으로 보이게 한 다음,
업데이트된 데이터를 S3 버킷에 업로드합니다.
"""

import json
import re
import argparse
import platform
from datetime import datetime, timedelta
from pathlib import Path
import boto3
from botocore.exceptions import ClientError


# 이모지를 비활성화하기 위해 Windows에서 실행 중인지 감지
IS_WINDOWS = platform.system() == "Windows"


def get_symbol(emoji, fallback):
    """Windows가 아닌 시스템에서는 이모지를, Windows에서는 대체 텍스트를 반환합니다."""
    return fallback if IS_WINDOWS else emoji


def get_current_week_info():
    """현재 주차 번호와 날짜 범위를 가져옵니다."""
    today = datetime.now()
    week_num = today.isocalendar()[1]

    # 현재 주의 월요일 가져오기
    monday = today - timedelta(days=today.weekday())

    # 해당 주의 날짜 생성(월요일~금요일)
    week_dates = {
        "monday": monday,
        "tuesday": monday + timedelta(days=1),
        "wednesday": monday + timedelta(days=2),
        "thursday": monday + timedelta(days=3),
        "friday": monday + timedelta(days=4),
        "saturday": monday + timedelta(days=5),
        "sunday": monday + timedelta(days=6),
    }

    return week_num, week_dates


def update_json_dates(file_path, week_dates):
    """JSON 파일의 날짜를 업데이트합니다."""
    with open(file_path, "r") as f:
        data = json.load(f)

    # 모든 날짜 필드를 재귀적으로 업데이트
    def update_dates_recursive(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and re.match(r"\d{4}-\d{2}-\d{2}", value):
                    # 요일을 기준으로 이전 날짜를 새 날짜에 매핑
                    old_date = datetime.strptime(value, "%Y-%m-%d")
                    day_name = old_date.strftime("%A").lower()
                    if day_name in week_dates:
                        obj[key] = week_dates[day_name].strftime("%Y-%m-%d")
                elif isinstance(value, (dict, list)):
                    update_dates_recursive(value)
        elif isinstance(obj, list):
            for item in obj:
                update_dates_recursive(item)

    update_dates_recursive(data)

    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"{get_symbol('✓', '+')} Updated {file_path.name}")


def update_markdown_dates(file_path, week_dates):
    """Markdown 파일의 날짜를 업데이트합니다."""
    with open(file_path, "r") as f:
        content = f.read()

    # YYYY-MM-DD 형식의 날짜 업데이트
    def replace_date(match):
        old_date = datetime.strptime(match.group(0), "%Y-%m-%d")
        day_name = old_date.strftime("%A").lower()
        if day_name in week_dates:
            return week_dates[day_name].strftime("%Y-%m-%d")
        return match.group(0)

    content = re.sub(r"\d{4}-\d{2}-\d{2}", replace_date, content)

    # "Week of Month Day" 형식 업데이트
    monday = week_dates["monday"]
    week_of_pattern = r"Week of \w+ \d{1,2}"
    content = re.sub(week_of_pattern, f"Week of {monday.strftime('%B %d')}", content)

    with open(file_path, "w") as f:
        f.write(content)

    print(f"{get_symbol('✓', '+')} Updated {file_path.name}")


def update_csv_dates(file_path, week_dates):
    """CSV 파일의 날짜를 업데이트합니다."""
    with open(file_path, "r") as f:
        lines = f.readlines()

    updated_lines = []
    for line in lines:
        # YYYY-MM-DD 형식의 날짜 업데이트
        def replace_date(match):
            old_date = datetime.strptime(match.group(0), "%Y-%m-%d")
            day_name = old_date.strftime("%A").lower()
            if day_name in week_dates:
                return week_dates[day_name].strftime("%Y-%m-%d")
            return match.group(0)

        updated_line = re.sub(r"\d{4}-\d{2}-\d{2}", replace_date, line)
        updated_lines.append(updated_line)

    with open(file_path, "w") as f:
        f.writelines(updated_lines)

    print(f"{get_symbol('✓', '+')} Updated {file_path.name}")


def rename_files_with_week(demo_data_path, week_num, week_dates):
    """현재 주차 번호와 날짜에 맞게 파일 이름을 변경합니다."""
    monday = week_dates["monday"]

    # 업데이트할 패턴
    patterns = [
        (r"_week_\d{2}\.", f"_week_{week_num:02d}."),
        (
            r"_(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)_\d{2}\.",
            f"_{monday.strftime('%b').lower()}_{monday.day:02d}.",
        ),
    ]

    for file_path in demo_data_path.rglob("*"):
        if file_path.is_file():
            new_name = file_path.name

            for pattern, replacement in patterns:
                new_name = re.sub(pattern, replacement, new_name, flags=re.IGNORECASE)

            if new_name != file_path.name:
                new_path = file_path.parent / new_name
                file_path.rename(new_path)
                print(f"{get_symbol('✓', '+')} Renamed {file_path.name} {get_symbol('→', '->')} {new_name}")


def upload_to_s3(demo_data_path, bucket_name, prefix="demo_data"):
    """모든 데모 데이터 파일을 S3 버킷에 업로드합니다."""
    s3_client = boto3.client("s3")

    print(f"\nUploading to S3 bucket: {bucket_name}")
    print(f"   Prefix: {prefix}/\n")

    uploaded_files = []

    for file_path in demo_data_path.rglob("*"):
        if file_path.is_file():
            # 상위 디렉터리가 아닌 demo_data 디렉터리 자체를 기준으로 상대 경로 계산
            relative_path = file_path.relative_to(demo_data_path)
            s3_key = f"{prefix}/{relative_path.as_posix()}" if prefix else relative_path.as_posix()

            try:
                # 콘텐츠 유형 결정
                content_type = "text/plain"
                if file_path.suffix == ".json":
                    content_type = "application/json"
                elif file_path.suffix == ".csv":
                    content_type = "text/csv"
                elif file_path.suffix == ".md":
                    content_type = "text/markdown"

                s3_client.upload_file(
                    str(file_path),
                    bucket_name,
                    s3_key,
                    ExtraArgs={"ContentType": content_type},
                )
                uploaded_files.append(s3_key)
                print(f"{get_symbol('✓', '+')} Uploaded {s3_key}")
            except ClientError as e:
                print(f"{get_symbol('✗', 'X')} Failed to upload {s3_key}: {e}")

    print(f"\n{get_symbol('✅', 'SUCCESS:')} Uploaded {len(uploaded_files)} files to s3://{bucket_name}/{prefix}/")
    return uploaded_files


def update_tools_config(bucket_name):
    """tools.py 파일의 S3_BUCKET 구성을 업데이트합니다."""
    script_dir = Path(__file__).parent
    tools_file = script_dir / "agent" / "tools.py"

    if not tools_file.exists():
        print(f"{get_symbol('⚠️', 'WARNING:')} tools.py not found at {tools_file}")
        return False

    try:
        # 파일 읽기
        with open(tools_file, "r") as f:
            content = f.read()

        # S3_BUCKET 줄 업데이트 - 단순 할당과 일치
        bucket_pattern = r"S3_BUCKET = ['\"][^'\"]*['\"]"
        bucket_replacement = f"S3_BUCKET = '{bucket_name}'"

        if re.search(bucket_pattern, content):
            content = re.sub(bucket_pattern, bucket_replacement, content)
            print(f"{get_symbol('✓', '+')} Updated S3_BUCKET in tools.py to: {bucket_name}")

            # 파일에 다시 쓰기
            with open(tools_file, "w") as f:
                f.write(content)

            return True
        else:
            print(f"{get_symbol('⚠️', 'WARNING:')} Could not find S3_BUCKET configuration in tools.py")
            return False

    except Exception as e:
        print(f"{get_symbol('❌', 'ERROR:')} Error updating tools.py: {e}")
        return False


def main():
    """모든 데모 데이터를 업데이트하고 S3에 업로드하는 메인 함수입니다."""
    parser = argparse.ArgumentParser(
        description="Update demo data dates and upload to S3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update dates and upload to S3 bucket
  python update_demo_dates.py --bucket my-weekly-reports-bucket
  
  # Update dates and upload with custom prefix
  python update_demo_dates.py --bucket my-bucket --prefix data/weekly-reports
  
  # Update dates only (no upload)
  python update_demo_dates.py
        """,
    )
    parser.add_argument("--bucket", type=str, help="S3 bucket name to upload demo data to")
    parser.add_argument(
        "--prefix",
        type=str,
        default="demo_data",
        help="S3 key prefix for uploaded files (default: demo_data)",
    )

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    demo_data_path = script_dir / "demo_data"

    if not demo_data_path.exists():
        print(f"Error: demo_data directory not found at {demo_data_path}")
        return

    week_num, week_dates = get_current_week_info()
    monday = week_dates["monday"]

    print(f"\n{get_symbol('📅', 'CALENDAR:')} Updating demo data to current week:")
    print(f"   Week {week_num} of {monday.year}")
    print(f"   Week of {monday.strftime('%B %d, %Y')}\n")

    # 먼저 현재 주차에 맞게 파일 이름 변경
    print("Renaming files...")
    rename_files_with_week(demo_data_path, week_num, week_dates)

    print("\nUpdating file contents...")

    # demo_data의 모든 파일 업데이트
    for file_path in demo_data_path.rglob("*"):
        if file_path.is_file() and file_path.name != "README.md":
            if file_path.suffix == ".json":
                update_json_dates(file_path, week_dates)
            elif file_path.suffix == ".md":
                update_markdown_dates(file_path, week_dates)
            elif file_path.suffix == ".csv":
                update_csv_dates(file_path, week_dates)

    print(f"\n{get_symbol('✅', 'SUCCESS:')} Demo data updated successfully!")
    print(f"   All dates now reflect week {week_num} ({monday.strftime('%B %d - %B %d, %Y')})")

    # 버킷이 지정되었으면 S3에 업로드
    if args.bucket:
        # 버킷 이름으로 tools.py 구성 업데이트
        print(f"\n{get_symbol('📝', 'NOTE:')} Updating tools.py configuration...")
        update_tools_config(args.bucket)

        # 데모 데이터 업로드
        upload_to_s3(demo_data_path, args.bucket, args.prefix)
    else:
        print(f"\n{get_symbol('💡', 'TIP:')} Use --bucket to upload data to S3 for AgentCore deployment")


if __name__ == "__main__":
    main()
