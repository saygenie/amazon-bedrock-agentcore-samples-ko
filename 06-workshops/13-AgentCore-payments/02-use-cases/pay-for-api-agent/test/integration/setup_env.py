"""pay-for-api 자습서의 env 파일 처리 모듈입니다.

Notebook과 utility script에서 ``env-sample.txt``를 기반으로 ``.env``를 만들고
비밀이 아닌 값(``USER_ID``, role ARN, manager ID 등)을 기록할 때 사용하는
간단한 helper를 제공합니다.

사용자가 제공하는 wallet provider secret(Coinbase/Privy key, Privy
authorization private key)은 ``.env``에 직접 붙여 넣습니다. Notebook 2절의
cell은 사용자를 위해 editor에서 ``.env``를 열고 아직 값이 필요한 키를
나열합니다. 이어서 Notebook 4절은 이 secret을 한 번 읽어
``CreatePaymentCredentialProvider``에 전달합니다. AgentCore Identity는 secret을
KMS로 암호화해 AWS Secrets Manager에 저장하고 agent에는 secret ARN만
노출합니다. 이후 runtime에는 로컬 ``.env`` 사본이 필요하지 않으므로 직접
지울 수 있습니다. 이 모듈은 secret 데이터를 log에 기록하거나 전송하거나
다시 읽지 않습니다.

진입점:

- ``python3 test/integration/setup_env.py`` - CLI. ``.env``를 만들고 없으면
  새 ``USER_ID``를 생성합니다.
- ``from setup_env import seed_env, write_env_var`` - 프로그래밍 방식 API입니다.
"""

from __future__ import annotations

import pathlib
import shutil
import sys
import uuid

# ── 경로 처리 ─────────────────────────────────────────────────────────
# Python module은 test/integration/setup_env.py에 있으므로 두 단계 위로 이동해
# env-sample.txt와 .env가 있는 use case root를 찾습니다.
HERE = pathlib.Path(__file__).resolve().parent
USE_CASE_ROOT = HERE.parent.parent
TEMPLATE = USE_CASE_ROOT / "env-sample.txt"
ENV_FILE = USE_CASE_ROOT / ".env"

# "아직 값이 입력되지 않음"을 의미하는 token으로, 빈 값처럼 처리합니다.
PLACEHOLDER_PREFIXES = ("<",)
PLACEHOLDER_SUBSTRINGS = ("<ACCOUNT_ID>",)


def _is_empty(value: str) -> bool:
    """값이 설정되지 않았거나 비어 있거나 template placeholder이면 True입니다."""
    if not value:
        return True
    if any(value.startswith(p) for p in PLACEHOLDER_PREFIXES):
        return True
    if any(s in value for s in PLACEHOLDER_SUBSTRINGS):
        return True
    return False


def _read_env_lines() -> list[str]:
    return ENV_FILE.read_text().splitlines() if ENV_FILE.exists() else []


def _current_value(key: str) -> str:
    for line in _read_env_lines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1]
    return ""


def write_env_var(key: str, value: str) -> None:
    """다른 줄은 건드리지 않고 .env의 KEY=VALUE를 업데이트하거나 추가합니다.

    Notebook이 프로그래밍 방식으로 기록하는 비밀이 아닌 값(USER_ID, role ARN,
    manager ID, instrument ID, session ID, wallet address)만을 위한 함수입니다.
    Wallet provider secret(Coinbase/Privy key, Privy authorization private key)은
    사용자가 ``.env``에 직접 붙여 넣으며 이 함수를 통과하지 않습니다.
    Notebook 4절에서 ``CreatePaymentCredentialProvider``를 호출하면 해당 secret은
    AgentCore Identity의 AWS Secrets Manager에 저장되고 credential provider ARN만
    ``.env``에 남습니다.
    """
    lines = _read_env_lines()
    replaced = False
    out: list[str] = []
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(out) + "\n")


def seed_env() -> bool:
    """.env가 없으면 env-sample.txt로 생성하고 USER_ID에 고유한 UUID가
    설정되었는지 확인합니다.

    이 호출에서 .env를 생성했으면 True, 이미 있었으면 False를 반환합니다.
    """
    seeded = False
    if not ENV_FILE.exists():
        if not TEMPLATE.exists():
            raise FileNotFoundError(
                f"env-sample.txt not found at {TEMPLATE}. Run this from the use-case root with the template in place."
            )
        shutil.copy2(TEMPLATE, ENV_FILE)
        seeded = True

    # 첫 실행 시 USER_ID를 자동 생성합니다. Notebook은 CreatePaymentSession header의
    # operator 식별자로 USER_ID를 사용합니다. 실행 간에 고정값을 사용하면 서비스의
    # vendor-user mapping에서 충돌하므로 새 .env마다 고유한 UUID를 부여합니다.
    #
    # `pay-for-api-` 접두사는 자습서 범위의 식별자임을 나타냅니다. production
    # 코드에서는 이 형식을 재사용하지 말고 자체 auth system에서 USER_ID를
    # 생성해야 합니다.
    if _is_empty(_current_value("USER_ID")):
        write_env_var("USER_ID", f"pay-for-api-{uuid.uuid4()}")

    return seeded


def _cli() -> int:
    if seed_env():
        print(f"✅ Seeded {ENV_FILE} from env-sample.txt.")
    else:
        print(f"↷ Found existing {ENV_FILE} — left in place.")
    print()
    print(
        "Open .env in your editor and fill in any missing values "
        "(secrets are paste-only; non-secrets are written for you by "
        "later notebook cells)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
