import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

DATA_FOLDER = Path.home() / ".shona"
MEMORY_FILE = DATA_FOLDER / "user_memory.json"
MAX_MEMORIES = 100

def _load_raw() -> List[Dict[str, str]]:
    if not MEMORY_FILE.exists():
        return []
    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        cleaned = []
        for item in data:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            created_at = str(item.get("created_at", "")).strip()
            if text:
                cleaned.append({"text": text, "created_at": created_at})
        return cleaned[-MAX_MEMORIES:]
    except (OSError, json.JSONDecodeError):
        return []

def _save_raw(memories: List[Dict[str, str]]) -> None:
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    MEMORY_FILE.write_text(
        json.dumps(memories[-MAX_MEMORIES:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def normalize_memory(text: str) -> str:
    return " ".join(text.strip().rstrip(".").split())

def list_memories() -> List[str]:
    return [item["text"] for item in _load_raw()]

def add_memory(text: str) -> bool:
    clean_text = normalize_memory(text)
    if not clean_text:
        return False
    memories = _load_raw()
    existing = {item["text"].lower() for item in memories}
    if clean_text.lower() in existing:
        return False
    memories.append(
        {
            "text": clean_text,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    _save_raw(memories)
    return True

def forget_matching_memory(query: str) -> int:
    clean_query = normalize_memory(query).lower()
    if not clean_query:
        return 0
    memories = _load_raw()
    remaining = []
    removed = 0
    for item in memories:
        memory_text = item["text"].lower()
        if clean_query in memory_text or memory_text in clean_query:
            removed += 1
        else:
            remaining.append(item)
    _save_raw(remaining)
    return removed

def clear_all_memories() -> None:
    _save_raw([])

def build_memory_context(limit: int = 20) -> str:
    memories = list_memories()[-limit:]
    if not memories:
        return "No saved user memories."
    return "\n".join(f"- {memory}" for memory in memories)

def extract_memory_to_save(command: str) -> Optional[str]:
    patterns = [
        r"^remember that\s+(.+)$",
        r"^remember\s+(.+)$",
        r"^please remember that\s+(.+)$",
        r"^save this in memory[:\s]+(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, command.strip(), flags=re.IGNORECASE)
        if match:
            return normalize_memory(match.group(1))
    return None

def extract_memory_to_forget(command: str) -> Optional[str]:
    patterns = [
        r"^forget that\s+(.+)$",
        r"^forget\s+(.+)$",
        r"^remove from memory[:\s]+(.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, command.strip(), flags=re.IGNORECASE)
        if match:
            return normalize_memory(match.group(1))
    return None

def is_memory_list_command(command: str) -> bool:
    lowered = command.lower().strip()
    return lowered in {
        "what do you remember about me",
        "what do you remember",
        "show my memories",
        "list my memories",
        "what do you know about me",
    }

def is_clear_all_memory_command(command: str) -> bool:
    lowered = command.lower().strip()
    return lowered in {
        "forget everything you remember about me",
        "clear all memories",
        "delete all memories",
        "forget everything about me",
    }
