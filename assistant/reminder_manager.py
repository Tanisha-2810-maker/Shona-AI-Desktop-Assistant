import re
import threading
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Reminder:
    message: str
    seconds: int


def parse_reminder(command: str) -> Optional[Reminder]:
    pattern = re.compile(
        r"remind me in\s+(\d+)\s*"
        r"(second|seconds|minute|minutes|hour|hours)\s+to\s+(.+)",
        re.IGNORECASE,
    )

    match = pattern.search(command.strip())

    if not match:
        return None

    amount = int(match.group(1))
    unit = match.group(2).lower()
    message = match.group(3).strip()

    multipliers = {
        "second": 1,
        "seconds": 1,
        "minute": 60,
        "minutes": 60,
        "hour": 3600,
        "hours": 3600,
    }

    return Reminder(
        message=message,
        seconds=amount * multipliers[unit],
    )


def schedule_reminder(
    reminder: Reminder,
    callback: Callable[[str], None],
) -> threading.Timer:
    timer = threading.Timer(
        reminder.seconds,
        callback,
        args=(reminder.message,),
    )
    timer.daemon = True
    timer.start()
    return timer


def format_duration(seconds: int) -> str:
    if seconds < 60:
        value = seconds
        unit = "second" if value == 1 else "seconds"
    elif seconds < 3600:
        value = seconds // 60
        unit = "minute" if value == 1 else "minutes"
    else:
        value = seconds // 3600
        unit = "hour" if value == 1 else "hours"

    return f"{value} {unit}"
