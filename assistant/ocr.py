from pathlib import Path

from assistant.vision import analyze_image


OCR_PROMPT = """
Read all clearly visible text from this screenshot.

Rules:
- Preserve headings and paragraph order.
- Preserve code formatting when code is visible.
- Include error messages exactly when possible.
- Do not describe the visual design.
- Do not invent missing or unreadable text.
- Return only the extracted text.
"""


def extract_text_from_image(image_path: Path) -> str:
    result = analyze_image(
        image_path,
        OCR_PROMPT,
    )

    if not result or not result.strip():
        return "I could not find readable text on the screen."

    return result.strip()