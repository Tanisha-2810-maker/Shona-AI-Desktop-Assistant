from typing import Callable, Optional

try:
    import keyboard
except ImportError:
    keyboard = None


_registered_hotkey: Optional[str] = None


def register_global_hotkey(
    callback: Callable[[], None],
    shortcut: str = "ctrl+space",
) -> bool:
    """
    Registers a Windows-wide keyboard shortcut.

    The keyboard callback runs outside Tkinter's UI thread,
    so the caller should use window.after(...) inside callback.
    """
    global _registered_hotkey

    if keyboard is None:
        return False

    unregister_global_hotkey()

    keyboard.add_hotkey(
        shortcut,
        callback,
        suppress=False,
        trigger_on_release=True,
    )

    _registered_hotkey = shortcut
    return True


def unregister_global_hotkey() -> None:
    global _registered_hotkey

    if keyboard is None or _registered_hotkey is None:
        return

    try:
        keyboard.remove_hotkey(_registered_hotkey)
    except (KeyError, ValueError):
        pass

    _registered_hotkey = None
