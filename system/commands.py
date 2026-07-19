import os
import shutil
import subprocess
import webbrowser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import pyautogui
import pyperclip

from assistant.vision_actions import (
    detect_vision_command,
    analyze_current_screen,
)

from system.app_launcher import open_installed_app, get_installed_app_names

try:
    import psutil
except ImportError:
    psutil = None

APP_PATHS = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "spotify": [os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe")],
    "vscode": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ],
    "visual studio code": [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe"),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ],
    "discord": [os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe")],
}

WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "linkedin": "https://www.linkedin.com",
    "chatgpt": "https://chatgpt.com",
    "instagram": "https://www.instagram.com",
}

COMMON_FOLDERS = {
    "downloads": Path.home() / "Downloads",
    "documents": Path.home() / "Documents",
    "desktop": Path.home() / "Desktop",
    "pictures": Path.home() / "Pictures",
    "videos": Path.home() / "Videos",
    "music": Path.home() / "Music",
}

SEARCH_ROOTS = list(COMMON_FOLDERS.values())


def _open_known_application(app_name):
    for app_path in APP_PATHS.get(app_name, []):
        expanded_path = os.path.expandvars(app_path)
        if not os.path.exists(expanded_path):
            continue
        if app_name == "discord" and expanded_path.endswith("Update.exe"):
            subprocess.Popen([expanded_path, "--processStart", "Discord.exe"])
        else:
            subprocess.Popen([expanded_path])
        return True
    return False


def _open_using_windows_command(app_name):
    executable = shutil.which(app_name)
    if executable:
        subprocess.Popen([executable])
        return True
    return False


def _extract_search_query(command):
    phrases = [
        "search google for", "google search for", "search for",
        "search google", "on the web", "on google", "google", "search",
    ]
    query = command.lower()
    for phrase in phrases:
        query = query.replace(phrase, " ")
    return " ".join(query.split()).strip()


def _extract_song_name(command):
    phrases = [
        "play the song", "play song", "play music",
        "on youtube", "on spotify", "play",
    ]
    song = command.lower()
    for phrase in phrases:
        song = song.replace(phrase, " ")
    return " ".join(song.split()).strip()


def _extract_named_target(command, prefixes):
    lowered = command.lower()
    for prefix in prefixes:
        if prefix in lowered:
            return lowered.split(prefix, 1)[1].strip()
    return ""


def _find_item_by_name(name, want_folder=False):
    normalized_name = name.lower().strip()
    if not normalized_name:
        return None

    for root in SEARCH_ROOTS:
        if not root.exists():
            continue
        try:
            for current_root, directories, files in os.walk(root):
                current_path = Path(current_root)
                if want_folder:
                    for directory in directories:
                        if normalized_name in directory.lower():
                            return current_path / directory
                else:
                    for filename in files:
                        stem = Path(filename).stem.lower()
                        if normalized_name == stem or normalized_name in filename.lower():
                            return current_path / filename
        except (PermissionError, OSError):
            continue
    return None


def _take_screenshot():
    one_drive = os.getenv("OneDrive")
    candidates = []
    if one_drive:
        candidates.append(Path(one_drive) / "Pictures")
    candidates.append(Path.home() / "Pictures")

    base_folder = next((folder for folder in candidates if folder.exists()), Path.home())
    screenshot_folder = base_folder / "MiniSiri Screenshots"
    screenshot_folder.mkdir(parents=True, exist_ok=True)

    filename = datetime.now().strftime("screenshot_%Y-%m-%d_%H-%M-%S.png")
    screenshot_path = screenshot_folder / filename
    pyautogui.screenshot().save(str(screenshot_path))
    print(f"Screenshot saved at: {screenshot_path}")
    return screenshot_path


def handle_system_command(command):
    
    vision_type = detect_vision_command(command)

    if vision_type:
        return analyze_current_screen(vision_type)
    
    command = command.lower().strip()

    if "what time" in command or "current time" in command:
        return f"The current time is {datetime.now().strftime('%I:%M %p')}."

    if any(phrase in command for phrase in [
        "what is the date", "today's date", "todays date", "current date"
    ]):
        return f"Today is {datetime.now().strftime('%A, %d %B %Y')}."

    if any(phrase in command for phrase in [
        "battery percentage", "battery level", "how much battery"
    ]) or command == "battery":
        if psutil is None:
            return "Please install psutil using pip install psutil to read battery information."
        battery = psutil.sensors_battery()
        if battery is None:
            return "I could not read the battery information."
        status = "charging" if battery.power_plugged else "not charging"
        return f"Your battery is at {round(battery.percent)} percent and it is {status}."

    if any(phrase in command for phrase in ["volume up", "increase volume", "raise volume"]):
        pyautogui.press("volumeup", presses=3, interval=0.08)
        return "Increasing the volume."

    if any(phrase in command for phrase in ["volume down", "decrease volume", "lower volume"]):
        pyautogui.press("volumedown", presses=3, interval=0.08)
        return "Decreasing the volume."

    if any(phrase in command for phrase in ["mute volume", "mute sound"]) or command == "mute":
        pyautogui.press("volumemute")
        return "Toggling mute."

    if any(phrase in command for phrase in ["pause music", "pause song", "resume music", "resume song"]):
        pyautogui.press("playpause")
        return "Toggling media playback."

    if "next song" in command or "next track" in command:
        pyautogui.press("nexttrack")
        return "Playing the next track."

    if "previous song" in command or "previous track" in command:
        pyautogui.press("prevtrack")
        return "Playing the previous track."

    if any(phrase in command for phrase in [
        "read clipboard", "what is in my clipboard", "what's in my clipboard", "show clipboard"
    ]):
        clipboard_text = pyperclip.paste().strip()
        if not clipboard_text:
            return "Your clipboard is empty."
        if len(clipboard_text) > 1200:
            clipboard_text = clipboard_text[:1200] + "..."
        return f"Your clipboard contains:\n\n{clipboard_text}"

    if "clear clipboard" in command:
        pyperclip.copy("")
        return "Your clipboard has been cleared."

    if any(phrase in command for phrase in [
        "take screenshot", "take a screenshot", "capture screen"
    ]) or command == "screenshot":
        try:
            screenshot_path = _take_screenshot()
            return f"Screenshot taken successfully. It was saved at {screenshot_path}."
        except Exception as error:
            print(f"Screenshot error: {error}")
            return "I could not take the screenshot. Please check the terminal for the error."

    if "lock computer" in command or "lock my computer" in command:
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
        return "Locking your computer."

    if command.startswith(("open file ", "find file ", "open the file ")):
        target = _extract_named_target(command, ["open the file ", "open file ", "find file "])
        found = _find_item_by_name(target, want_folder=False)
        if found:
            os.startfile(found)
            return f"Opening {found.name}."
        return f"I could not find a file matching {target} in your common folders."

    if command.startswith(("open folder ", "find folder ", "open the folder ")):
        target = _extract_named_target(command, ["open the folder ", "open folder ", "find folder "])
        found = _find_item_by_name(target, want_folder=True)
        if found:
            os.startfile(found)
            return f"Opening the {found.name} folder."
        return f"I could not find a folder matching {target} in your common folders."

    for folder_name, folder_path in COMMON_FOLDERS.items():
        if any(phrase in command for phrase in [
            f"open {folder_name}", f"show {folder_name}", f"open my {folder_name}"
        ]):
            candidates = [folder_path]
            one_drive = os.getenv("OneDrive")
            if one_drive:
                candidates.insert(0, Path(one_drive) / folder_name.capitalize())
            actual_path = next((path for path in candidates if path.exists()), None)
            if actual_path:
                os.startfile(actual_path)
                return f"Opening your {folder_name} folder."
            return f"I could not find your {folder_name} folder."

    utilities = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "paint": "mspaint.exe",
        "command prompt": "cmd.exe",
        "cmd": "cmd.exe",
        "file explorer": "explorer.exe",
        "task manager": "taskmgr.exe",
        "settings": "ms-settings:",
    }
    for utility_name, executable in utilities.items():
        if f"open {utility_name}" in command:
            if executable.endswith(":"):
                os.startfile(executable)
            else:
                subprocess.Popen(executable)
            return f"Opening {utility_name}."

    for website_name, website_url in WEBSITES.items():
        if f"open {website_name}" in command or f"go to {website_name}" in command:
            webbrowser.open(website_url)
            return f"Opening {website_name}."

    if "open browser" in command:
        webbrowser.open("https://www.google.com")
        return "Opening your browser."

    if command.startswith("play ") or "play song" in command:
        song_name = _extract_song_name(command)
        if song_name:
            webbrowser.open("https://www.youtube.com/results?search_query=" + quote_plus(song_name))
            return f"Searching YouTube for {song_name}."
        webbrowser.open("https://www.youtube.com")
        return "Opening YouTube."

    if command.startswith("search") or command.startswith("google") or "search google" in command:
        query = _extract_search_query(command)
        if query:
            webbrowser.open("https://www.google.com/search?q=" + quote_plus(query))
            return f"Searching Google for {query}."
        webbrowser.open("https://www.google.com")
        return "Opening Google."

    if (
        "what apps can you open" in command
        or "which apps can you open" in command
        or "list installed apps" in command
        or "show installed apps" in command
    ):
        app_names = get_installed_app_names(limit=30)

        if not app_names:
            return "I could not find any Start Menu applications."

        readable_names = ", ".join(
            name.title() for name in app_names
        )

        return (
            "I found these applications in your Start Menu:\n\n"
            f"{readable_names}"
        )

    for app_name in APP_PATHS:
        if f"open {app_name}" in command:

            # First try the hardcoded executable path.
            if _open_known_application(app_name):
                return f"Opening {app_name}."

            # Then try the smarter launcher.
            if open_installed_app(app_name):
                return f"Opening {app_name}."

            # Finally try PATH.
            if _open_using_windows_command(app_name):
                return f"Opening {app_name}."

            return (
                f"I could not find {app_name} on this computer.\n"
                "Try reinstalling it or tell me its executable path."
            )
    if command.startswith("open "):
        app_name = command.replace("open ", "", 1).strip()

        if open_installed_app(app_name):
            return f"Opening {app_name}."

        if _open_using_windows_command(app_name):
            return f"Opening {app_name}."

        return (
            f"I could not find an installed application called {app_name}. "
            "Try using its exact Start Menu name."
        )

    return None


def type_in_notepad(text):
    subprocess.Popen("notepad.exe")
    pyautogui.sleep(1.5)
    pyperclip.copy(text)
    pyautogui.hotkey("ctrl", "v")
    return "I typed the response in Notepad."


def copy_to_clipboard(text):
    pyperclip.copy(text)
    return "I copied the response to your clipboard."