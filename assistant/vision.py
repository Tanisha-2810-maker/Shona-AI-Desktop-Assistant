import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.1-flash-lite",
)

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from the .env file."
    )

client = genai.Client(api_key=API_KEY)


def analyze_image(
    image_path: Path,
    prompt: str,
) -> str:
    if not image_path.exists():
        raise FileNotFoundError(
            f"Image was not found: {image_path}"
        )

    image_part = types.Part.from_bytes(
        data=image_path.read_bytes(),
        mime_type="image/png",
    )

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                prompt,
                image_part,
            ],
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=1200,
            ),
        )

        if response.text:
            return response.text.strip()

        return "I could not understand the screen image."

    except Exception as error:
        print(f"Vision error: {error}")

        return (
            "I could not analyze the screen right now. "
            "Please check the terminal for details."
        )