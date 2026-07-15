"""
pay-for-api Notebook에서 공유하는 utils.py helper입니다.

응답 정돈 출력, IAM role assume, 상태 전환 polling, 멱등 create 호출 처리를
위한 간단한 boto3 wrapper를 제공합니다.
"""

import json
import time

import boto3
import botocore.exceptions


def pp(label: str, response: dict) -> None:
    """ResponseMetadata를 제외하고 API 응답을 보기 좋게 출력합니다."""
    data = {k: v for k, v in response.items() if k != "ResponseMetadata"}
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(json.dumps(data, indent=2, default=str))


def assume_role(
    session: boto3.Session,
    role_arn: str,
    session_name: str = "tutorial-session",
) -> boto3.Session:
    """IAM role을 assume하고 credential을 자동 갱신하는 boto3 Session을 반환합니다.

    내부적으로 botocore의 ``RefreshableCredentials``를 사용하므로 호출자가
    client를 다시 만들지 않아도 기본 1시간 STS 만료 이후까지 session이
    유효하게 유지됩니다. 사용자가 5.1절의 session을 몇 시간 동안 그대로 둔 뒤
    7절이나 9절로 돌아올 수 있는 Notebook에서 중요합니다.

    get_caller_identity()를 호출해 assume한 identity를 즉시 검증하며,
    assume 자체가 실패하면 예외를 발생시킵니다.
    """
    from botocore.credentials import RefreshableCredentials
    from botocore.session import Session as BotocoreSession

    sts = session.client("sts")

    def _refresh() -> dict:
        creds = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name,
        )["Credentials"]
        return {
            "access_key": creds["AccessKeyId"],
            "secret_key": creds["SecretAccessKey"],
            "token": creds["SessionToken"],
            "expiry_time": creds["Expiration"].isoformat(),
        }

    refreshable_creds = RefreshableCredentials.create_from_metadata(
        metadata=_refresh(),
        refresh_using=_refresh,
        method="sts-assume-role",
    )

    botocore_session = BotocoreSession()
    botocore_session._credentials = refreshable_creds
    botocore_session.set_config_variable("region", session.region_name)

    new_session = boto3.Session(botocore_session=botocore_session)

    assumed_arn = new_session.client("sts").get_caller_identity()["Arn"]
    print(f"  Assumed: {assumed_arn}")
    return new_session


def wait_for_status(
    client_fn,
    expected_status: str,
    poll_interval: int = 5,
    timeout: int = 120,
    **kwargs,
) -> dict:
    """resource가 expected_status에 도달할 때까지 Get* API를 polling합니다.

    다음 응답 형식에서 순서대로 상태를 확인합니다.
    - 최상위 ``status`` 필드(Manager, Connector 응답)
    - ``paymentInstrument.status``(GetPaymentInstrument 응답)

    resource가 ``timeout``초 이내에 expected_status에 도달하지 않으면
    TimeoutError를 발생시킵니다.
    resource가 종료 failure 상태(``_FAILED``로 끝나는 모든 상태)에 들어가면
    즉시 RuntimeError를 발생시킵니다.
    """
    deadline = time.time() + timeout
    while True:
        resp = client_fn(**kwargs)
        status = resp.get("status") or resp.get("paymentInstrument", {}).get("status")
        print(f"   Status: {status}")
        if isinstance(status, str) and status.endswith("_FAILED"):
            raise RuntimeError(f"Resource reached failure state: '{status}'")
        if status == expected_status:
            return resp
        if time.time() >= deadline:
            raise TimeoutError(f"Resource still in '{status}' after {timeout}s — check the console for errors")
        time.sleep(poll_interval)


def idempotent_create(create_fn, conflict_msg: str = "Resource already exists", **kwargs) -> dict | None:
    """create_fn을 호출하고 ConflictException을 정상적으로 처리합니다.

    성공하면 API 응답을 반환하고 resource가 이미 있으면 None을 반환합니다.
    그 밖의 ClientError는 다시 발생시킵니다.
    """
    try:
        return create_fn(**kwargs)
    except botocore.exceptions.ClientError as exc:
        if exc.response["Error"]["Code"] == "ConflictException":
            print(f"  ⚠️  {conflict_msg} — skipping create")
            return None
        raise


def write_env_updates(updates: dict, env_path: str = ".env") -> None:
    """다른 줄을 보존하면서 dotenv 파일에 key=value 쌍을 upsert합니다.

    제자리에서 업데이트합니다. 일치하는 키는 교체하고 새 키는 추가하며,
    주석과 빈 줄은 보존합니다. 이 자습서의 기존 .env 스타일에 맞춰 값을
    그대로(따옴표 없이) 기록합니다.

    Notebook이 runtime에 기록하는 비밀이 아닌 값(USER_ID, role ARN, manager ID,
    instrument ID, session ID, wallet address)에만 사용합니다. Wallet provider
    secret(Coinbase/Privy key, Privy authorization private key)은 사용자가
    ``.env``에 직접 붙여 넣으며 이 함수를 통과하지 않습니다. Notebook 4절에서
    ``CreatePaymentCredentialProvider``를 호출하면 AgentCore Identity가 해당
    secret을 KMS로 암호화해 AWS Secrets Manager에 저장하고, runtime에서 사용할
    credential provider ARN만 ``.env``에 남습니다. ``.env`` 파일 자체는 use case
    생성 시점부터 gitignore 대상입니다.
    """
    import pathlib

    path = pathlib.Path(env_path)
    existing = path.read_text().splitlines() if path.exists() else []
    seen = set()
    out = []
    for line in existing:
        key = line.split("=", 1)[0].strip()
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n")
