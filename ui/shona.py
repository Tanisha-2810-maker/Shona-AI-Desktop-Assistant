import math
import threading
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
import customtkinter as ctk

from assistant.vision_actions import (
    detect_vision_command,
    analyze_current_screen,
)
from assistant.voice import speak, listen
from system.commands import (
    handle_system_command,
    type_in_notepad,
    copy_to_clipboard,
)
from assistant.ai_brain import ask_ai
from assistant.reminder_manager import parse_reminder, schedule_reminder, format_duration
from assistant.memory_manager import build_conversation_context
from assistant.preferences_manager import load_settings, save_settings
from assistant.conversation_manager import (
    list_conversations,
    create_conversation,
    get_conversation,
    save_conversation,
    delete_conversation,
    generate_title,
)

from assistant.browser_agent import search_and_summarize

from services.action_manager import ActionManager

from ui.floating_orb import FloatingShonaOrb
from system.hotkeys import (
    register_global_hotkey,
    unregister_global_hotkey,
)

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None


ctk.set_appearance_mode("light")


def process_command(command: str):
    command = command.strip()

    if not command:
        return (
            "I did not hear you properly. Please try again.",
            "I did not hear you properly. Please try again.",
        )

    lowered = command.lower()
    

    if any(word in lowered for word in ["goodbye", "bye", "exit assistant"]):
        return "Goodbye. Have a lovely day!", "Goodbye. Have a lovely day!"

    if "type in notepad" in lowered or "write in notepad" in lowered:
        ai_response = ask_ai(command)
        type_in_notepad(ai_response)
        return ai_response, "Done. I typed it in Notepad."

    if lowered.startswith("copy ") or "copy this" in lowered:
        ai_response = ask_ai(command)
        copy_to_clipboard(ai_response)
        return ai_response, "Done. I copied it to your clipboard."

    system_response = handle_system_command(lowered)
    if system_response:
        return system_response, system_response
    
    

    ai_response = ask_ai(command)

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

    return ai_response, voice_line

def extract_agent_search_query(command: str):
    lowered = command.lower().strip()

    prefixes = [
        "search and summarize ",
        "search and summarise ",
        "find and summarize ",
        "find and summarise ",
        "research ",
        "find information about ",
    ]

    for prefix in prefixes:
        if lowered.startswith(prefix):
            return command[len(prefix):].strip()

    return None


class ShonaApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Shona")
        self.geometry("1480x800")
        self.minsize(1280, 720)
        self.configure(fg_color="#F4EEF8")

        self.is_processing = False
        self.orb_running = False
        self.orb_step = 0
        self.typing_row = None
        self.typing_label = None
        self.typing_running = False
        self.typing_step = 0
        self.last_assistant_response = ""
        self.chat_messages = []
        self.active_reminders = []
        self.is_restoring_history = False
        self.settings = load_settings()
        self.current_conversation_id = None
        self.conversation_buttons = []

        self.action_manager = ActionManager(
            reminder_callback=self._reminder_due_from_thread,
            progress_callback=self._agent_progress_from_thread,
        )

        self._build_layout()
        self._draw_orb()
        self._restore_previous_chat()
        self.input_box.focus()
        
        self.floating_orb = FloatingShonaOrb(
            parent=self,
            toggle_callback=self._toggle_window_visibility,
            exit_callback=self._exit_shona,
        )

        hotkey_registered = register_global_hotkey(
            callback=self._hotkey_toggle,
            shortcut="ctrl+space",
        )

        if not hotkey_registered:
            print(
                "Global shortcut could not be registered. "
                "Install it using: pip install keyboard"
            )

        # Clicking X hides Shona into the floating orb.
        self.protocol(
            "WM_DELETE_WINDOW",
            self._hide_to_floating_orb,
        )

    # --------------------------------------------------
    # LAYOUT
    # --------------------------------------------------

    def _build_layout(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.chat_drawer_open = True
        self.history_drawer_open = True

        self.shell = ctk.CTkFrame(
            self,
            corner_radius=34,
            fg_color="#F7F2FA",
            border_width=1,
            border_color="#E8DFF0",
        )
        self.shell.grid(
            row=0,
            column=0,
            padx=26,
            pady=24,
            sticky="nsew",
        )
        self.shell.grid_columnconfigure(0, weight=0)
        self.shell.grid_columnconfigure(
            1,
            weight=0 if self.history_drawer_open else 1,
        )
        self.shell.grid_columnconfigure(2, weight=1)
        self.shell.grid_columnconfigure(3, weight=1)
        self.shell.grid_rowconfigure(0, weight=1)

        self._build_history_panel(self.shell)
        self._build_left_panel(self.shell)
        self._build_voice_panel(self.shell)
        self._build_chat_panel(self.shell)

        # This slim tab appears only when Smart Chat is collapsed.
        self.chat_reopen_button = ctk.CTkButton(
            self.shell,
            text="💬",
            width=48,
            height=112,
            corner_radius=20,
            fg_color="#A35BDD",
            hover_color="#8D48C8",
            border_width=2,
            border_color="#E9D7F5",
            font=ctk.CTkFont(
                "Segoe UI Emoji",
                20,
            ),
            command=self._open_chat_drawer,
        )

        self.history_reopen_button = ctk.CTkButton(
            self.shell,
            text="☰\nChats",
            width=54,
            height=118,
            corner_radius=20,
            fg_color="#A35BDD",
            hover_color="#8D48C8",
            border_width=2,
            border_color="#E9D7F5",
            text_color="#FFFFFF",
            font=ctk.CTkFont(
                "Segoe UI",
                11,
                "bold",
            ),
            command=self._open_history_drawer,
        )

    def _build_history_panel(self, parent):
        panel = ctk.CTkFrame(
            parent,
            width=235,
            corner_radius=28,
            fg_color="#F3EAF7",
            border_width=1,
            border_color="#E5D7EC",
        )
        panel.grid(
            row=0,
            column=0,
            padx=(18, 8),
            pady=18,
            sticky="nsew",
        )
        self.history_panel = panel
        panel.grid_propagate(False)
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        history_header = ctk.CTkFrame(
            panel,
            fg_color="transparent",
        )
        history_header.grid(
            row=0,
            column=0,
            padx=14,
            pady=(18, 10),
            sticky="ew",
        )
        history_header.grid_columnconfigure(1, weight=1)

        self.collapse_history_button = ctk.CTkButton(
            history_header,
            text="❮",
            width=34,
            height=30,
            corner_radius=14,
            fg_color="#EADCF4",
            hover_color="#DDC8EC",
            text_color="#75449B",
            font=ctk.CTkFont(
                "Segoe UI Symbol",
                14,
                "bold",
            ),
            command=self._close_history_drawer,
        )
        self.collapse_history_button.grid(
            row=0,
            column=0,
            padx=(0, 8),
        )

        ctk.CTkLabel(
            history_header,
            text="Chats",
            font=ctk.CTkFont("Segoe UI", 20, "bold"),
            text_color="#302638",
        ).grid(
            row=0,
            column=1,
            sticky="w",
        )

        ctk.CTkButton(
            panel,
            text="+ New Chat",
            height=42,
            corner_radius=16,
            fg_color="#9A55DB",
            hover_color="#8542C5",
            command=self._start_new_chat,
        ).grid(
            row=1,
            column=0,
            padx=14,
            pady=(0, 12),
            sticky="ew",
        )

        self.history_list = ctk.CTkScrollableFrame(
            panel,
            corner_radius=18,
            fg_color="#F8F3FA",
        )
        self.history_list.grid(
            row=2,
            column=0,
            padx=12,
            pady=(0, 12),
            sticky="nsew",
        )
        self.history_list.grid_columnconfigure(0, weight=1)

        self.delete_chat_button = ctk.CTkButton(
            panel,
            text="Delete Current Chat",
            height=38,
            corner_radius=15,
            fg_color="#F4DDE7",
            hover_color="#ECC9D8",
            text_color="#A34066",
            command=self._delete_current_chat,
        )
        self.delete_chat_button.grid(
            row=3,
            column=0,
            padx=14,
            pady=(0, 16),
            sticky="ew",
        )

        self._refresh_conversation_list()

    def _build_left_panel(self, parent):
        panel = ctk.CTkFrame(
            parent,
            width=285,
            corner_radius=28,
            fg_color="#FFFDFE",
            border_width=1,
            border_color="#ECE5F1",
        )
        panel.grid(row=0, column=1, padx=(10, 10), pady=18, sticky="nsew")
        self.left_panel = panel
        panel.grid_propagate(False)
        panel.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(panel, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(24, 10))

        avatar = ctk.CTkLabel(
            top,
            text="TS",
            width=42,
            height=42,
            corner_radius=21,
            fg_color="#EADAF6",
            text_color="#6F3AA8",
            font=ctk.CTkFont("Segoe UI", 14, "bold"),
        )
        avatar.pack(side="left")

        welcome = ctk.CTkLabel(
            top,
            text=f"Hi, {self.settings['user_name']}\nWelcome Back",
            justify="left",
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color="#292433",
        )
        welcome.pack(side="left", padx=10)

        ctk.CTkLabel(
            panel,
            text="Good Morning\nHow can I help you?",
            justify="left",
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 23, "bold"),
            text_color="#1F1A29",
        ).pack(anchor="w", padx=20, pady=(10, 20))

        action_grid = ctk.CTkFrame(panel, fg_color="transparent")
        action_grid.pack(fill="x", padx=18)

        for col in range(2):
            action_grid.grid_columnconfigure(col, weight=1)

        cards = [
            ("✨", "Talk to AI", "Ask me anything", lambda: self._use_suggestion("Explain artificial intelligence in simple words")),
            ("🎙", "Voice", "Voice assistant", self.handle_voice_command),
            ("✉", "Email", "Write an email", lambda: self._use_suggestion("Write a professional leave email")),
            ("🔎", "Search", "Search the web", lambda: self._use_suggestion("Search data science courses")),
            ("📄", "PDF", "Summarize a PDF", self._choose_and_summarize_pdf),
            ("⏰", "Reminder", "Set a reminder", lambda: self._use_suggestion("Remind me in 10 minutes to drink water")),
        ]

        for index, (icon, title, subtitle, action) in enumerate(cards):
            row, col = divmod(index, 2)

            card = ctk.CTkButton(
                action_grid,
                text=f"{icon}\n{title}\n{subtitle}",
                command=action,
                corner_radius=18,
                height=105,
                fg_color="#F7F1FA",
                hover_color="#EEDFF7",
                border_width=1,
                border_color="#EDE4F3",
                text_color="#312A3B",
                anchor="w",
                font=ctk.CTkFont("Segoe UI", 11, "bold"),
            )
            card.grid(
                row=row,
                column=col,
                padx=5,
                pady=5,
                sticky="nsew",
            )

        ctk.CTkLabel(
            panel,
            text="Topics",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            text_color="#292433",
        ).pack(anchor="w", padx=20, pady=(24, 10))

        chips = ctk.CTkFrame(panel, fg_color="transparent")
        chips.pack(fill="x", padx=18)

        topic_prompts = {
            "Daily life": "Give me three useful productivity tips for daily life",
            "Business": "Explain one useful business idea for a beginner",
            "Health": "Give me general healthy lifestyle tips",
            "Developer": "Suggest a beginner-friendly Python project",
        }

        for i, topic in enumerate(topic_prompts):
            chip = ctk.CTkButton(
                chips,
                text=topic,
                width=55,
                height=28,
                corner_radius=14,
                fg_color="#F0E5F8" if i == 0 else "#F7F3F9",
                hover_color="#E8D8F2",
                text_color="#6A4B80",
                font=ctk.CTkFont("Segoe UI", 9, "bold"),
                command=lambda selected=topic: self._use_suggestion(topic_prompts[selected]),
            )
            chip.pack(side="left", padx=3)

        prompt_card = ctk.CTkFrame(
            panel,
            corner_radius=18,
            fg_color="#FFFDFE",
            border_width=1,
            border_color="#ECE5F1",
        )
        prompt_card.pack(fill="x", padx=18, pady=16)

        ctk.CTkLabel(
            prompt_card,
            text="Quick idea",
            font=ctk.CTkFont("Segoe UI", 11, "bold"),
            text_color="#7A48A8",
        ).pack(anchor="w", padx=14, pady=(12, 4))

        ctk.CTkLabel(
            prompt_card,
            text='Try saying:\n"Write a short note on AI"',
            justify="left",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color="#4D4557",
        ).pack(anchor="w", padx=14, pady=(0, 13))

    def _build_voice_panel(self, parent):
        panel = ctk.CTkFrame(
            parent,
            corner_radius=28,
            fg_color="#FFFDFE",
            border_width=1,
            border_color="#ECE5F1",
        )
        panel.grid(row=0, column=2, padx=10, pady=18, sticky="nsew")
        self.voice_panel = panel
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(22, 0))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Voice Assistant",
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
            text_color="#251F2D",
        ).grid(row=0, column=0)

        self.voice_status = ctk.CTkLabel(
            panel,
            text="Ready",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color="#9C8AA8",
        )
        self.voice_status.grid(row=1, column=0, pady=(8, 4))

        orb_wrap = ctk.CTkFrame(panel, fg_color="transparent")
        orb_wrap.grid(row=2, column=0)

        self.orb_canvas = tk.Canvas(
            orb_wrap,
            width=300,
            height=300,
            bg="#FFFDFE",
            highlightthickness=0,
        )
        self.orb_canvas.pack()

        self.voice_question = ctk.CTkLabel(
            panel,
            text="Tap the microphone\nand start speaking",
            justify="center",
            font=ctk.CTkFont("Segoe UI", 20, "bold"),
            text_color="#352C3D",
        )
        self.voice_question.grid(row=3, column=0, pady=(0, 10))

        self.voice_hint = ctk.CTkLabel(
            panel,
            text="I can open apps, search the web,\nand answer your questions.",
            justify="center",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color="#9A8EA2",
        )
        self.voice_hint.grid(row=4, column=0, pady=(0, 20))

        controls = ctk.CTkFrame(panel, fg_color="transparent")
        controls.grid(row=5, column=0, pady=(0, 24))

        self.main_mic_button = ctk.CTkButton(
            controls,
            text="🎤",
            width=62,
            height=62,
            corner_radius=31,
            fg_color="#9A55DB",
            hover_color="#8542C5",
            font=ctk.CTkFont("Segoe UI Emoji", 22),
            command=self.handle_voice_command,
        )
        self.main_mic_button.pack()

    def _build_chat_panel(self, parent):
        panel = ctk.CTkFrame(
            parent,
            corner_radius=28,
            fg_color="#FFFDFE",
            border_width=1,
            border_color="#ECE5F1",
        )
        panel.grid(row=0, column=3, padx=(10, 18), pady=18, sticky="nsew")
        self.chat_panel = panel
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)

        chat_header = ctk.CTkFrame(panel, fg_color="transparent")
        chat_header.grid(
            row=0,
            column=0,
            padx=18,
            pady=(18, 10),
            sticky="ew",
        )
        chat_header.grid_columnconfigure(1, weight=1)

        self.collapse_chat_button = ctk.CTkButton(
            chat_header,
            text="❯",
            width=34,
            height=30,
            corner_radius=14,
            fg_color="#F2E8F8",
            hover_color="#E6D6F0",
            text_color="#75449B",
            font=ctk.CTkFont("Segoe UI Symbol", 14, "bold"),
            command=self._close_chat_drawer,
        )
        self.collapse_chat_button.grid(
            row=0,
            column=0,
            padx=(0, 8),
        )

        ctk.CTkLabel(
            chat_header,
            text="Smart Chat",
            font=ctk.CTkFont("Segoe UI", 16, "bold"),
            text_color="#251F2D",
        ).grid(row=0, column=1, sticky="w")

        self.settings_button = ctk.CTkButton(
            chat_header,
            text="⚙",
            width=38,
            height=30,
            corner_radius=14,
            fg_color="#F2E8F8",
            hover_color="#E6D6F0",
            text_color="#75449B",
            command=self._open_settings,
        )
        self.settings_button.grid(row=0, column=2, padx=4)

        self.copy_button = ctk.CTkButton(
            chat_header,
            text="Copy",
            width=65,
            height=30,
            corner_radius=14,
            fg_color="#EFE3F7",
            hover_color="#E3D1EF",
            text_color="#75449B",
            command=self._copy_last_response,
        )
        self.copy_button.grid(row=0, column=3, padx=4)

        self.clear_button = ctk.CTkButton(
            chat_header,
            text="Clear",
            width=65,
            height=30,
            corner_radius=14,
            fg_color="#F7E7ED",
            hover_color="#F0D8E2",
            text_color="#A34868",
            command=self._clear_chat,
        )
        self.clear_button.grid(row=0, column=4, padx=4)

        self.chat_frame = ctk.CTkScrollableFrame(
            panel,
            corner_radius=20,
            fg_color="#F8F4FA",
        )
        self.chat_frame.grid(
            row=1,
            column=0,
            padx=16,
            pady=(0, 12),
            sticky="nsew",
        )
        self.chat_frame.grid_columnconfigure(0, weight=1)

        composer = ctk.CTkFrame(
            panel,
            corner_radius=18,
            fg_color="#F7F1FA",
        )
        composer.grid(row=2, column=0, padx=16, pady=(0, 18), sticky="ew")
        composer.grid_columnconfigure(0, weight=1)

        self.input_box = ctk.CTkEntry(
            composer,
            height=46,
            corner_radius=16,
            placeholder_text="Type a message",
            font=ctk.CTkFont("Segoe UI", 12),
            fg_color="#FFFFFF",
            border_color="#E6DCEC",
            text_color="#302838",
        )
        self.input_box.grid(row=0, column=0, padx=(10, 8), pady=10, sticky="ew")
        self.input_box.bind("<Return>", lambda event: self.handle_text_command())

        self.send_button = ctk.CTkButton(
            composer,
            text="➤",
            width=46,
            height=46,
            corner_radius=23,
            fg_color="#9A55DB",
            hover_color="#8542C5",
            font=ctk.CTkFont("Segoe UI", 17, "bold"),
            command=self.handle_text_command,
        )
        self.send_button.grid(row=0, column=1, padx=(0, 8), pady=10)

        self.small_mic_button = ctk.CTkButton(
            composer,
            text="🎤",
            width=46,
            height=46,
            corner_radius=23,
            fg_color="#B775E6",
            hover_color="#9D5CD1",
            font=ctk.CTkFont("Segoe UI Emoji", 16),
            command=self.handle_voice_command,
        )
        self.small_mic_button.grid(row=0, column=2, padx=(0, 10), pady=10)

    # --------------------------------------------------
    # COLLAPSIBLE CHAT HISTORY DRAWER
    # --------------------------------------------------

    def _close_history_drawer(self):
        if not self.history_drawer_open:
            return

        self.history_drawer_open = False
        self.history_panel.grid_remove()

        # Expand the main content into the freed left-side space.
        self.shell.grid_columnconfigure(0, weight=0)
        self.shell.grid_columnconfigure(1, weight=1)
        self.shell.grid_columnconfigure(2, weight=2)

        self.history_reopen_button.grid(
            row=0,
            column=0,
            padx=(14, 4),
            pady=28,
            sticky="w",
        )

        self.after(20, self.update_idletasks)

    def _open_history_drawer(self):
        if self.history_drawer_open:
            return

        self.history_drawer_open = True
        self.history_reopen_button.grid_remove()

        self.shell.grid_columnconfigure(0, weight=0)

        # Left and voice panel sizing depends on whether Smart Chat is open.
        if self.chat_drawer_open:
            self.shell.grid_columnconfigure(1, weight=0)
            self.shell.grid_columnconfigure(2, weight=1)
        else:
            self.shell.grid_columnconfigure(1, weight=1)
            self.shell.grid_columnconfigure(2, weight=2)

        self.history_panel.grid(
            row=0,
            column=0,
            padx=(18, 8),
            pady=18,
            sticky="nsew",
        )
        self.history_panel.lift()

        self.after(20, self.update_idletasks)

    def _toggle_history_drawer(self):
        if self.history_drawer_open:
            self._close_history_drawer()
        else:
            self._open_history_drawer()

    # --------------------------------------------------
    # COLLAPSIBLE SMART CHAT DRAWER
    # --------------------------------------------------

    def _close_chat_drawer(self):
        if not self.chat_drawer_open:
            return

        self.chat_drawer_open = False
        self.chat_panel.grid_remove()

        # Allow the remaining main sections to use the freed space.
        self.shell.grid_columnconfigure(
            1,
            weight=1,
        )
        self.shell.grid_columnconfigure(
            2,
            weight=2,
        )
        self.shell.grid_columnconfigure(3, weight=0)

        if not self.history_drawer_open:
            self.shell.grid_columnconfigure(0, weight=0)

        self.chat_reopen_button.grid(
            row=0,
            column=3,
            padx=(4, 14),
            pady=28,
            sticky="e",
        )

        self.after(20, self.update_idletasks)

    def _open_chat_drawer(self):
        if self.chat_drawer_open:
            return

        self.chat_drawer_open = True
        self.chat_reopen_button.grid_remove()

        # Restore the original four-section layout.
        self.shell.grid_columnconfigure(1, weight=0)
        self.shell.grid_columnconfigure(2, weight=1)
        self.shell.grid_columnconfigure(3, weight=1)

        self.chat_panel.grid(
            row=0,
            column=3,
            padx=(10, 18),
            pady=18,
            sticky="nsew",
        )

        self.chat_panel.lift()
        self.after(20, self.update_idletasks)

        if hasattr(self, "input_box"):
            self.input_box.focus()

    def _toggle_chat_drawer(self):
        if self.chat_drawer_open:
            self._close_chat_drawer()
        else:
            self._open_chat_drawer()

    # --------------------------------------------------
    # QUICK ACTIONS AND CHAT UTILITIES
    # --------------------------------------------------

    def _use_suggestion(self, prompt: str):
        if self.is_processing:
            return

        self.input_box.delete(0, "end")
        self.input_box.insert(0, prompt)
        self.handle_text_command()

    def _copy_last_response(self):
        if not self.last_assistant_response:
            self._set_state("error")
            self.voice_question.configure(text="There is no response to copy yet")
            self.after(1200, lambda: self._set_state("ready"))
            return

        copy_to_clipboard(self.last_assistant_response)
        self._set_state("speaking")
        self.voice_question.configure(text="Response copied to clipboard")

        threading.Thread(
            target=self._speak_if_enabled,
            args=("I copied the latest response to your clipboard.",),
            daemon=True,
        ).start()

        self.after(1400, lambda: self._set_state("ready"))

    def _clear_chat(self):
        if self.is_processing:
            return

        for child in self.chat_frame.winfo_children():
            child.destroy()

        self.chat_messages.clear()
        self.last_assistant_response = ""

        self._add_message(
            "Shona",
            "This conversation has been cleared. "
            "How can I help you now?",
        )

        self._save_current_conversation()

        threading.Thread(
            target=self._speak_if_enabled,
            args=("This conversation has been cleared.",),
            daemon=True,
        ).start()

    def _restore_previous_chat(self):
        conversations = list_conversations()

        if (
            self.settings.get("restore_history", True)
            and conversations
        ):
            self._load_conversation(conversations[0]["id"])
            return

        self._start_new_chat(initial=True)

    def _refresh_conversation_list(self):
        if not hasattr(self, "history_list"):
            return

        for child in self.history_list.winfo_children():
            child.destroy()

        self.conversation_buttons.clear()

        for row_index, conversation in enumerate(
            list_conversations()
        ):
            conversation_id = conversation["id"]
            title = conversation.get("title", "New Chat")

            active = (
                conversation_id
                == self.current_conversation_id
            )

            button = ctk.CTkButton(
                self.history_list,
                text=title,
                height=42,
                corner_radius=14,
                anchor="w",
                fg_color="#DCC5EB" if active else "#FFFFFF",
                hover_color="#E8D8F1",
                text_color="#493558",
                command=lambda selected_id=conversation_id: (
                    self._load_conversation(selected_id)
                ),
            )
            button.grid(
                row=row_index,
                column=0,
                padx=5,
                pady=4,
                sticky="ew",
            )

            self.conversation_buttons.append(button)

    def _start_new_chat(self, initial=False):
        if self.is_processing:
            return

        conversation = create_conversation()
        self.current_conversation_id = conversation["id"]

        for child in self.chat_frame.winfo_children():
            child.destroy()

        self.chat_messages = []
        self.last_assistant_response = ""

        welcome = (
            f"Hi {self.settings['user_name']} ✨\n"
            "This is a new conversation. How can I help you?"
        )

        self._add_message("Shona", welcome)
        self._save_current_conversation()
        self._refresh_conversation_list()

        if not initial:
            self.input_box.focus()

    def _load_conversation(self, conversation_id: str):
        if self.is_processing:
            return

        conversation = get_conversation(conversation_id)

        if conversation is None:
            return

        self.current_conversation_id = conversation_id

        for child in self.chat_frame.winfo_children():
            child.destroy()

        self.chat_messages = []
        self.last_assistant_response = ""
        self.is_restoring_history = True

        messages = conversation.get("messages", [])

        for item in messages:
            self._add_message(
                item.get("sender", "Shona"),
                item.get("message", ""),
            )

        self.is_restoring_history = False
        self.chat_messages = messages.copy()

        if not messages:
            self._add_message(
                "Shona",
                f"Hi {self.settings['user_name']} ✨\n"
                "How can I assist you today?",
            )

        for item in reversed(self.chat_messages):
            if item.get("sender") == "Shona":
                self.last_assistant_response = item.get(
                    "message",
                    "",
                )
                break

        self._refresh_conversation_list()

    def _save_current_conversation(self):
        if not self.current_conversation_id:
            return

        title = generate_title(self.chat_messages)

        save_conversation(
            self.current_conversation_id,
            self.chat_messages,
            title=title,
        )

        self._refresh_conversation_list()

    def _delete_current_chat(self):
        if (
            self.is_processing
            or not self.current_conversation_id
        ):
            return

        delete_conversation(self.current_conversation_id)

        conversations = list_conversations()

        if conversations:
            self._load_conversation(
                conversations[0]["id"]
            )
        else:
            self._start_new_chat(initial=True)
    def _hotkey_toggle(self):
        """
        Called by the global keyboard listener.
        Transfer the actual UI work to Tkinter's main thread.
        """
        self.after(
            0,
            self._toggle_window_visibility,
        )


    def _toggle_window_visibility(self):
        if self.state() == "withdrawn" or not self.winfo_viewable():
            self._show_main_window()
        else:
            self._hide_to_floating_orb()


    def _show_main_window(self):
        self.deiconify()
        self.state("normal")
        self.lift()
        self.focus_force()

        if hasattr(self, "floating_orb"):
            self.floating_orb.hide()

        if hasattr(self, "input_box"):
            self.input_box.focus()


    def _hide_to_floating_orb(self):
        self.withdraw()

        if hasattr(self, "floating_orb"):
            self.floating_orb.show()


    def _exit_shona(self):
        unregister_global_hotkey()

        if hasattr(self, "floating_orb"):
            try:
                self.floating_orb.destroy()
            except Exception:
                pass

        self.destroy()

    # --------------------------------------------------
    # SETTINGS
    # --------------------------------------------------

    def _open_settings(self):
        if self.is_processing:
            return

        window = ctk.CTkToplevel(self)
        window.title("Shona Settings")
        window.geometry("470x520")
        window.resizable(False, False)
        window.transient(self)
        window.grab_set()
        window.configure(fg_color="#F4EEF8")

        card = ctk.CTkFrame(
            window,
            corner_radius=26,
            fg_color="#FFFDFE",
            border_width=1,
            border_color="#E6DAEC",
        )
        card.pack(
            padx=20,
            pady=20,
            fill="both",
            expand=True,
        )

        ctk.CTkLabel(
            card,
            text="Assistant Settings",
            font=ctk.CTkFont("Segoe UI", 22, "bold"),
            text_color="#33273C",
        ).pack(pady=(24, 6))

        ctk.CTkLabel(
            card,
            text="Personalize how Shona responds to you.",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color="#8C7D95",
        ).pack(pady=(0, 22))

        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=28)

        ctk.CTkLabel(
            form,
            text="Your name",
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color="#493A52",
        ).pack(fill="x", pady=(0, 6))

        name_entry = ctk.CTkEntry(
            form,
            height=42,
            corner_radius=14,
            fg_color="#F8F3FA",
            border_color="#E2D5E9",
        )
        name_entry.pack(fill="x", pady=(0, 18))
        name_entry.insert(0, self.settings.get("user_name", "Tanisha"))

        ctk.CTkLabel(
            form,
            text="Response length",
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
            text_color="#493A52",
        ).pack(fill="x", pady=(0, 6))

        style_menu = ctk.CTkOptionMenu(
            form,
            values=["Short", "Balanced", "Detailed"],
            height=42,
            corner_radius=14,
            fg_color="#A15BDD",
            button_color="#8E49CA",
            button_hover_color="#7E3DB7",
        )
        style_menu.pack(fill="x", pady=(0, 18))
        style_menu.set(
            self.settings.get("response_style", "Balanced")
        )

        voice_switch = ctk.CTkSwitch(
            form,
            text="Speak assistant confirmations",
            font=ctk.CTkFont("Segoe UI", 12),
            progress_color="#9A55DB",
        )
        voice_switch.pack(anchor="w", pady=(4, 14))

        if self.settings.get("voice_enabled", True):
            voice_switch.select()

        history_switch = ctk.CTkSwitch(
            form,
            text="Restore previous chat when the app opens",
            font=ctk.CTkFont("Segoe UI", 12),
            progress_color="#9A55DB",
        )
        history_switch.pack(anchor="w", pady=(0, 24))

        if self.settings.get("restore_history", True):
            history_switch.select()

        def save_and_close():
            user_name = name_entry.get().strip() or "User"

            self.settings = {
                "user_name": user_name,
                "response_style": style_menu.get(),
                "voice_enabled": bool(voice_switch.get()),
                "restore_history": bool(history_switch.get()),
            }

            save_settings(self.settings)
            window.destroy()

            self._add_message(
                "Shona",
                f"Settings saved. I will call you {user_name}.",
            )

            if self.settings["voice_enabled"]:
                threading.Thread(
                    target=self._speak_if_enabled,
                    args=("Your settings have been saved.",),
                    daemon=True,
                ).start()

        ctk.CTkButton(
            card,
            text="Save Settings",
            height=44,
            corner_radius=18,
            fg_color="#9A55DB",
            hover_color="#8542C5",
            command=save_and_close,
        ).pack(fill="x", padx=28, pady=(8, 22))

    def _speak_if_enabled(self, text: str):
        if not self.settings.get("voice_enabled", True):
            return

        speak(text)

    def _response_style_instruction(self) -> str:
        style = self.settings.get("response_style", "Balanced")

        instructions = {
            "Short": (
                "Keep the answer very concise, usually under 5 lines, "
                "unless the user explicitly asks for detail."
            ),
            "Balanced": (
                "Give a clear, moderately detailed answer without "
                "unnecessary repetition."
            ),
            "Detailed": (
                "Give a thorough, well-structured answer with useful "
                "explanation and examples when appropriate."
            ),
        }

        return instructions.get(style, instructions["Balanced"])


    # --------------------------------------------------
    # PDF SUMMARIZATION
    # --------------------------------------------------

    def _choose_and_summarize_pdf(self):
        if self.is_processing:
            return

        if PdfReader is None:
            self._add_message(
                "Shona",
                "PDF support is not installed. Run: pip install pypdf",
            )

            threading.Thread(
                target=self._speak_if_enabled,
                args=("Please install the PDF package first.",),
                daemon=True,
            ).start()
            return

        file_path = filedialog.askopenfilename(
            title="Choose a PDF to summarize",
            filetypes=[("PDF files", "*.pdf")],
        )

        if not file_path:
            return

        selected_file = Path(file_path)

        self._add_message(
            "You",
            f"Summarize PDF: {selected_file.name}",
        )
        self._save_current_conversation()

        self._set_controls_enabled(False)
        self._set_state("thinking")
        self._start_orb()
        self._show_typing()

        threading.Thread(
            target=self._summarize_pdf_background,
            args=(selected_file,),
            daemon=True,
        ).start()

    def _summarize_pdf_background(self, file_path: Path):
        try:
            reader = PdfReader(str(file_path))
            extracted_pages = []

            for page_number, page in enumerate(
                reader.pages,
                start=1,
            ):
                page_text = page.extract_text() or ""

                if page_text.strip():
                    extracted_pages.append(
                        f"Page {page_number}:\n"
                        f"{page_text.strip()}"
                    )

            if not extracted_pages:
                raise ValueError(
                    "No readable text was found. "
                    "This may be a scanned-image PDF."
                )

            full_text = "\n\n".join(extracted_pages)

            maximum_characters = 50000
            was_shortened = (
                len(full_text) > maximum_characters
            )
            text_for_ai = full_text[:maximum_characters]

            prompt = f"""
You are Shona, helping a student summarize a PDF.

Create:
1. A short overview.
2. Main points in clear bullets.
3. Important facts, terms, or definitions.
4. A short conclusion.

Use simple, readable language.
Do not invent anything that is not present in the document.

PDF filename: {file_path.name}

PDF content:
{text_for_ai}
"""

            summary = ask_ai(prompt)

            if was_shortened:
                summary += (
                    "\n\nNote: This PDF was very long, "
                    "so the summary used the first part "
                    "of the extracted text."
                )

            self.after(
                0,
                lambda: self._show_response(
                    summary,
                    f"Here is the summary of {file_path.name}.",
                ),
            )

        except Exception as error:
            print("PDF summarization error:", error)

            self.after(
                0,
                lambda: self._show_pdf_error(
                    "I could not summarize this PDF.\n\n"
                    f"Reason: {error}"
                ),
            )

    def _show_pdf_error(self, message: str):
        self._hide_typing()
        self._stop_orb()

        self._add_message(
            "Shona",
            message,
        )
        self._save_current_conversation()
        self._set_state("error")

        threading.Thread(
            target=self._speak_if_enabled,
            args=("I could not summarize that PDF.",),
            daemon=True,
        ).start()

        self.after(
            1800,
            self._reset_ui,
        )

    # --------------------------------------------------
    # ORB
    # --------------------------------------------------

    def _draw_orb(self):
        self.orb_canvas.delete("all")

        cx, cy = 150, 150
        rings = [
            (118, "#E8DDF7"),
            (104, "#E1CFF2"),
            (88, "#D8BBF2"),
            (70, "#C899EE"),
            (52, "#A970DC"),
        ]

        for radius, color in rings:
            self.orb_canvas.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                fill=color,
                outline="",
            )

        for i in range(7):
            angle = math.radians(i * 51 + self.orb_step * 4)
            x1 = cx + math.cos(angle) * 26
            y1 = cy + math.sin(angle) * 26
            x2 = cx + math.cos(angle + 1.2) * 86
            y2 = cy + math.sin(angle + 1.2) * 86

            color = ["#B76FE5", "#8BA8F7", "#F09ACB"][i % 3]
            self.orb_canvas.create_line(
                x1,
                y1,
                x2,
                y2,
                width=8,
                fill=color,
                smooth=True,
                capstyle=tk.ROUND,
            )

        self.orb_canvas.create_oval(
            105,
            105,
            195,
            195,
            fill="#F7EAFE",
            outline="",
        )

        self.orb_canvas.create_text(
            150,
            150,
            text="✦",
            fill="#9B58D0",
            font=("Segoe UI Symbol", 30, "bold"),
        )

    def _start_orb(self):
        self.orb_running = True
        self._animate_orb()

    def _stop_orb(self):
        self.orb_running = False
        self._draw_orb()

    def _animate_orb(self):
        if not self.orb_running:
            return

        self.orb_step += 1
        self._draw_orb()
        self.after(90, self._animate_orb)

    # --------------------------------------------------
    # CHAT
    # --------------------------------------------------

    def _add_message(self, sender: str, message: str):
        is_user = sender == "You"
        self.chat_messages.append({"sender": sender, "message": message})

        if sender == "Shona":
            self.last_assistant_response = message

        if not self.is_restoring_history:
            self._save_current_conversation()

        row_index = len(self.chat_frame.winfo_children())

        row = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        row.grid(row=row_index, column=0, padx=8, pady=6, sticky="ew")
        row.grid_columnconfigure(0, weight=1)
        row.grid_columnconfigure(1, weight=1)

        bubble = ctk.CTkFrame(
            row,
            corner_radius=16,
            fg_color="#1E1B2A" if is_user else "#FFFFFF",
            border_width=0 if is_user else 1,
            border_color="#E8DFEE",
        )

        if is_user:
            bubble.grid(row=0, column=1, padx=(25, 0), sticky="e")
        else:
            bubble.grid(row=0, column=0, padx=(0, 25), sticky="w")

        ctk.CTkLabel(
            bubble,
            text=sender,
            font=ctk.CTkFont("Segoe UI", 9, "bold"),
            text_color="#D8C9E5" if is_user else "#9A55DB",
            anchor="w",
        ).pack(anchor="w", padx=13, pady=(9, 2))

        ctk.CTkLabel(
            bubble,
            text=message,
            justify="left",
            anchor="w",
            wraplength=250,
            font=ctk.CTkFont("Segoe UI", 11),
            text_color="#FFFFFF" if is_user else "#3B3342",
        ).pack(anchor="w", padx=13, pady=(0, 11))

        self.after(
            100,
            lambda: self.chat_frame._parent_canvas.yview_moveto(1.0),
        )

    def _show_typing(self):
        if self.typing_row is not None:
            return

        self.typing_running = True
        self.typing_step = 0

        row_index = len(self.chat_frame.winfo_children())
        self.typing_row = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        self.typing_row.grid(row=row_index, column=0, padx=8, pady=6, sticky="ew")

        bubble = ctk.CTkFrame(
            self.typing_row,
            corner_radius=16,
            fg_color="#FFFFFF",
            border_width=1,
            border_color="#E8DFEE",
        )
        bubble.pack(anchor="w")

        self.typing_label = ctk.CTkLabel(
            bubble,
            text="Shona is thinking",
            font=ctk.CTkFont("Segoe UI", 11),
            text_color="#9A55DB",
        )
        self.typing_label.pack(padx=14, pady=11)

        self._animate_typing()

    def _animate_typing(self):
        if not self.typing_running or self.typing_label is None:
            return

        dots = ["", ".", "..", "..."]
        self.typing_label.configure(
            text="Shona is thinking" + dots[self.typing_step % len(dots)]
        )
        self.typing_step += 1
        self.after(350, self._animate_typing)

    def _hide_typing(self):
        self.typing_running = False

        if self.typing_row is not None:
            self.typing_row.destroy()

        self.typing_row = None
        self.typing_label = None

    # --------------------------------------------------
    # STATE
    # --------------------------------------------------

    def _set_state(self, state: str):
        states = {
            "ready": ("Ready", "Tap the microphone\nand start speaking", "#9C8AA8"),
            "preparing": ("Adjusting microphone...", "Preparing your microphone", "#C29345"),
            "listening": ("Listening...", "I am listening\nSpeak now", "#9A55DB"),
            "thinking": ("Thinking...", "Processing your request", "#8A6FCC"),
            "speaking": ("Speaking...", "Here is your response", "#8D55BD"),
            "error": ("Try again", "I could not hear you properly", "#C85D75"),
        }

        status, question, color = states[state]
        self.voice_status.configure(text=status, text_color=color)
        self.voice_question.configure(text=question)
        if hasattr(self, "floating_orb"):
            self.floating_orb.set_state(state)

    def _set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.send_button.configure(state=state)
        self.small_mic_button.configure(state=state)
        self.main_mic_button.configure(state=state)
        self.input_box.configure(state=state)
        self.copy_button.configure(state=state)
        self.clear_button.configure(state=state)
        self.settings_button.configure(state=state)
        self.is_processing = not enabled

    # --------------------------------------------------
    # TEXT COMMAND
    # --------------------------------------------------

    def handle_text_command(self):
        if self.is_processing:
            return

        command = self.input_box.get().strip()
        if not command:
            return

        self.input_box.delete(0, "end")
        self._add_message("You", command)
        self._save_current_conversation()
        self._set_controls_enabled(False)
        self._set_state("thinking")
        self._start_orb()
        self._show_typing()

        threading.Thread(
            target=self._process_command_background,
            args=(command,),
            daemon=True,
        ).start()

    # --------------------------------------------------
    # VOICE COMMAND
    # --------------------------------------------------

    def handle_voice_command(self):
        if self.is_processing:
            return

        self._set_controls_enabled(False)
        self.main_mic_button.configure(state="normal")
        self._set_state("preparing")

        threading.Thread(
            target=self._listen_background,
            daemon=True,
        ).start()

    def _listen_background(self):
        def microphone_ready():
            self.after(0, self._begin_listening_state)

        command = listen(on_ready=microphone_ready)
        self.after(0, lambda: self._finish_listening(command))

    def _begin_listening_state(self):
        self._set_state("listening")
        self._start_orb()

    def _finish_listening(self, command: str):
        self._stop_orb()

        if not command:
            message = "I did not hear you properly. Please try again."
            self._add_message("Shona", message)
            self._set_state("error")

            threading.Thread(
                target=self._speak_if_enabled,
                args=(message,),
                daemon=True,
            ).start()

            self.after(1500, self._reset_ui)
            return

        self._add_message("You", command)
        self._set_state("thinking")
        self._start_orb()
        self._show_typing()

        threading.Thread(
            target=self._process_command_background,
            args=(command,),
            daemon=True,
        ).start()

    # --------------------------------------------------
    # PROCESSING
    # --------------------------------------------------

    def _process_command_background(self, command: str):
        try:
            lowered = command.lower().strip()

            # This command depends on UI state, so keep it here.
            if (
                "copy the suggested fix" in lowered
                or "copy the last solution" in lowered
                or "copy the last response" in lowered
            ):
                if self.last_assistant_response:
                    copy_to_clipboard(
                        self.last_assistant_response
                    )
                    response = (
                        "I copied the latest response "
                        "to your clipboard."
                    )
                else:
                    response = (
                        "There is no previous response to copy."
                    )

                self.after(
                    0,
                    lambda: self._show_response(
                        response,
                        response,
                    ),
                )
                return

            context = build_conversation_context(
                self.chat_messages,
                limit=10,
            )

            result = self.action_manager.execute(
                command=command,
                conversation_context=context,
                response_style_instruction=(
                    self._response_style_instruction()
                ),
            )

            self.after(
                0,
                lambda: self._show_response(
                    result.response,
                    result.voice_line,
                ),
            )

        except Exception as error:
            print("Action Manager error:", error)
            self.after(0, self._show_error)

    def _reminder_due_from_thread(self, message: str):
        self.after(
            0,
            lambda: self._show_reminder_popup(message),
        )
        
    def _agent_progress_from_thread(self, message: str):
        self.after(
            0,
            lambda: self._show_agent_progress(message),
        )


    def _show_agent_progress(self, message: str):
        self._add_message(
            "Shona",
            f"⚙ {message}",
        )

        self._set_state("thinking")

    def _show_reminder_popup(self, message: str):
        self._add_message(
            "Shona",
            f"⏰ Reminder: {message}",
        )

        popup = ctk.CTkToplevel(self)
        popup.title("Shona Reminder")
        popup.geometry("430x240")
        popup.resizable(False, False)
        popup.transient(self)
        popup.grab_set()
        popup.configure(fg_color="#F4EEF8")

        card = ctk.CTkFrame(
            popup,
            corner_radius=24,
            fg_color="#FFFDFE",
            border_width=1,
            border_color="#E5D9EC",
        )
        card.pack(
            padx=18,
            pady=18,
            fill="both",
            expand=True,
        )

        ctk.CTkLabel(
            card,
            text="⏰",
            font=ctk.CTkFont("Segoe UI Emoji", 34),
        ).pack(pady=(20, 8))

        ctk.CTkLabel(
            card,
            text="Reminder",
            font=ctk.CTkFont("Segoe UI", 18, "bold"),
            text_color="#3B2947",
        ).pack()

        ctk.CTkLabel(
            card,
            text=message,
            wraplength=350,
            justify="center",
            font=ctk.CTkFont("Segoe UI", 13),
            text_color="#5A4C63",
        ).pack(padx=20, pady=12)

        ctk.CTkButton(
            card,
            text="Done",
            width=110,
            height=38,
            corner_radius=18,
            fg_color="#9A55DB",
            hover_color="#8542C5",
            command=popup.destroy,
        ).pack(pady=(2, 18))

        threading.Thread(
            target=self._speak_if_enabled,
            args=(f"Reminder. {message}",),
            daemon=True,
        ).start()

    def _show_response(self, response: str, voice_line: str):
        self._hide_typing()
        self._stop_orb()
        self._add_message("Shona", response)
        self._save_current_conversation()
        self._set_state("speaking")

        threading.Thread(
            target=self._speak_and_reset,
            args=(voice_line,),
            daemon=True,
        ).start()

    def _speak_and_reset(self, voice_line: str):
        self._speak_if_enabled(voice_line)
        self.after(0, self._reset_ui)

    def _show_error(self):
        self._hide_typing()
        self._stop_orb()

        message = "Something went wrong while processing your request."
        self._add_message("Shona", message)
        self._set_state("error")

        threading.Thread(
            target=self._speak_if_enabled,
            args=("Something went wrong. Please try again.",),
            daemon=True,
        ).start()

        self.after(1500, self._reset_ui)

    def _reset_ui(self):
        self._hide_typing()
        self._stop_orb()
        self._set_controls_enabled(True)
        self._set_state("ready")
        self.input_box.focus()


if __name__ == "__main__":
    app = ShonaApp()
    app.mainloop()