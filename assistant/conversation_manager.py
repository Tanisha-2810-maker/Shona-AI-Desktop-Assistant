import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


DATA_FOLDER = Path.home() / ".mini_siri"
CONVERSATIONS_FILE = DATA_FOLDER / "conversations.json"


def _load_raw() -> List[Dict]:
    if not CONVERSATIONS_FILE.exists():
        return []

    try:
        data = json.loads(
            CONVERSATIONS_FILE.read_text(encoding="utf-8")
        )

        if isinstance(data, list):
            return data

    except (OSError, json.JSONDecodeError):
        pass

    return []


def _save_raw(conversations: List[Dict]) -> None:
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)

    CONVERSATIONS_FILE.write_text(
        json.dumps(
            conversations,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def list_conversations() -> List[Dict]:
    conversations = _load_raw()

    conversations.sort(
        key=lambda item: item.get("updated_at", ""),
        reverse=True,
    )

    return conversations


def create_conversation(
    title: str = "New Chat",
) -> Dict:
    now = datetime.now().isoformat(timespec="seconds")

    conversation = {
        "id": str(uuid.uuid4()),
        "title": title,
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }

    conversations = _load_raw()
    conversations.append(conversation)
    _save_raw(conversations)

    return conversation


def get_conversation(
    conversation_id: str,
) -> Optional[Dict]:
    for conversation in _load_raw():
        if conversation.get("id") == conversation_id:
            return conversation

    return None


def save_conversation(
    conversation_id: str,
    messages: List[Dict[str, str]],
    title: Optional[str] = None,
) -> None:
    conversations = _load_raw()
    now = datetime.now().isoformat(timespec="seconds")

    for conversation in conversations:
        if conversation.get("id") != conversation_id:
            continue

        conversation["messages"] = messages[-60:]
        conversation["updated_at"] = now

        if title:
            conversation["title"] = title

        _save_raw(conversations)
        return


def delete_conversation(conversation_id: str) -> None:
    conversations = [
        conversation
        for conversation in _load_raw()
        if conversation.get("id") != conversation_id
    ]

    _save_raw(conversations)


def generate_title(messages: List[Dict[str, str]]) -> str:
    for item in messages:
        if item.get("sender") != "You":
            continue

        text = item.get("message", "").strip()

        if not text:
            continue

        words = text.split()
        title = " ".join(words[:6])

        if len(words) > 6:
            title += "..."

        return title

    return "New Chat"
