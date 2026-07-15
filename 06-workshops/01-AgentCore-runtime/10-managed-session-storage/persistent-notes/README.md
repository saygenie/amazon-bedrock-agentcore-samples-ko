# Persistent Notes Skill

메모를 로컬 `/mnt/workspace/notes.json` 파일에 저장하는 skill입니다.

## 사용법

```bash
python3 persistent-notes/scripts/note_manager.py "Your note here"
```

## 동작

- 현재 디렉터리의 `/mnt/workspace/notes.json`에 메모 저장
- 기존 메모에 새 메모 추가
- 각 메모에 content 및 timestamp 포함
- JSON 확인 응답 반환

## 예제

```bash
python3 persistent-notes/scripts/note_manager.py "Remember to deploy on Friday"
```

## 파일 구조

```
persistent-notes/
├── SKILL.md              # Skill 문서
├── README.md             # 이 파일
└── scripts/
    └── note_manager.py   # 메모 저장 스크립트
```

## 메모 형식

메모는 `notes.json`에 JSON 배열로 저장됩니다.

```json
[
  {
    "content": "Your note content",
    "timestamp": "2026-03-19T10:30:00.123456"
  }
]
```

이것으로 영구 저장을 지원하는 간단한 메모 저장 기능이 완성됩니다.
