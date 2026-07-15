#!/usr/bin/env python3
"""Heurist finance agent의 공유 configuration입니다."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

AGENT_DIR = Path(__file__).resolve().parent
LIVE_CATALOG_CACHE_PATH = AGENT_DIR / "catalog_live_cache.json"

# Agent directory(Runtime container layout) 또는 상위 use case directory
# (sync_registry용 host machine layout)의 .env를 허용
ENV_CANDIDATE_PATHS: tuple[Path, ...] = (
    AGENT_DIR / ".env",
    AGENT_DIR.parent / ".env",
)

DEFAULT_HEURIST_AGENT_IDS = (
    "ExaSearchDigestAgent",
    "YahooFinanceAgent",
    "FredMacroAgent",
    "SecEdgarAgent",
)

# Agent가 host 측 script를 실행하는 데 필요한 environment variable
# Runtime container에는 필요하지 않으며 runtime의 invocation payload에서
# payment context를 가져옴
_REQUIRED_ENV_VARS: tuple[str, ...] = (
    "PAYMENT_MANAGER_ARN",
    "PAYMENT_SESSION_ID",
    "PAYMENT_INSTRUMENT_ID",
)


def load_environment() -> None:
    """지원되는 위치에서 로컬 .env 파일을 load합니다."""
    for candidate in ENV_CANDIDATE_PATHS:
        if candidate.is_file():
            load_dotenv(candidate, override=False)


@dataclass(frozen=True)
class AppConfig:
    aws_region: str
    aws_profile: str | None
    bedrock_profile: str | None
    bedrock_model_id: str
    payment_manager_arn: str
    payment_session_id: str
    payment_instrument_id: str
    user_id: str
    heurist_catalog_url: str
    heurist_tool_agent_ids: tuple[str, ...]
    code_interpreter_session_name: str
    agent_timeout_seconds: int
    agent_max_tokens: int


def _parse_csv_tuple(raw_value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if not raw_value:
        return default
    values = tuple(item.strip() for item in raw_value.split(",") if item.strip())
    return values or default


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    searched = ", ".join(str(p) for p in ENV_CANDIDATE_PATHS)
    raise RuntimeError(
        f"Missing required environment variable {name!r}. "
        f"Set it in your shell or in a .env file at one of: {searched}. "
        f"See .env.example for the full list of required values."
    )


def get_config() -> AppConfig:
    load_environment()
    missing = [name for name in _REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        searched = ", ".join(str(p) for p in ENV_CANDIDATE_PATHS)
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + f". Set them in your shell or in a .env file at one of: {searched}. "
            + "See .env.example for the full list of required values."
        )
    return AppConfig(
        aws_region=os.environ.get("AWS_REGION", "us-west-2"),
        aws_profile=os.environ.get("AWS_PROFILE"),
        bedrock_profile=os.environ.get("BEDROCK_PROFILE") or os.environ.get("AWS_PROFILE"),
        bedrock_model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6"),
        payment_manager_arn=_require_env("PAYMENT_MANAGER_ARN"),
        payment_session_id=_require_env("PAYMENT_SESSION_ID"),
        payment_instrument_id=_require_env("PAYMENT_INSTRUMENT_ID"),
        user_id=os.environ.get("USER_ID", "demo-user"),
        heurist_catalog_url=os.environ.get(
            "HEURIST_CATALOG_URL",
            "https://mesh.heurist.xyz/x402/base-sepolia/agents?details=true",
        ),
        heurist_tool_agent_ids=_parse_csv_tuple(os.environ.get("HEURIST_AGENT_IDS"), DEFAULT_HEURIST_AGENT_IDS),
        code_interpreter_session_name=os.environ.get("CODE_INTERPRETER_SESSION_NAME", "heurist-finance"),
        agent_timeout_seconds=int(os.environ.get("AGENT_TIMEOUT_SECONDS", "300")),
        agent_max_tokens=int(os.environ.get("AGENT_MAX_TOKENS", "64000")),
    )
