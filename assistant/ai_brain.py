import os
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types


load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

_client: Optional[genai.Client] = None


def _get_client() -> genai.Client:
    global _client

    if not API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Add it to your .env file."
        )

    if _client is None:
        _client = genai.Client(api_key=API_KEY)

    return _client


def ask_ai(prompt: str) -> str:
    """
    Sends a text prompt to Gemini and returns a clean text response.
    This function is used by chat, email generation, PDF summaries,
    conversation memory, and other Mini Siri AI features.
    """

    if not prompt or not prompt.strip():
        return "Please give me a question or instruction."

    try:
        client = _get_client()

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt.strip(),
            config=types.GenerateContentConfig(
                temperature=0.6,
                max_output_tokens=1200,
            ),
        )

        text = getattr(response, "text", None)

        if text and text.strip():
            return text.strip()

        return "I could not generate a text response for that request."

    except Exception as error:
        print(f"Gemini error: {error}")

        error_text = str(error).lower()

        if "429" in error_text or "quota" in error_text:
            return (
                "The Gemini usage limit has been reached temporarily. "
                "Please wait a little and try again."
            )

        if "api key" in error_text or "api_key" in error_text:
            return (
                "The Gemini API key is missing or invalid. "
                "Please check the GEMINI_API_KEY value in your .env file."
            )

        if "model" in error_text and (
            "not found" in error_text
            or "404" in error_text
        ):
            return (
                f"The configured Gemini model '{MODEL_NAME}' is unavailable. "
                "Please update GEMINI_MODEL in your .env file."
            )

        if "network" in error_text or "connection" in error_text:
            return (
                "I could not connect to Gemini. "
                "Please check your internet connection."
            )

        return (
            "I could not generate an answer right now. "
            "Please check the terminal for the detailed error."
        )