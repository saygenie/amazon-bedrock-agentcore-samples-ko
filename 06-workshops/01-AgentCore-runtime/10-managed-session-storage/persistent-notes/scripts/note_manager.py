#!/usr/bin/env python3
"""Note를 로컬 notes.json 파일에 저장하는 간단한 saver입니다."""

import json
import sys
from datetime import datetime
from pathlib import Path

# 현재 디렉터리에 note 저장
NOTES_FILE = Path("/mnt/workspace/notes.json")


def save_note(content: str) -> None:
    """Note를 notes.json에 저장합니다."""
    # 기존 note 불러오기
    notes = []
    if NOTES_FILE.exists():
        try:
            with open(NOTES_FILE, "r") as f:
                notes = json.load(f)
        except json.JSONDecodeError:
            notes = []

    # 새 note 추가
    note = {"content": content, "timestamp": datetime.now().isoformat()}
    notes.append(note)

    # 파일에 다시 저장
    with open(NOTES_FILE, "w") as f:
        json.dump(notes, f, indent=2)

    print(
        json.dumps(
            {
                "status": "success",
                "message": f"Note saved to {NOTES_FILE}",
                "note": note,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 note_manager.py <note_content>")
        sys.exit(1)

    note_content = " ".join(sys.argv[1:])
    save_note(note_content)
