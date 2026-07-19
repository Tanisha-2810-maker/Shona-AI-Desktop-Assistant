from typing import List

from assistant.ai_brain import ask_ai
from assistant.task_models import StepResult, TaskPlan


def build_task_report(
    plan: TaskPlan,
    step_results: List[StepResult],
) -> str:
    completed = []
    failed = []

    for index, result in enumerate(step_results, start=1):
        output = result.output.strip()

        # Prevent extremely large browser results from being resent.
        if len(output) > 5000:
            output = output[:5000] + "\n...[shortened]"

        section = (
            f"Step {index}: {result.tool}/{result.action}\n"
            f"Status: {'Completed' if result.success else 'Failed'}\n"
            f"Output:\n{output}"
        )

        if result.success:
            completed.append(section)
        else:
            failed.append(section)

    raw_results = "\n\n".join(completed + failed)

    prompt = f"""
You are Shona, reporting the outcome of an automated task.

Original goal:
{plan.goal}

Execution details:
{raw_results}

Create a useful final response with these sections:

TASK COMPLETED
Briefly state what was done.

RESULT
Present the useful findings or summary from the completed steps.
Do not omit the important content just because a file was saved.

SAVED FILE
Mention the exact saved path when one appears in the execution details.
Omit this section when nothing was saved.

NOTES
Mention any failed step, limitation, incomplete search result, or shortened input.
Omit this section if there are no issues.

Do not invent facts, filenames, paths, results, or completed actions.
Keep the response readable and reasonably concise.
"""

    return ask_ai(prompt)
