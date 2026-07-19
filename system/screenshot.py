from pathlib import Path
import tempfile

import mss
from PIL import Image


def capture_screen():
    """
    Captures the primary monitor.

    Returns:
        pathlib.Path
    """

    temp_dir = Path(tempfile.gettempdir())
    screenshot_path = temp_dir / "shona_screen.png"

    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)

        image = Image.frombytes(
            "RGB",
            shot.size,
            shot.rgb,
        )

        image.save(screenshot_path)

    return screenshot_path