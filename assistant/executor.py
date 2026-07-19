from typing import Callable, List, Optional

from assistant.task_models import (
    ExecutionResult,
    StepResult,
    TaskPlan,
)
from assistant.task_reporter import build_task_report
from services.tool_registry import run_tool


ProgressCallback = Optional[Callable[[str], None]]


def execute_plan(
    plan: TaskPlan,
    progress_callback: ProgressCallback = None,
) -> ExecutionResult:
    step_results: List[StepResult] = []
    previous_output = ""

    for index, step in enumerate(plan.steps, start=1):
        progress_message = (
            f"Step {index}/{len(plan.steps)}: "
            f"{step.description}"
        )

        if progress_callback:
            progress_callback(progress_message)

        try:
            output = run_tool(
                tool=step.tool,
                action=step.action,
                arguments=step.arguments,
                previous_output=previous_output,
            )

            step_results.append(
                StepResult(
                    success=True,
                    output=output,
                    tool=step.tool,
                    action=step.action,
                )
            )

            previous_output = output

        except Exception as error:
            step_results.append(
                StepResult(
                    success=False,
                    output=str(error),
                    tool=step.tool,
                    action=step.action,
                )
            )

            if progress_callback:
                progress_callback(
                    f"Step {index} failed. Preparing a report."
                )

            report = build_task_report(
                plan,
                step_results,
            )

            return ExecutionResult(
                success=False,
                response=report,
                step_results=step_results,
            )

    if progress_callback:
        progress_callback(
            "All steps completed. Preparing the final report."
        )

    report = build_task_report(
        plan,
        step_results,
    )

    return ExecutionResult(
        success=True,
        response=report,
        step_results=step_results,
    )