from pathlib import Path

from assistant.vision import analyze_image


ERROR_SOLVER_PROMPT = """
Carefully inspect the screenshot for a programming error, traceback,
failed command, warning, or code problem.

Respond using this structure:

ERROR IDENTIFIED
Explain the visible error in simple language.

LIKELY CAUSE
State the most likely reason it happened.

HOW TO FIX IT
Give clear numbered steps.

CORRECTED CODE
Provide corrected code only when enough code is visible.

IMPORTANT
Do not invent filenames, variables, or code that cannot be seen.
Clearly mention when some information is not visible.
"""


CODE_REVIEW_PROMPT = """
Review the programming code visible in the screenshot.

Explain:

1. What the code does
2. Any visible bugs
3. Possible runtime errors
4. Security or reliability problems
5. Readability and structure improvements
6. A corrected version when enough code is visible

Do not invent code that is outside the visible screen.
Use clear headings and readable formatting.
"""


def solve_visible_error(image_path: Path) -> str:
    return analyze_image(
        image_path,
        ERROR_SOLVER_PROMPT,
    )


def review_visible_code(image_path: Path) -> str:
    return analyze_image(
        image_path,
        CODE_REVIEW_PROMPT,
    )