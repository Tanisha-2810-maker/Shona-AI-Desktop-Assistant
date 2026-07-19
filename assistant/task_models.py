from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class TaskStep:
    tool: str
    action: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class TaskPlan:
    goal: str
    steps: List[TaskStep]
    final_response_instruction: str = ""


@dataclass
class StepResult:
    success: bool
    output: str
    tool: str
    action: str


@dataclass
class ExecutionResult:
    success: bool
    response: str
    step_results: List[StepResult]
