from assistant.vision import analyze_image
from system.screenshot import capture_screen

import pyperclip

from assistant.ocr import extract_text_from_image

from assistant.code_vision import (
    solve_visible_error,
    review_visible_code,
)
VISION_COMMANDS = {
    "screen": [
        "what is on my screen",
        "what's on my screen",
        "describe my screen",
        "explain my screen",
        "explain this screen",
    ],
    "error": [
        "explain this error",
        "solve this error",
        "fix this error",
        "explain this traceback",
        "solve this traceback",
        "why am i getting this error",
    ],
    "code": [
        "explain this code",
        "review this code",
        "find bugs in this code",
        "fix the visible code",
        "improve this code",
    ],
    "webpage": [
        "summarize this webpage",
        "summarise this webpage",
        "explain this webpage",
        "review this website",
        "review this webpage",
    ],
    "diagram": [
        "explain this diagram",
        "explain this graph",
        "explain this chart",
        "explain this flowchart",
    ],
    "read_text": [
        "read this screen",
        "read my screen",
        "read this page",
        "read this document",
        "extract text from screen",
        "extract the text from screen",
    ],

    "copy_text": [
        "copy text from screen",
        "copy all text from screen",
        "copy the text on my screen",
        "extract and copy text",
    ],
    "ui": [
        "review this ui",
        "review this design",
        "how can i improve this ui",
        "how can i improve this design",
    ],
}


VISION_PROMPTS = {
    "screen": """
Describe what is currently visible on the screen.

Mention:
- The application or website that is open
- Important visible text
- Buttons, panels, menus or windows
- Any warnings, errors or notifications
- What the user appears to be doing

Give a clear and concise explanation.
""",

    "error": """
Inspect the visible screen carefully and identify any error,
traceback, warning or failed command.

Explain:
1. What the error means
2. The most likely cause
3. The exact steps needed to fix it
4. Corrected code when enough code is visible

Do not invent details that cannot be seen.
""",

    "code": """
Analyze the code visible on the screen.

Explain:
- What the code does
- The important functions or classes
- Any visible bugs or risky parts
- How it could be improved

Use simple language and include corrected code only when useful.
""",

    "webpage": """
Analyze the webpage currently visible on the screen.

Provide:
- A short summary of the page
- The main visible information
- Important buttons, links or sections
- Any usability or content observations

Do not claim to see content outside the visible screen.
""",

    "diagram": """
Explain the visible diagram, graph, chart or flowchart.

Describe:
- What it represents
- The important labels and relationships
- The main conclusion or meaning
- Any visible trend or process

Use clear student-friendly language.
""",

    "ui": """
Review the visible user interface as a UI/UX designer.

Evaluate:
- Layout and alignment
- Visual hierarchy
- Spacing and readability
- Colours and consistency
- Buttons and navigation
- Responsiveness concerns that can be inferred

Give practical improvements in priority order.
""",
}


def detect_vision_command(command: str):
    lowered = command.lower().strip()

    for vision_type, phrases in VISION_COMMANDS.items():
        if any(phrase in lowered for phrase in phrases):
            return vision_type

    return None


def analyze_current_screen(vision_type: str) -> str:
    screenshot_path = capture_screen()

    if vision_type == "read_text":
        return extract_text_from_image(screenshot_path)

    if vision_type == "code":
        return review_visible_code(screenshot_path)

    if vision_type == "read_text":
        return extract_text_from_image(screenshot_path)


    if vision_type == "copy_text":
        extracted_text = extract_text_from_image(
            screenshot_path
        )

        if extracted_text.startswith(
            "I could not find readable text"
        ):
            return extracted_text

        pyperclip.copy(extracted_text)

        return (
            "I extracted the visible text and copied it "
            "to your clipboard.\n\n"
            f"{extracted_text}"
        )

    prompt = VISION_PROMPTS.get(
        vision_type,
        VISION_PROMPTS["screen"],
    )

    return analyze_image(
        screenshot_path,
        prompt,
    )