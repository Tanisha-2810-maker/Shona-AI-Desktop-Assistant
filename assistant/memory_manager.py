import json
from pathlib import Path
from typing import Dict, List

MEMORY_FOLDER = Path.home() / ".mini_siri"
MEMORY_FILE = MEMORY_FOLDER / "chat_history.json"
MAX_SAVED_MESSAGES = 30

def load_chat_history() -> List[Dict[str, str]]:
    if not MEMORY_FILE.exists():
        return []
    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        cleaned = []
        for item in data[-MAX_SAVED_MESSAGES:]:
            if not isinstance(item, dict):
                continue
            sender = str(item.get("sender", "")).strip()
            message = str(item.get("message", "")).strip()
            if sender and message:
                cleaned.append({"sender": sender, "message": message})
        return cleaned
    except (OSError, json.JSONDecodeError):
        return []

def save_chat_history(messages: List[Dict[str, str]]) -> None:
    MEMORY_FOLDER.mkdir(parents=True, exist_ok=True)
    safe_messages = []
    for item in messages[-MAX_SAVED_MESSAGES:]:
        sender = str(item.get("sender", "")).strip()
        message = str(item.get("message", "")).strip()
        if sender and message:
            safe_messages.append({"sender": sender, "message": message})
    MEMORY_FILE.write_text(
        json.dumps(safe_messages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def clear_chat_history() -> None:
    try:
        if MEMORY_FILE.exists():
            MEMORY_FILE.unlink()
    except OSError:
        pass

def build_conversation_context(messages: List[Dict[str, str]], limit: int = 10) -> str:
    recent_messages = messages[-limit:]
    lines = []
    for item in recent_messages:
        sender = item.get("sender", "")
        message = item.get("message", "")
        role = "User" if sender == "You" else "Assistant"
        lines.append(f"{role}: {message}")
    return "\n".join(lines)
