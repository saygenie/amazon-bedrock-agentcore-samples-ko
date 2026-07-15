#!/usr/bin/env python3
"""Heurist tool catalog를 load하고 agent system prompt용으로 format합니다."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import requests

from config import LIVE_CATALOG_CACHE_PATH, get_config

# --- 안전 limit ------------------------------------------------------------
# Sample에서는 의도적으로 여유 있게 설정하지만 잘못 구성된 endpoint나 disk 손상으로
# memory가 과도하게 사용되는 것을 방지함
MAX_CATALOG_BYTES = 5 * 1024 * 1024  # 5 MiB disk cache 제한
MAX_CATALOG_RESPONSE_BYTES = 10 * 1024 * 1024  # 10 MiB network payload 제한
MAX_PROMPT_FIELD_LEN = 500  # System prompt로 rendering할 때 field별 상한

_UNSAFE_FIELD_PLACEHOLDER = "(unavailable)"
_UNSAFE_PROMPT_CHARS = re.compile(r"[\x00-\x1f\x7f`|\[\]]")


def _sanitize_prompt_text(value: Any, max_len: int = MAX_PROMPT_FIELD_LEN) -> str:
    """``value``에서 생성한 Markdown-safe 단일 line string을 반환합니다.

    외부 catalog data는 agent system prompt에 interpolate됩니다. Sanitize하지
    않으면 악성 registry entry가 link, code fence, table pipe를 삽입하여
    prompt 구조를 변경할 수 있습니다.
    """
    if value is None:
        return ""
    text = str(value)
    text = _UNSAFE_PROMPT_CHARS.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rstrip() + "…"
    return text


def _sanitize_url(value: Any) -> str:
    """http(s) URL만 허용하며 그 외에는 placeholder를 반환합니다."""
    text = _sanitize_prompt_text(value, max_len=MAX_PROMPT_FIELD_LEN)
    if not text:
        return _UNSAFE_FIELD_PLACEHOLDER
    if not re.match(r"^https?://[^\s]+$", text, re.IGNORECASE):
        return _UNSAFE_FIELD_PLACEHOLDER
    return text


def _coerce_price(raw: Any) -> float:
    """Raw price 값을 유한한 음이 아닌 float로 변환합니다."""
    try:
        price = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid price value {raw!r}") from exc
    if not math.isfinite(price) or price < 0:
        raise ValueError(f"Invalid price value {raw!r}: must be a finite, non-negative number")
    return price


def _atomic_write_text(path: Path, content: str) -> None:
    """동일 directory의 임시 파일을 통해 ``content``를 ``path``에 atomic하게 기록합니다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def fetch_live_catalog(session: requests.Session | None = None) -> dict[str, Any]:
    """Live Heurist mesh registry를 가져와 로컬에 cache합니다."""
    cfg = get_config()
    http = session or requests.Session()
    response = http.get(cfg.heurist_catalog_url, timeout=30, stream=True)
    response.raise_for_status()

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_CATALOG_RESPONSE_BYTES:
            raise ValueError(f"Heurist catalog response exceeded {MAX_CATALOG_RESPONSE_BYTES} bytes")
        chunks.append(chunk)
    body = b"".join(chunks).decode(response.encoding or "utf-8")
    payload = json.loads(body)

    _atomic_write_text(LIVE_CATALOG_CACHE_PATH, json.dumps(payload, indent=2))
    return payload


def load_live_catalog(path: Path | None = None) -> dict[str, Any]:
    input_path = path or LIVE_CATALOG_CACHE_PATH
    if not input_path.exists():
        raise FileNotFoundError(f"Live catalog cache not found: {input_path}")
    size = input_path.stat().st_size
    if size > MAX_CATALOG_BYTES:
        raise ValueError(
            f"Catalog cache at {input_path} is {size} bytes which exceeds the "
            f"{MAX_CATALOG_BYTES} byte limit. Delete or regenerate the file."
        )
    return json.loads(input_path.read_text(encoding="utf-8"))


def get_live_catalog(refresh: bool = False, session: requests.Session | None = None) -> dict[str, Any]:
    if refresh or not LIVE_CATALOG_CACHE_PATH.exists():
        return fetch_live_catalog(session=session)
    return load_live_catalog()


def get_tools_for_agents(
    agent_ids: tuple[str, ...] | list[str],
    refresh: bool = False,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    """선택한 Heurist agent의 정규화된 tool definition을 반환합니다."""
    import logging

    logger = logging.getLogger(__name__)

    selected = set(agent_ids)
    live_catalog = get_live_catalog(refresh=refresh, session=session)
    tools: list[dict[str, Any]] = []
    found_ids: set[str] = set()

    for agent in live_catalog.get("agents", []):
        agent_id = agent.get("agentId")
        if not agent_id or agent_id not in selected:
            continue
        found_ids.add(agent_id)
        for tool_def in agent.get("tools", []):
            try:
                price_usd = _coerce_price(tool_def["priceUsd"])
            except (KeyError, ValueError):
                continue
            tools.append(
                {
                    "agent_id": agent_id,
                    "tool_name": tool_def.get("name", ""),
                    "resource_url": tool_def.get("resourceUrl", ""),
                    "price_usd": price_usd,
                    "method": tool_def.get("method", "POST"),
                    "description": tool_def.get("description", ""),
                    "parameters": tool_def.get("parameters", {}) or {},
                }
            )

    missing = selected - found_ids
    if missing:
        logger.warning(
            "The following agent IDs were not found in the Heurist catalog and will be "
            "skipped. They may have been renamed or removed: %s. "
            "Run sync_registry to refresh the catalog, or update HEURIST_AGENT_IDS in .env.",
            ", ".join(sorted(missing)),
        )

    return tools


def format_catalog_for_prompt(tools: list[dict[str, Any]]) -> str:
    """Tool catalog를 agent system prompt용 reference table로 format합니다."""
    lines = ["## Available Paid Endpoints (Heurist x402)", ""]
    lines.append("| Agent | Tool | URL | Method | Price | Description |")
    lines.append("|-------|------|-----|--------|-------|-------------|")

    for t in tools:
        agent_id = _sanitize_prompt_text(t.get("agent_id"), max_len=80)
        tool_name = _sanitize_prompt_text(t.get("tool_name"), max_len=80)
        url = _sanitize_url(t.get("resource_url"))
        method = _sanitize_prompt_text(t.get("method"), max_len=10) or "POST"
        desc = _sanitize_prompt_text(t.get("description"), max_len=80)
        price = t.get("price_usd")
        price_str = f"${price:.3f}" if isinstance(price, (int, float)) and math.isfinite(price) else "n/a"
        lines.append(f"| {agent_id} | {tool_name} | {url} | {method} | {price_str} | {desc} |")

    lines.append("")
    lines.append("### Parameter Schemas")
    lines.append("")
    for t in tools:
        params = t.get("parameters", {}) or {}
        props = params.get("properties", {}) or {}
        if not props:
            continue
        agent_id = _sanitize_prompt_text(t.get("agent_id"), max_len=80)
        tool_name = _sanitize_prompt_text(t.get("tool_name"), max_len=80)
        method = _sanitize_prompt_text(t.get("method"), max_len=10) or "POST"
        url = _sanitize_url(t.get("resource_url"))
        lines.append(f"**{agent_id}/{tool_name}** (`{method} {url}`)")
        required_fields = params.get("required", []) or []
        for name, schema in props.items():
            if not isinstance(schema, dict):
                schema = {}
            safe_name = _sanitize_prompt_text(name, max_len=80)
            required = safe_name in {_sanitize_prompt_text(r, max_len=80) for r in required_fields}
            req_marker = " (required)" if required else ""
            type_name = _sanitize_prompt_text(schema.get("type", "any"), max_len=40)
            desc = _sanitize_prompt_text(schema.get("description", ""), max_len=120)
            lines.append(f"  - `{safe_name}`: {type_name}{req_marker} — {desc}")
        lines.append("")

    return "\n".join(lines)
