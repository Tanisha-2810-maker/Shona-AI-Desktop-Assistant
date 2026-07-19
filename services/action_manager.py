from dataclasses import dataclass
from typing import Callable, Optional

from assistant.ai_brain import ask_ai
from assistant.browser_agent import search_and_summarize
from assistant.long_term_memory import (
    add_memory,
    build_memory_context,
    clear_all_memories,
    extract_memory_to_forget,
    extract_memory_to_save,
    forget_matching_memory,
    is_clear_all_memory_command,
    is_memory_list_command,
    list_memories,
)
from assistant.reminder_manager import format_duration, parse_reminder, schedule_reminder
from assistant.vision_actions import analyze_current_screen, detect_vision_command
from system.commands import handle_system_command
from assistant.planner import create_plan
from assistant.executor import execute_plan


@dataclass
class ActionResult:
    response: str
    voice_line: str
    action_type: str
    success: bool = True


def extract_browser_query(command: str) -> Optional[str]:
    lowered = command.lower().strip()
    prefixes = [
        "search and summarize ",
        "search and summarise ",
        "find and summarize ",
        "find and summarise ",
        "find information about ",
        "research ",
    ]
    for prefix in prefixes:
        if lowered.startswith(prefix):
            return command[len(prefix):].strip()
    return None


def extract_agent_goal(command: str) -> Optional[str]:
    lowered = command.lower().strip()

    explicit_prefixes = [
        "agent task ",
        "agent task: ",
        "plan and execute ",
        "plan and execute: ",
        "do this task ",
        "do this task: ",
        "complete this task ",
        "complete this task: ",
    ]

    for prefix in explicit_prefixes:
        if lowered.startswith(prefix):
            return command[len(prefix):].strip()

    multi_step_signals = [
        " and save ",
        " then save ",
        " and summarize ",
        " and summarise ",
        " then summarize ",
        " then summarise ",
    ]

    action_starts = (
        "research ",
        "find ",
        "describe ",
        "analyze ",
        "analyse ",
        "review ",
    )

    if lowered.startswith(action_starts) and any(
        signal in lowered
        for signal in multi_step_signals
    ):
        return command.strip()

    return None


def format_plan_preview(plan) -> str:
    lines = []

    for index, step in enumerate(plan.steps, start=1):
        description = step.description or f"{step.tool}: {step.action}"
        lines.append(f"{index}. {description}")

    return "\n".join(lines)


class ActionManager:
    def __init__(
        self,
        reminder_callback: Optional[Callable[[str], None]] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        self.reminder_callback = reminder_callback
        self.progress_callback = progress_callback
        self.pending_plan = None

    def execute(
        self,
        command: str,
        conversation_context: str = "",
        response_style_instruction: str = "",
    ) -> ActionResult:
        clean_command = command.strip()

        if not clean_command:
            return ActionResult(
                "I did not hear you properly. Please try again.",
                "I did not hear you properly. Please try again.",
                "empty",
                False,
            )

        lowered = clean_command.lower()

        if is_clear_all_memory_command(clean_command):
            clear_all_memories()
            return ActionResult(
                "I cleared all saved personal memories. Your chat history was not deleted.",
                "I cleared all saved memories.",
                "memory_clear_all",
            )

        memory_to_save = extract_memory_to_save(clean_command)
        if memory_to_save:
            if add_memory(memory_to_save):
                return ActionResult(
                    f"I'll remember that {memory_to_save}.",
                    "I saved that in memory.",
                    "memory_save",
                )
            return ActionResult(
                "I already have that information saved in my memory.",
                "I already remember that.",
                "memory_save_duplicate",
            )

        memory_to_forget = extract_memory_to_forget(clean_command)
        if memory_to_forget:
            removed = forget_matching_memory(memory_to_forget)
            if removed:
                return ActionResult(
                    f"I forgot {removed} matching memory item.",
                    "I removed that from memory.",
                    "memory_forget",
                )
            return ActionResult(
                f"I could not find a saved memory matching '{memory_to_forget}'.",
                "I could not find that memory.",
                "memory_forget_missing",
                False,
            )

        if is_memory_list_command(clean_command):
            memories = list_memories()
            if not memories:
                return ActionResult(
                    "I do not have any long-term personal memories saved yet.",
                    "I do not have any saved memories yet.",
                    "memory_list",
                )

            formatted = "\n".join(
                f"{index}. {memory}"
                for index, memory in enumerate(memories, start=1)
            )

            return ActionResult(
                f"Here is what I remember about you:\n\n{formatted}",
                "Here is what I remember about you.",
                "memory_list",
            )

        # -------------------------------------------------
        # AGENT TASK CONFIRMATION / CANCELLATION
        # -------------------------------------------------

        confirm_phrases = {
            "confirm task",
            "confirm the task",
            "start task",
            "start the task",
            "execute task",
            "execute the task",
            "yes execute",
            "yes start it",
            "proceed with the task",
        }

        cancel_phrases = {
            "cancel task",
            "cancel the task",
            "discard task",
            "discard the task",
            "stop task",
            "do not execute",
            "don't execute",
        }

        if lowered in cancel_phrases:
            if self.pending_plan is None:
                return ActionResult(
                    "There is no pending agent task to cancel.",
                    "There is no pending task.",
                    "agent_cancel_missing",
                    False,
                )

            self.pending_plan = None

            return ActionResult(
                "The pending agent task has been cancelled.",
                "The task has been cancelled.",
                "agent_cancel",
            )

        if lowered in confirm_phrases:
            if self.pending_plan is None:
                return ActionResult(
                    "There is no pending agent task to execute.",
                    "There is no pending task.",
                    "agent_confirm_missing",
                    False,
                )

            plan_to_execute = self.pending_plan
            self.pending_plan = None

            try:
                execution = execute_plan(
                    plan_to_execute,
                    progress_callback=self.progress_callback,
                )

                return ActionResult(
                    execution.response,
                    (
                        "The task is complete."
                        if execution.success
                        else "The task could not be completed."
                    ),
                    "agent_task",
                    execution.success,
                )

            except Exception as error:
                return ActionResult(
                    (
                        "I could not execute the confirmed task.\n\n"
                        f"Reason: {error}"
                    ),
                    "I could not complete that task.",
                    "agent_task",
                    False,
                )

        agent_goal = extract_agent_goal(clean_command)

        if agent_goal:
            try:
                plan = create_plan(agent_goal)
                self.pending_plan = plan

                preview = format_plan_preview(plan)

                return ActionResult(
                    (
                        "I created the following task plan:\n\n"
                        f"{preview}\n\n"
                        "Say “confirm task” to begin or "
                        "“cancel task” to discard it."
                    ),
                    "I created a task plan. Please confirm it before I begin.",
                    "agent_plan_pending",
                )

            except Exception as error:
                return ActionResult(
                    (
                        "I could not create that task plan.\n\n"
                        f"Reason: {error}"
                    ),
                    "I could not create the task plan.",
                    "agent_plan_error",
                    False,
                )

        vision_type = detect_vision_command(clean_command)
        if vision_type:
            response = analyze_current_screen(vision_type)
            voice_lines = {
                "screen": "Here is what I can see on your screen.",
                "error": "I analyzed the visible error.",
                "code": "I analyzed the visible code.",
                "webpage": "Here is the webpage summary.",
                "diagram": "Here is the explanation.",
                "ui": "Here is my interface review.",
                "read_text": "Here is the visible text.",
                "copy_text": "I extracted the visible text and copied it to your clipboard.",
            }
            return ActionResult(
                response,
                voice_lines.get(vision_type, "Here is my screen analysis."),
                f"vision:{vision_type}",
            )

        browser_query = extract_browser_query(clean_command)
        if browser_query:
            return ActionResult(
                search_and_summarize(browser_query),
                "I searched the web and summarized the results for you.",
                "browser_research",
            )

        reminder = parse_reminder(clean_command)
        if reminder:
            if self.reminder_callback is None:
                return ActionResult(
                    "I understood the reminder, but the reminder system is not connected.",
                    "The reminder system is not connected.",
                    "reminder",
                    False,
                )

            schedule_reminder(reminder, self.reminder_callback)
            duration = format_duration(reminder.seconds)

            return ActionResult(
                f"Reminder set for {duration}: {reminder.message}",
                f"Reminder set for {duration}.",
                "reminder",
            )

        if any(
            phrase in lowered
            for phrase in ["goodbye", "exit assistant", "close shona"]
        ):
            return ActionResult(
                "Goodbye. Have a lovely day!",
                "Goodbye. Have a lovely day!",
                "exit",
            )

        system_response = handle_system_command(lowered)
        if system_response:
            return ActionResult(
                system_response,
                system_response,
                "system",
            )

        memory_context = build_memory_context(limit=20)

        prompt = f"""
You are Shona, a friendly AI desktop assistant.

Use conversation context and saved user memories only when relevant.
Do not mention that hidden context or memory was supplied.
Do not claim a memory is true unless it appears in the saved memory list.

Response style:
{response_style_instruction or "Give a clear, balanced answer."}

Saved user memories:
{memory_context}

Recent conversation:
{conversation_context or "No recent conversation context."}

Latest user request:
{clean_command}
"""

        response = ask_ai(prompt)

        if "email" in lowered:
            voice_line = "Here is your email."
        elif "application" in lowered:
            voice_line = "Here is your application."
        elif "note" in lowered:
            voice_line = "Here is your note."
        elif "explain" in lowered:
            voice_line = "Here is the explanation."
        elif "summary" in lowered or "summarize" in lowered:
            voice_line = "Here is the summary."
        else:
            voice_line = "Here is your answer."

        return ActionResult(
            response,
            voice_line,
            "ai_chat",
        )