#!/usr/bin/env python3
"""Live Heurist catalog를 가져와 로컬 cache를 갱신합니다.

Image에 포함되는 catalog cache를 최신 상태로 유지하도록 각
`agentcore deploy` 전에 container 내부가 아닌 host machine에서 실행합니다.

사용법(pay-for-data/에서 실행):
    python agent/sync_registry.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Script로 실행할 때 sibling module을 import할 수 있도록 설정
sys.path.insert(0, str(Path(__file__).resolve().parent))

from catalog import fetch_live_catalog, get_tools_for_agents  # noqa: E402
from config import LIVE_CATALOG_CACHE_PATH, get_config  # noqa: E402


def main() -> None:
    cfg = get_config()
    catalog = fetch_live_catalog()
    selected_tools = get_tools_for_agents(cfg.heurist_tool_agent_ids, refresh=False)
    print(f"Saved live catalog cache to {LIVE_CATALOG_CACHE_PATH}")
    print(f"Catalog url:    {cfg.heurist_catalog_url}")
    print(f"Catalog agents: {catalog.get('count', '?')}")
    print(f"Selected agents: {', '.join(cfg.heurist_tool_agent_ids)}")
    print(f"Selected tools: {len(selected_tools)}")


if __name__ == "__main__":
    main()
