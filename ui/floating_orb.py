import math
import tkinter as tk

import customtkinter as ctk


class FloatingShonaOrb(ctk.CTkToplevel):
    """
    Transparent, draggable lavender floating disc.

    Left-click toggles Shona.
    Right-click exits Shona.
    """

    TRANSPARENT_COLOR = "#010101"

    def __init__(
        self,
        parent,
        toggle_callback,
        exit_callback=None,
    ):
        super().__init__(parent)

        self.toggle_callback = toggle_callback
        self.exit_callback = exit_callback

        self.drag_start_x = 0
        self.drag_start_y = 0
        self.was_dragged = False
        self.current_state = "ready"
        self.hovered = False
        self.animation_step = 0
        self.animation_running = False

        self.title("Shona")
        self.geometry("112x112+1180+620")
        self.resizable(False, False)
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # On Windows this removes the square window background,
        # leaving only the circular disc visible.
        self.configure(fg_color=self.TRANSPARENT_COLOR)

        try:
            self.wm_attributes(
                "-transparentcolor",
                self.TRANSPARENT_COLOR,
            )
        except tk.TclError:
            pass

        self.canvas = tk.Canvas(
            self,
            width=112,
            height=112,
            bg=self.TRANSPARENT_COLOR,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<Enter>", self._on_enter)
        self.canvas.bind("<Leave>", self._on_leave)
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag_window)
        self.canvas.bind("<ButtonRelease-1>", self._finish_drag)
        self.canvas.bind("<Button-3>", self._handle_right_click)

        self._draw_disc()
        self.withdraw()

    def _state_palette(self):
        palettes = {
            "ready": (
                "#F2E7FF",
                "#DCC4F4",
                "#BE8BE7",
                "#9146D4",
            ),
            "preparing": (
                "#FFF5DE",
                "#F1DCA8",
                "#D5A84B",
                "#A97B22",
            ),
            "listening": (
                "#EEE6FF",
                "#CEB6F4",
                "#A66BE0",
                "#7F38C4",
            ),
            "thinking": (
                "#EEE9FF",
                "#D2C6F5",
                "#9E86D9",
                "#7259B8",
            ),
            "speaking": (
                "#F5E6FF",
                "#DEBDF4",
                "#BB78E4",
                "#8E43C9",
            ),
            "error": (
                "#FFE9EF",
                "#F3C4D1",
                "#D87A94",
                "#B44665",
            ),
        }

        return palettes.get(
            self.current_state,
            palettes["ready"],
        )

    def _draw_disc(self):
        self.canvas.delete("all")

        light, mid, accent, deep = self._state_palette()
        cx = cy = 56

        # Soft circular shadow.
        self.canvas.create_oval(
            9,
            11,
            105,
            107,
            fill="#D7CBE1",
            outline="",
        )

        # Lavender halo rings.
        self.canvas.create_oval(
            4,
            4,
            108,
            108,
            fill=light,
            outline="#E8D7F7",
            width=2,
        )
        self.canvas.create_oval(
            12,
            12,
            100,
            100,
            fill=mid,
            outline="#E1CAF5",
            width=2,
        )
        self.canvas.create_oval(
            21,
            21,
            91,
            91,
            fill=accent,
            outline="#C99AEB",
            width=2,
        )
        self.canvas.create_oval(
            31,
            31,
            81,
            81,
            fill=deep,
            outline="#AA69DD",
            width=2,
        )

        # Subtle orbit details make it feel like a disc rather than a button.
        orbit_radius = 37
        for index in range(4):
            angle = math.radians(
                index * 90 + self.animation_step
            )
            x = cx + math.cos(angle) * orbit_radius
            y = cy + math.sin(angle) * orbit_radius

            self.canvas.create_oval(
                x - 2.4,
                y - 2.4,
                x + 2.4,
                y + 2.4,
                fill="#FFFFFF",
                outline="",
            )

        center_fill = "#FFFFFF" if not self.hovered else "#FBF5FF"

        self.canvas.create_oval(
            38,
            38,
            74,
            74,
            fill=center_fill,
            outline="#ECDCF8",
            width=2,
        )

        state_symbols = {
            "ready": "✦",
            "preparing": "⋯",
            "listening": "●",
            "thinking": "✧",
            "speaking": "◉",
            "error": "!",
        }

        self.canvas.create_text(
            56,
            55,
            text=state_symbols.get(
                self.current_state,
                "✦",
            ),
            fill=deep,
            font=(
                "Segoe UI Symbol",
                22 if self.current_state != "error" else 20,
                "bold",
            ),
        )

        # A faint glossy highlight.
        self.canvas.create_arc(
            17,
            15,
            95,
            93,
            start=42,
            extent=82,
            style="arc",
            outline="#FFFFFF",
            width=3,
        )

    def _on_enter(self, _event):
        self.hovered = True
        self._draw_disc()

    def _on_leave(self, _event):
        self.hovered = False
        self._draw_disc()

    def _start_drag(self, event):
        self.drag_start_x = event.x_root - self.winfo_x()
        self.drag_start_y = event.y_root - self.winfo_y()
        self.was_dragged = False

    def _drag_window(self, event):
        new_x = event.x_root - self.drag_start_x
        new_y = event.y_root - self.drag_start_y

        if (
            abs(new_x - self.winfo_x()) > 2
            or abs(new_y - self.winfo_y()) > 2
        ):
            self.was_dragged = True

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        new_x = max(
            0,
            min(new_x, screen_width - 112),
        )
        new_y = max(
            0,
            min(new_y, screen_height - 112),
        )

        self.geometry(f"+{new_x}+{new_y}")

    def _finish_drag(self, _event):
        if not self.was_dragged:
            self.toggle_callback()

        self.after(
            140,
            self._reset_drag_flag,
        )

    def _reset_drag_flag(self):
        self.was_dragged = False

    def _handle_right_click(self, _event):
        if self.exit_callback is not None:
            self.exit_callback()

    def _animate(self):
        if not self.animation_running:
            return

        self.animation_step = (
            self.animation_step + 4
        ) % 360
        self._draw_disc()
        self.after(90, self._animate)

    def show(self):
        self.deiconify()
        self.lift()

    def hide(self):
        self.withdraw()

    def set_state(self, state: str):
        self.current_state = state

        animated_states = {
            "preparing",
            "listening",
            "thinking",
            "speaking",
        }

        should_animate = state in animated_states

        if should_animate and not self.animation_running:
            self.animation_running = True
            self._animate()
        elif not should_animate:
            self.animation_running = False
            self.animation_step = 0
            self._draw_disc()