import json
import re
from typing import Any, Dict, List

from assistant.ai_brain import ask_ai
from assistant.task_models import TaskPlan, TaskStep


ALLOWED_TOOLS = {
    "browser": {"research"},
    "vision": {"screen", "error", "code", "webpage", "ui", "read_text"},
    "files": {"save_text"},
    "ai": {"summarize", "rewrite"},
}


PLANNER_PROMPT = """
You are the planning component of Shona, a Windows desktop assistant.

Convert the user's goal into a short JSON task plan.

Allowed tools and actions:
- browser / research
- vision / screen
- vision / error
- vision / code
- vision / webpage
- vision / ui
- vision / read_text
- ai / summarize
- ai / rewrite
- files / save_text

Safety rules:
- Never plan purchases, payments, account logins, form submissions, file deletion,
  file overwriting without confirmation, shell commands, or arbitrary code execution.
- Prefer at most 5 steps.
- Use outputs from earlier steps by putting "$previous" in a later step argument.
- For files/save_text, use a simple filename ending in .txt.
- Return JSON only.

Schema:
{
  "goal": "original goal",
  "steps": [
    {
      "tool": "browser",
      "action": "research",
      "arguments": {"query": "cybersecurity internships"},
      "description": "Search and collect relevant results"
    }
  ],
  "final_response_instruction": "Briefly summarize what was completed"
}
"""


def _extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)

    if not match:
        raise ValueError("Planner did not return valid JSON.")

    return json.loads(match.group(0))


def _validate_step(raw_step: Dict[str, Any]) -> TaskStep:
    tool = str(raw_step.get("tool", "")).strip()
    action = str(raw_step.get("action", "")).strip()
    arguments = raw_step.get("arguments", {})
    description = str(raw_step.get("description", "")).strip()

    if tool not in ALLOWED_TOOLS:
        raise ValueError(f"Planner selected unsupported tool: {tool}")

    if action not in ALLOWED_TOOLS[tool]:
        raise ValueError(
            f"Planner selected unsupported action: {tool}/{action}"
        )

    if not isinstance(arguments, dict):
        raise ValueError("Step arguments must be an object.")

    return TaskStep(
        tool=tool,
        action=action,
        arguments=arguments,
        description=description or f"{tool}: {action}",
    )


def create_plan(goal: str) -> TaskPlan:
    prompt = f"""
{PLANNER_PROMPT}

User goal:
{goal}
"""

    raw_response = ask_ai(prompt)
    data = _extract_json(raw_response)

    raw_steps = data.get("steps", [])

    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("Planner returned no executable steps.")

    steps: List[TaskStep] = [
        _validate_step(step)
        for step in raw_steps[:5]
    ]

    return TaskPlan(
        goal=str(data.get("goal", goal)),
        steps=steps,
        final_response_instruction=str(
            data.get(
                "final_response_instruction",
                "Summarize what was completed.",
            )
        ),
    )
