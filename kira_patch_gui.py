#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import ctypes
import io
import sys
import threading
from collections import deque
from ctypes import wintypes
from pathlib import Path
from queue import Empty, Queue

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from shiny_patcher import patch_rom


ODDS_PRESETS = (
    "8192",
    "4096",
    "2048",
    "1024",
    "512",
    "256",
    "128",
    "64",
    "32",
    "16",
    "Custom",
)

COLORS = {
    "bg": "#081321",
    "card": "#0D1D33",
    "card_alt": "#142942",
    "field": "#10233A",
    "border": "#1B395C",
    "accent": "#2E86D6",
    "accent_active": "#1F5D94",
    "titlebar": "#0B1626",
    "title_button_hover": "#1B395C",
    "title_close_hover": "#8F3340",
    "text": "#EEF5FF",
    "muted": "#9DB4D1",
}

WINDOW_SIZE = "920x620"
FILES_HEIGHT = 204
LIVE_LOG_HEIGHT = 92
LOG_HEIGHT = 116
WM_DROPFILES = 0x0233
GWL_WNDPROC = -4
GWL_STYLE = -16
DWMWA_USE_IMMERSIVE_DARK_MODE_OLD = 19
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_MAXIMIZEBOX = 0x00010000
WS_MINIMIZEBOX = 0x00020000
WS_SYSMENU = 0x00080000
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020
LONG_PTR = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LONG_PTR, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidates = (
        base / "assets" / name,
        base / name,
        Path(__file__).resolve().parent / "assets" / name,
        Path(__file__).resolve().parent / name,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def colorref_from_hex(hex_color: str) -> int:
    value = hex_color.lstrip("#")
    red = int(value[0:2], 16)
    green = int(value[2:4], 16)
    blue = int(value[4:6], 16)
    return red | (green << 8) | (blue << 16)


class KiraPatchApp:
    def __init__(self, root: tk.Tk, startup_paths: list[Path]) -> None:
        self.root = root
        self.root.title("KiraPatch")
        self.root.geometry(WINDOW_SIZE)
        self.root.resizable(False, False)
        self.root.configure(bg=COLORS["border"])
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.paths: list[Path] = []
        self.worker: threading.Thread | None = None
        self.log_queue: Queue[tuple[str, object]] = Queue()
        self.live_log_lines: deque[str] = deque(maxlen=8)
        self.odds_choice = tk.StringVar(value="256")
        self.custom_odds = tk.StringVar(value="256")
        self.status_text = tk.StringVar(value="Drag .gba files into the window or click Add ROMs.")
        self.file_count_text = tk.StringVar(value="No ROMs selected")

        self._icon_image: tk.PhotoImage | None = None
        self._logo_image: tk.PhotoImage | None = None
        self._window_proc_ref: WNDPROC | None = None
        self._old_wndproc: int | None = None
        self._hwnd: int | None = None
        self._call_window_proc = None
        self._drag_offset = (0, 0)

        self.file_buttons: list[tk.Button] = []
        self.patch_button: tk.Button | None = None
        self.log_text: tk.Text | None = None
        self.live_log_text: tk.Text | None = None
        self.odds_combo: ttk.Combobox | None = None
        self.custom_entry: tk.Entry | None = None
        self.file_list: tk.Listbox | None = None

        self._configure_theme()
        self._set_icon()
        self._build_ui()
        self.root.update_idletasks()
        self._enable_custom_frame()
        self.root.after(160, self._enable_custom_frame)
        self._enable_file_drops()
        self.root.bind("<Map>", self._on_window_map, add="+")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if startup_paths:
            self.add_paths(startup_paths)

        self._sync_custom_odds_state()
        self._set_busy(False)
        self._append_log("KiraPatch ready. Auto mode uses canonical shiny generation.\n")
        self.root.after(100, self._poll_log_queue)

    def _configure_theme(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "App.TCombobox",
            padding=7,
            foreground=COLORS["text"],
            fieldbackground=COLORS["field"],
            background=COLORS["field"],
            bordercolor=COLORS["border"],
            lightcolor=COLORS["border"],
            darkcolor=COLORS["border"],
            arrowcolor=COLORS["text"],
        )
        style.map(
            "App.TCombobox",
            foreground=[("readonly", COLORS["text"]), ("disabled", COLORS["muted"])],
            fieldbackground=[("readonly", COLORS["field"]), ("disabled", COLORS["field"])],
            background=[("readonly", COLORS["field"]), ("active", COLORS["card_alt"]), ("disabled", COLORS["field"])],
            selectforeground=[("readonly", COLORS["text"])],
            selectbackground=[("readonly", COLORS["field"])],
        )
        self.root.option_add("*TCombobox*Listbox.background", COLORS["field"])
        self.root.option_add("*TCombobox*Listbox.foreground", COLORS["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", COLORS["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", COLORS["text"])

    def _set_icon(self) -> None:
        png_path = resource_path("logo.png")
        if png_path.exists():
            try:
                self._icon_image = tk.PhotoImage(file=str(png_path))
                self.root.iconphoto(True, self._icon_image)
                self._logo_image = self._icon_image.subsample(4, 4)
                return
            except tk.TclError:
                self._icon_image = None

        ico_path = resource_path("logo.ico")
        if ico_path.exists():
            try:
                self.root.iconbitmap(default=str(ico_path))
            except tk.TclError:
                pass

    def _enable_custom_frame(self) -> None:
        if sys.platform == "win32":
            try:
                self.root.overrideredirect(True)
            except tk.TclError:
                return
        self._apply_window_frame()

    def _apply_window_frame(self) -> None:
        if sys.platform != "win32":
            return

        self._hwnd = self.root.winfo_id()
        try:
            user32 = ctypes.windll.user32
            dwmapi = ctypes.windll.dwmapi
        except AttributeError:
            return

        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.GetWindowLongW.restype = ctypes.c_long
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
        user32.SetWindowLongW.restype = ctypes.c_long
        user32.SetWindowPos.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
        ]
        user32.SetWindowPos.restype = wintypes.BOOL

        try:
            current_style = user32.GetWindowLongW(self._hwnd, GWL_STYLE)
            target_style = (current_style & ~(WS_CAPTION | WS_THICKFRAME | WS_MAXIMIZEBOX)) | WS_MINIMIZEBOX | WS_SYSMENU
            if target_style != current_style:
                user32.SetWindowLongW(self._hwnd, GWL_STYLE, target_style)
            user32.SetWindowPos(
                wintypes.HWND(self._hwnd),
                wintypes.HWND(0),
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_FRAMECHANGED,
            )
        except OSError:
            return

        def set_attr(attribute: int, value: int) -> None:
            data = ctypes.c_int(value)
            result = dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(self._hwnd),
                ctypes.c_uint(attribute),
                ctypes.byref(data),
                ctypes.sizeof(data),
            )
            if result != 0:
                raise OSError(result, f"DwmSetWindowAttribute failed for {attribute}")

        for dark_attr in (DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_USE_IMMERSIVE_DARK_MODE_OLD):
            try:
                set_attr(dark_attr, 1)
            except OSError:
                continue

        try:
            set_attr(DWMWA_CAPTION_COLOR, colorref_from_hex(COLORS["titlebar"]))
            set_attr(DWMWA_TEXT_COLOR, colorref_from_hex(COLORS["text"]))
            set_attr(DWMWA_BORDER_COLOR, colorref_from_hex(COLORS["border"]))
        except OSError:
            pass

    def _build_ui(self) -> None:
        shell = tk.Frame(self.root, bg=COLORS["border"], padx=1, pady=1)
        shell.grid(row=0, column=0, sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        titlebar = self._build_titlebar(shell)
        titlebar.grid(row=0, column=0, sticky="ew")

        body = tk.Frame(shell, bg=COLORS["bg"])
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)

        container = tk.Frame(body, bg=COLORS["bg"], padx=16, pady=16)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        header = self._make_card(container)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        if self._logo_image is not None:
            tk.Label(header, image=self._logo_image, bg=COLORS["card"]).grid(
                row=0, column=0, rowspan=2, sticky="w", padx=(0, 14)
            )

        tk.Label(
            header,
            text="KiraPatch",
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 18),
        ).grid(row=0, column=1, sticky="w")
        tk.Label(
            header,
            text="Gen3 shiny patcher with canonical legal rerolls.\nGitHub@eightmouse",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            justify="left",
            wraplength=620,
            font=("Segoe UI", 10),
        ).grid(row=1, column=1, sticky="w", pady=(4, 0))

        panels = tk.Frame(container, bg=COLORS["bg"])
        panels.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        panels.columnconfigure(0, weight=1, uniform="panel")
        panels.columnconfigure(1, weight=1, uniform="panel")
        panels.rowconfigure(0, weight=1)

        files_card = self._make_card(panels)
        files_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        files_card.columnconfigure(0, weight=1)
        files_card.rowconfigure(2, weight=1)

        tk.Label(
            files_card,
            text="ROM Files",
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 12),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            files_card,
            text="Drag and drop .gba files into the window, or use Add ROMs.",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
            wraplength=360,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 10))

        list_shell = tk.Frame(
            files_card,
            bg=COLORS["field"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            bd=0,
            height=FILES_HEIGHT,
        )
        list_shell.grid(row=2, column=0, sticky="nsew")
        list_shell.grid_propagate(False)
        list_shell.columnconfigure(0, weight=1)
        list_shell.rowconfigure(0, weight=1)

        self.file_list = tk.Listbox(
            list_shell,
            selectmode=tk.EXTENDED,
            height=10,
            activestyle="none",
            bg=COLORS["field"],
            fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            selectforeground=COLORS["text"],
            highlightthickness=0,
            relief="flat",
            font=("Segoe UI", 10),
        )
        self.file_list.grid(row=0, column=0, sticky="nsew")

        file_scroll = self._make_scrollbar(list_shell, self.file_list.yview)
        file_scroll.grid(row=0, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=file_scroll.set)

        footer_row = tk.Frame(files_card, bg=COLORS["card"])
        footer_row.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        footer_row.columnconfigure(0, weight=1, uniform="file_buttons")
        footer_row.columnconfigure(1, weight=1, uniform="file_buttons")
        footer_row.columnconfigure(2, weight=1, uniform="file_buttons")

        add_button = self._make_button(footer_row, "Add ROMs", self.choose_files)
        remove_button = self._make_button(footer_row, "Remove", self.remove_selected)
        clear_button = self._make_button(footer_row, "Clear", self.clear_files)
        add_button.grid(row=0, column=0, sticky="ew")
        remove_button.grid(row=0, column=1, sticky="ew", padx=8)
        clear_button.grid(row=0, column=2, sticky="ew")
        self.file_buttons = [add_button, remove_button, clear_button]

        tk.Label(
            files_card,
            textvariable=self.file_count_text,
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
        ).grid(row=4, column=0, sticky="w", pady=(8, 0))

        settings_card = self._make_card(panels)
        settings_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        settings_card.columnconfigure(1, weight=1)
        settings_card.rowconfigure(7, weight=1)

        tk.Label(
            settings_card,
            text="Patch Settings",
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 12),
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(
            settings_card,
            text="Mode stays on auto so the EXE always uses the canonical legal shiny path.",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
            wraplength=360,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))

        tk.Label(
            settings_card,
            text="Odds (1 in N)",
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=("Segoe UI", 10),
        ).grid(row=2, column=0, sticky="w")
        self.odds_combo = ttk.Combobox(
            settings_card,
            textvariable=self.odds_choice,
            values=ODDS_PRESETS,
            state="readonly",
            style="App.TCombobox",
        )
        self.odds_combo.grid(row=2, column=1, sticky="ew")
        self.odds_combo.bind("<<ComboboxSelected>>", self._on_odds_selected)

        tk.Label(
            settings_card,
            text="Custom N",
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=("Segoe UI", 10),
        ).grid(row=3, column=0, sticky="w", pady=(10, 0))
        self.custom_entry = tk.Entry(
            settings_card,
            textvariable=self.custom_odds,
            bg=COLORS["field"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            disabledbackground=COLORS["field"],
            disabledforeground=COLORS["muted"],
            relief="flat",
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
            highlightthickness=1,
            bd=0,
            font=("Segoe UI", 10),
        )
        self.custom_entry.grid(row=3, column=1, sticky="ew", pady=(10, 0))

        tk.Label(
            settings_card,
            text="1/16 is valid but it can pause. 1/128 or 1/256 are smoother for normal play.",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            wraplength=360,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 14))

        self.patch_button = self._make_button(settings_card, "Patch", self.start_patch, accent=True)
        self.patch_button.grid(row=5, column=0, columnspan=2, sticky="ew")

        tk.Label(
            settings_card,
            text="Live Output",
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 11),
        ).grid(row=6, column=0, columnspan=2, sticky="w", pady=(10, 6))

        live_shell = tk.Frame(
            settings_card,
            bg=COLORS["field"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            bd=0,
            height=LIVE_LOG_HEIGHT,
        )
        live_shell.grid(row=7, column=0, columnspan=2, sticky="nsew")
        live_shell.grid_propagate(False)
        live_shell.columnconfigure(0, weight=1)
        live_shell.rowconfigure(0, weight=1)

        self.live_log_text = tk.Text(
            live_shell,
            height=4,
            wrap="word",
            state="disabled",
            bg=COLORS["field"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightthickness=0,
            bd=0,
            font=("Consolas", 9),
        )
        self.live_log_text.grid(row=0, column=0, sticky="nsew")

        live_scroll = self._make_scrollbar(live_shell, self.live_log_text.yview)
        live_scroll.grid(row=0, column=1, sticky="ns")
        self.live_log_text.configure(yscrollcommand=live_scroll.set)

        log_card = self._make_card(container)
        log_card.grid(row=2, column=0, sticky="nsew", pady=(10, 0))
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)

        tk.Label(
            log_card,
            text="Patch Log",
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 12),
        ).grid(row=0, column=0, sticky="w")

        log_shell = tk.Frame(
            log_card,
            bg=COLORS["field"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            bd=0,
            height=LOG_HEIGHT,
        )
        log_shell.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        log_shell.grid_propagate(False)
        log_shell.columnconfigure(0, weight=1)
        log_shell.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_shell,
            height=8,
            wrap="word",
            state="disabled",
            bg=COLORS["field"],
            fg=COLORS["text"],
            insertbackground=COLORS["text"],
            relief="flat",
            highlightthickness=0,
            bd=0,
            font=("Consolas", 9),
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        log_scroll = self._make_scrollbar(log_shell, self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)

        status = tk.Label(
            container,
            textvariable=self.status_text,
            bg=COLORS["bg"],
            fg=COLORS["muted"],
            anchor="w",
            justify="left",
            font=("Segoe UI", 9),
        )
        status.grid(row=3, column=0, sticky="ew", pady=(12, 0))

    def _build_titlebar(self, parent: tk.Misc) -> tk.Frame:
        titlebar = tk.Frame(parent, bg=COLORS["titlebar"], height=42)
        titlebar.grid_propagate(False)
        titlebar.columnconfigure(1, weight=1)

        if self._logo_image is not None:
            icon_label = tk.Label(titlebar, image=self._logo_image, bg=COLORS["titlebar"])
            icon_label.grid(row=0, column=0, sticky="w", padx=(12, 8), pady=6)
        else:
            icon_label = tk.Label(titlebar, text="", bg=COLORS["titlebar"], width=2)
            icon_label.grid(row=0, column=0, sticky="w", padx=(12, 8), pady=6)

        title_label = tk.Label(
            titlebar,
            text="KiraPatch",
            bg=COLORS["titlebar"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 11),
        )
        title_label.grid(row=0, column=1, sticky="w")

        controls = tk.Frame(titlebar, bg=COLORS["titlebar"])
        controls.grid(row=0, column=2, sticky="e")

        minimize_button = self._make_title_button(controls, "_", self._minimize_window)
        minimize_button.grid(row=0, column=0)
        close_button = self._make_title_button(controls, "X", self._on_close, close_button=True)
        close_button.grid(row=0, column=1)

        for widget in (titlebar, icon_label, title_label):
            widget.bind("<ButtonPress-1>", self._start_window_drag, add="+")
            widget.bind("<B1-Motion>", self._drag_window, add="+")

        return titlebar

    def _make_card(self, parent: tk.Misc) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=COLORS["card"],
            padx=14,
            pady=14,
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            bd=0,
        )

    def _make_button(self, parent: tk.Misc, text: str, command: object, accent: bool = False) -> tk.Button:
        bg = COLORS["accent"] if accent else COLORS["card_alt"]
        fg = COLORS["text"]
        active_bg = COLORS["accent_active"] if accent else COLORS["field"]
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=COLORS["text"],
            disabledforeground=COLORS["text"] if accent else COLORS["muted"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=12,
            pady=10,
            cursor="hand2",
            takefocus=0,
            font=("Segoe UI Semibold", 10),
        )

    def _make_title_button(self, parent: tk.Misc, text: str, command: object, close_button: bool = False) -> tk.Button:
        active_bg = COLORS["title_close_hover"] if close_button else COLORS["title_button_hover"]
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=COLORS["titlebar"],
            fg=COLORS["text"],
            activebackground=active_bg,
            activeforeground=COLORS["text"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            width=4,
            pady=7,
            cursor="hand2",
            takefocus=0,
            font=("Segoe UI Semibold", 11),
        )

    def _make_scrollbar(self, parent: tk.Misc, command: object) -> tk.Scrollbar:
        return tk.Scrollbar(
            parent,
            orient="vertical",
            command=command,
            bg=COLORS["field"],
            troughcolor=COLORS["bg"],
            activebackground=COLORS["card_alt"],
            highlightbackground=COLORS["field"],
            highlightcolor=COLORS["field"],
            elementborderwidth=0,
            borderwidth=0,
            relief="flat",
            width=12,
        )

    def _start_window_drag(self, event: tk.Event) -> None:
        self._drag_offset = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag_window(self, event: tk.Event) -> None:
        offset_x, offset_y = self._drag_offset
        self.root.geometry(f"+{event.x_root - offset_x}+{event.y_root - offset_y}")

    def _minimize_window(self) -> None:
        if sys.platform == "win32":
            try:
                self.root.overrideredirect(False)
            except tk.TclError:
                pass
        self.root.iconify()

    def _on_window_map(self, _event: tk.Event) -> None:
        if sys.platform == "win32" and self.root.state() == "normal":
            self.root.after(10, self._enable_custom_frame)

    def _enable_file_drops(self) -> None:
        if sys.platform != "win32":
            return

        self.root.update_idletasks()
        self._hwnd = self.root.winfo_id()
        shell32 = ctypes.windll.shell32
        user32 = ctypes.windll.user32

        shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
        shell32.DragAcceptFiles(self._hwnd, True)

        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
        user32.SetWindowLongPtrW.restype = LONG_PTR
        user32.CallWindowProcW.argtypes = [LONG_PTR, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallWindowProcW.restype = LONG_PTR
        self._call_window_proc = user32.CallWindowProcW

        self._window_proc_ref = WNDPROC(self._window_proc)
        self._old_wndproc = user32.SetWindowLongPtrW(
            self._hwnd,
            GWL_WNDPROC,
            ctypes.cast(self._window_proc_ref, ctypes.c_void_p).value,
        )

    def _restore_window_proc(self) -> None:
        if sys.platform != "win32" or self._hwnd is None or self._old_wndproc is None:
            return
        user32 = ctypes.windll.user32
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, LONG_PTR]
        user32.SetWindowLongPtrW.restype = LONG_PTR
        user32.SetWindowLongPtrW(self._hwnd, GWL_WNDPROC, self._old_wndproc)
        self._old_wndproc = None

    def _window_proc(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        try:
            if msg == WM_DROPFILES:
                paths = self._extract_drop_paths(wparam)
                self.root.after(0, lambda drop_paths=paths: self._handle_drop(drop_paths))
                return 0
        except Exception as exc:
            self.root.after(0, lambda err=str(exc): self._report_drop_error(err))
            return 0

        if self._call_window_proc is not None and self._old_wndproc is not None:
            return int(self._call_window_proc(self._old_wndproc, hwnd, msg, wparam, lparam))
        return 0

    def _extract_drop_paths(self, hdrop: int) -> list[Path]:
        shell32 = ctypes.windll.shell32
        shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
        shell32.DragQueryFileW.restype = wintypes.UINT
        shell32.DragFinish.argtypes = [wintypes.HANDLE]

        paths: list[Path] = []
        try:
            count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
            for idx in range(count):
                length = shell32.DragQueryFileW(hdrop, idx, None, 0)
                buffer = ctypes.create_unicode_buffer(length + 1)
                shell32.DragQueryFileW(hdrop, idx, buffer, length + 1)
                if buffer.value:
                    paths.append(Path(buffer.value))
        finally:
            shell32.DragFinish(hdrop)
        return paths

    def _report_drop_error(self, message: str) -> None:
        self.status_text.set("Drag and drop failed. Try Add ROMs instead.")
        self._append_log(f"[WARN] Drag and drop failed: {message}\n")

    def _handle_drop(self, dropped_paths: list[Path]) -> None:
        try:
            if not dropped_paths:
                return
            added, ignored = self.add_paths(dropped_paths)
            if added > 0:
                self.status_text.set(f"Added {added} file(s) by drag and drop.")
                self._append_log(f"Added {added} file(s) by drag and drop.\n")
            elif ignored > 0:
                self.status_text.set("No .gba files were added from that drop.")
                self._append_log("Ignored dropped items that were not new .gba files.\n")
        except Exception as exc:
            self._report_drop_error(str(exc))

    def _on_close(self) -> None:
        self._restore_window_proc()
        self.root.destroy()

    def _on_odds_selected(self, _event: object) -> None:
        self._sync_custom_odds_state()

    def _sync_custom_odds_state(self) -> None:
        is_custom = self.odds_choice.get() == "Custom"
        combo_state = "readonly" if self.worker is None or not self.worker.is_alive() else "disabled"
        entry_state = "normal" if is_custom else "disabled"
        if combo_state == "disabled":
            entry_state = "disabled"
        if self.odds_combo is not None:
            self.odds_combo.configure(state=combo_state)
        if self.custom_entry is not None:
            self.custom_entry.configure(state=entry_state)
        if not is_custom:
            self.custom_odds.set(self.odds_choice.get())

    def _update_file_count(self) -> None:
        count = len(self.paths)
        if count == 0:
            self.file_count_text.set("No ROMs selected")
        elif count == 1:
            self.file_count_text.set("1 ROM queued")
        else:
            self.file_count_text.set(f"{count} ROMs queued")

    def choose_files(self) -> None:
        selected = filedialog.askopenfilenames(
            title="Select Gen 3 ROMs",
            filetypes=[("GBA ROMs", "*.gba"), ("All files", "*.*")],
        )
        if selected:
            added, _ignored = self.add_paths([Path(p) for p in selected])
            if added > 0:
                self.status_text.set("ROMs added.")

    def add_paths(self, new_paths: list[Path]) -> tuple[int, int]:
        known = set()
        for path in self.paths:
            try:
                known.add(path.resolve(strict=False))
            except OSError:
                continue

        added = 0
        ignored = 0
        for path in new_paths:
            if path.suffix.lower() != ".gba":
                ignored += 1
                continue
            try:
                resolved = path.resolve(strict=False)
            except OSError:
                ignored += 1
                continue
            if resolved in known:
                ignored += 1
                continue
            self.paths.append(path)
            if self.file_list is not None:
                self.file_list.insert("end", str(path))
            known.add(resolved)
            added += 1

        self._update_file_count()
        return added, ignored

    def remove_selected(self) -> None:
        if self.file_list is None:
            return
        indices = list(self.file_list.curselection())
        if not indices:
            return
        for idx in reversed(indices):
            self.file_list.delete(idx)
            del self.paths[idx]
        self._update_file_count()
        self.status_text.set("Selected ROMs removed.")

    def clear_files(self) -> None:
        if self.file_list is not None:
            self.file_list.delete(0, "end")
        self.paths.clear()
        self._update_file_count()
        self.status_text.set("ROM list cleared.")

    def _append_live_log(self, text: str) -> None:
        if self.live_log_text is None:
            return
        for raw_line in text.replace("\r", "\n").splitlines():
            line = raw_line.strip()
            if line:
                self.live_log_lines.append(line)
        if not self.live_log_lines:
            self.live_log_lines.append("Waiting to patch...")
        self.live_log_text.configure(state="normal")
        self.live_log_text.delete("1.0", "end")
        self.live_log_text.insert("end", "\n".join(self.live_log_lines))
        self.live_log_text.see("end")
        self.live_log_text.configure(state="disabled")

    def _append_log(self, text: str) -> None:
        if self.log_text is not None:
            self.log_text.configure(state="normal")
            self.log_text.insert("end", text)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self._append_live_log(text)

    def _selected_odds(self) -> int | None:
        raw = self.custom_odds.get().strip() if self.odds_choice.get() == "Custom" else self.odds_choice.get()
        if not raw.isdigit():
            return None
        value = int(raw)
        if value <= 0:
            return None
        return value

    def _set_busy(self, busy: bool) -> None:
        entry_state = "normal" if self.odds_choice.get() == "Custom" else "disabled"
        if self.patch_button is not None:
            if busy:
                self.patch_button.configure(
                    text="Patching...",
                    bg=COLORS["accent_active"],
                    activebackground=COLORS["accent_active"],
                    fg=COLORS["text"],
                    activeforeground=COLORS["text"],
                    cursor="watch",
                )
            else:
                self.patch_button.configure(
                    text="Patch",
                    bg=COLORS["accent"],
                    activebackground=COLORS["accent_active"],
                    fg=COLORS["text"],
                    activeforeground=COLORS["text"],
                    cursor="hand2",
                )
        if self.odds_combo is not None:
            self.odds_combo.configure(state="disabled" if busy else "readonly")
        if self.custom_entry is not None:
            self.custom_entry.configure(state="disabled" if busy else entry_state)
        for button in self.file_buttons:
            button.configure(state=tk.DISABLED if busy else tk.NORMAL)

    def start_patch(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            return
        if not self.paths:
            messagebox.showerror("KiraPatch", "Add at least one .gba ROM first.")
            return

        odds = self._selected_odds()
        if odds is None:
            messagebox.showerror("KiraPatch", "Enter a valid positive odds value.")
            return

        self.live_log_lines.clear()
        self._append_log(f"\n=== Starting patch run (auto mode, 1/{odds}) ===\n")
        self.status_text.set("Patching...")
        self._set_busy(True)

        paths = list(self.paths)
        self.worker = threading.Thread(target=self._run_patch_worker, args=(paths, odds), daemon=True)
        self.worker.start()

    def _run_patch_worker(self, paths: list[Path], odds: int) -> None:
        passed = 0
        failed = 0

        for path in paths:
            buffer = io.StringIO()
            try:
                with contextlib.redirect_stdout(buffer):
                    rc = patch_rom(
                        input_path=path,
                        odds=odds,
                        mode="auto",
                        output_path=None,
                        overwrite_output=False,
                        auto_rename_output=True,
                    )
            except Exception as exc:
                rc = 1
                print(f"[ERROR] {exc}", file=buffer)
            if rc == 0:
                passed += 1
            else:
                failed += 1
            output = buffer.getvalue()
            prefix = f"\n--- {path.name} ---\n"
            self.log_queue.put(("log", prefix + output + "\n"))

        summary = f"Finished. OK: {passed}  FAIL: {failed}"
        self.log_queue.put(("done", summary))

    def _poll_log_queue(self) -> None:
        try:
            while True:
                kind, payload = self.log_queue.get_nowait()
                if kind == "log":
                    self._append_log(str(payload))
                elif kind == "status":
                    message = str(payload)
                    self.status_text.set(message)
                    self._append_log(message + "\n")
                elif kind == "done":
                    summary = str(payload)
                    self._append_log(summary + "\n")
                    self.status_text.set(summary)
                    self._set_busy(False)
                    if "FAIL: 0" in summary:
                        messagebox.showinfo("KiraPatch", summary)
                    else:
                        messagebox.showwarning("KiraPatch", summary)
        except Empty:
            pass
        self.root.after(100, self._poll_log_queue)

def main() -> int:
    startup_paths = [Path(arg) for arg in sys.argv[1:] if arg.lower().endswith(".gba")]

    root = tk.Tk()
    KiraPatchApp(root, startup_paths)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
