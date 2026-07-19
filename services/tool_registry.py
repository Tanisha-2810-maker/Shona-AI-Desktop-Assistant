from pathlib import Path
from typing import Any, Dict

from assistant.ai_brain import ask_ai
from assistant.browser_agent import search_and_summarize
from assistant.vision_actions import analyze_current_screen


SAFE_OUTPUT_FOLDER = Path.home() / "Documents" / "Shona Outputs"


def _resolve_previous(value: Any, previous_output: str) -> Any:
    if isinstance(value, str):
        return value.replace("$previous", previous_output)

    if isinstance(value, dict):
        return {
            key: _resolve_previous(item, previous_output)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _resolve_previous(item, previous_output)
            for item in value
        ]

    return value


def run_tool(
    tool: str,
    action: str,
    arguments: Dict[str, Any],
    previous_output: str = "",
) -> str:
    resolved = _resolve_previous(arguments, previous_output)

    if tool == "browser" and action == "research":
        query = str(resolved.get("query", "")).strip()

        if not query:
            raise ValueError("Browser research requires a query.")

        return search_and_summarize(query)

    if tool == "vision":
        return analyze_current_screen(action)

    if tool == "ai" and action == "summarize":
        content = str(resolved.get("content", previous_output)).strip()

        if not content:
            raise ValueError("There is no content to summarize.")

        return ask_ai(
            "Summarize the following content clearly and concisely:\n\n"
            + content
        )

    if tool == "ai" and action == "rewrite":
        content = str(resolved.get("content", previous_output)).strip()
        instruction = str(
            resolved.get(
                "instruction",
                "Rewrite this clearly and professionally.",
            )
        ).strip()

        if not content:
            raise ValueError("There is no content to rewrite.")

        return ask_ai(
            f"{instruction}\n\nContent:\n{content}"
        )

    if tool == "files" and action == "save_text":
        filename = str(
            resolved.get("filename", "shona_output.txt")
        ).strip()

        content = str(
            resolved.get("content", previous_output)
        ).strip()

        if not filename.lower().endswith(".txt"):
            filename += ".txt"

        safe_name = Path(filename).name
        SAFE_OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

        output_path = SAFE_OUTPUT_FOLDER / safe_name
        output_path.write_text(content, encoding="utf-8")

        return f"Saved the result to {output_path}."

    raise ValueError(f"Unsupported tool action: {tool}/{action}")
