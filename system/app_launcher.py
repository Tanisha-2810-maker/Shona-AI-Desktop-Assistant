import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional


START_MENU_FOLDERS = [
    Path(os.environ.get("APPDATA", ""))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs",

    Path(os.environ.get("PROGRAMDATA", ""))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs",
]


EXCLUDED_WORDS = {
    "uninstall",
    "help",
    "readme",
    "documentation",
    "license",
    "website",
}


# Special Windows URI commands for Store applications.
APP_URIS = {
    "spotify": "spotify:",
    "whatsapp": "whatsapp:",
    "settings": "ms-settings:",
    "calculator": "calculator:",
}


# Common installation locations that may not have Start Menu shortcuts.
KNOWN_PATHS = {
    "spotify": [
        Path(os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")),
        Path(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe")),
    ],

    "chrome": [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ],

    "vscode": [
        Path(
            os.path.expandvars(
                r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"
            )
        ),
        Path(r"C:\Program Files\Microsoft VS Code\Code.exe"),
    ],

    "visual studio code": [
        Path(
            os.path.expandvars(
                r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"
            )
        ),
        Path(r"C:\Program Files\Microsoft VS Code\Code.exe"),
    ],
}


def normalize_app_name(name: str) -> str:
    cleaned = name.lower().strip()

    replacements = [
        "microsoft ",
        " app",
        " application",
        ".exe",
    ]

    for value in replacements:
        cleaned = cleaned.replace(value, "")

    return " ".join(cleaned.split())


def scan_start_menu_apps() -> Dict[str, Path]:
    apps: Dict[str, Path] = {}

    for folder in START_MENU_FOLDERS:
        if not folder.exists():
            continue

        try:
            for shortcut in folder.rglob("*.lnk"):
                normalized = normalize_app_name(shortcut.stem)

                if not normalized:
                    continue

                if any(
                    word in normalized
                    for word in EXCLUDED_WORDS
                ):
                    continue

                apps.setdefault(normalized, shortcut)

        except (PermissionError, OSError):
            continue

    return apps


def find_app_shortcut(app_name: str) -> Optional[Path]:
    requested = normalize_app_name(app_name)
    apps = scan_start_menu_apps()

    if requested in apps:
        return apps[requested]

    prefix_matches = [
        (name, path)
        for name, path in apps.items()
        if name.startswith(requested)
    ]

    if prefix_matches:
        prefix_matches.sort(
            key=lambda item: len(item[0])
        )
        return prefix_matches[0][1]

    partial_matches = [
        (name, path)
        for name, path in apps.items()
        if requested in name or name in requested
    ]

    if partial_matches:
        partial_matches.sort(
            key=lambda item: abs(
                len(item[0]) - len(requested)
            )
        )
        return partial_matches[0][1]

    return None


def _open_known_path(app_name: str) -> bool:
    normalized = normalize_app_name(app_name)

    for app_path in KNOWN_PATHS.get(normalized, []):
        if app_path.exists():
            subprocess.Popen([str(app_path)])
            return True

    return False


def _open_uri(app_name: str) -> bool:
    normalized = normalize_app_name(app_name)
    uri = APP_URIS.get(normalized)

    if not uri:
        return False

    try:
        os.startfile(uri)
        return True
    except OSError:
        return False


def _open_from_path_environment(app_name: str) -> bool:
    executable = shutil.which(app_name)

    if not executable:
        executable = shutil.which(f"{app_name}.exe")

    if executable:
        subprocess.Popen([executable])
        return True

    return False


def open_installed_app(app_name: str) -> bool:
    normalized = normalize_app_name(app_name)

    # 1. Known executable paths
    if _open_known_path(normalized):
        return True

    # 2. Start Menu shortcuts
    shortcut = find_app_shortcut(normalized)

    if shortcut is not None:
        os.startfile(shortcut)
        return True

    # 3. Windows application URI
    if _open_uri(normalized):
        return True

    # 4. Executables available through PATH
    if _open_from_path_environment(normalized):
        return True

    return False


def get_installed_app_names(limit: int = 40):
    names = set(scan_start_menu_apps().keys())
    names.update(APP_URIS.keys())
    names.update(KNOWN_PATHS.keys())

    return sorted(names)[:limit]