import json
from pathlib import Path
from typing import Any, Dict

SETTINGS_FOLDER = Path.home() / ".mini_siri"
SETTINGS_FILE = SETTINGS_FOLDER / "settings.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "user_name": "Tanisha",
    "response_style": "Balanced",
    "voice_enabled": True,
    "restore_history": True,
}


def load_settings() -> Dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()

    try:
        saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))

        if not isinstance(saved, dict):
            return DEFAULT_SETTINGS.copy()

        settings = DEFAULT_SETTINGS.copy()
        settings.update(saved)
        return settings

    except (OSError, json.JSONDecodeError):
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: Dict[str, Any]) -> None:
    SETTINGS_FOLDER.mkdir(parents=True, exist_ok=True)

    safe_settings = DEFAULT_SETTINGS.copy()
    safe_settings.update(settings)

    SETTINGS_FILE.write_text(
        json.dumps(safe_settings, indent=2),
        encoding="utf-8",
    )
