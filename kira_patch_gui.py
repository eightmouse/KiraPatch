#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import ctypes
import io
import sys
import threading
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
    "bg": "#07111D",
    "card": "#0D1D33",
    "card_alt": "#122844",
    "field": "#10233A",
    "border": "#1C3A5D",
    "accent": "#69B7FF",
    "accent_active": "#8BC8FF",
    "text": "#EEF5FF",
    "muted": "#9DB4D1",
}

WINDOW_SIZE = "500x740"
FILES_HEIGHT = 220
LOG_HEIGHT = 190
WM_DROPFILES = 0x0233
GWL_WNDPROC = -4
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_TEXT_COLOR = 36
LONG_PTR = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LONG_PTR, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


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
        self.root.configure(bg=COLORS["bg"])
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.paths: list[Path] = []
        self.worker: threading.Thread | None = None
        self.log_queue: Queue[tuple[str, object]] = Queue()
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

        self._configure_theme()
        self._set_icon()
        self._build_ui()
        self.root.update_idletasks()
        self._apply_window_chrome()
        self._enable_file_drops()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        if startup_paths:
            self.add_paths(startup_paths)

        self._sync_custom_odds_state()
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
        self.root.option_add("*TCombobox*Listbox.selectForeground", COLORS["bg"])

    def _set_icon(self) -> None:
        png_path = resource_path("logo.png")
        if png_path.exists():
            try:
                self._icon_image = tk.PhotoImage(file=str(png_path))
                self.root.iconphoto(True, self._icon_image)
                self._logo_image = self._icon_image.subsample(3, 3)
                return
            except tk.TclError:
                self._icon_image = None

        ico_path = resource_path("logo.ico")
        if ico_path.exists():
            try:
                self.root.iconbitmap(default=str(ico_path))
            except tk.TclError:
                pass

    def _apply_window_chrome(self) -> None:
        if sys.platform != "win32":
            return
        self._hwnd = self.root.winfo_id()
        try:
            dwmapi = ctypes.windll.dwmapi
        except AttributeError:
            return

        def set_attr(attribute: int, value: int) -> None:
            data = ctypes.c_int(value)
            dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(self._hwnd),
                ctypes.c_uint(attribute),
                ctypes.byref(data),
                ctypes.sizeof(data),
            )

        try:
            set_attr(DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
            set_attr(DWMWA_CAPTION_COLOR, colorref_from_hex(COLORS["card"]))
            set_attr(DWMWA_TEXT_COLOR, colorref_from_hex(COLORS["text"]))
            set_attr(DWMWA_BORDER_COLOR, colorref_from_hex(COLORS["border"]))
        except OSError:
            pass

    def _build_ui(self) -> None:
        container = tk.Frame(self.root, bg=COLORS["bg"], padx=16, pady=16)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)

        header = self._make_card(container)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        if self._logo_image is not None:
            tk.Label(header, image=self._logo_image, bg=COLORS["card"]).grid(
                row=0, column=0, rowspan=2, sticky="nw", padx=(0, 12)
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
            text="Gen3 Shiny Patcher built in Python.\nGitHub@eightmouse",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            justify="left",
            wraplength=300,
            font=("Segoe UI", 10),
        ).grid(row=1, column=1, sticky="w", pady=(4, 0))

        files_card = self._make_card(container)
        files_card.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        files_card.columnconfigure(0, weight=1)

        tk.Label(
            files_card,
            text="ROM Files",
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 12),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            files_card,
            text="Drag and drop .gba files onto this window, or use Add ROMs.",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
        ).grid(row=1, column=0, sticky="w", pady=(4, 10))

        list_shell = tk.Frame(
            files_card,
            bg=COLORS["field"],
            highlightbackground=COLORS["border"],
            highlightthickness=1,
            bd=0,
            height=FILES_HEIGHT,
        )
        list_shell.grid(row=2, column=0, sticky="ew")
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
            selectforeground=COLORS["bg"],
            highlightthickness=0,
            relief="flat",
            font=("Segoe UI", 10),
        )
        self.file_list.grid(row=0, column=0, sticky="nsew")

        file_scroll = self._make_scrollbar(list_shell, self.file_list.yview)
        file_scroll.grid(row=0, column=1, sticky="ns")
        self.file_list.configure(yscrollcommand=file_scroll.set)

        footer_row = tk.Frame(files_card, bg=COLORS["card"])
        footer_row.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        footer_row.columnconfigure(0, weight=1)
        footer_row.columnconfigure(1, weight=1)
        footer_row.columnconfigure(2, weight=1)

        self._make_button(footer_row, "Add ROMs", self.choose_files).grid(row=0, column=0, sticky="ew")
        self._make_button(footer_row, "Remove", self.remove_selected).grid(row=0, column=1, sticky="ew", padx=8)
        self._make_button(footer_row, "Clear", self.clear_files).grid(row=0, column=2, sticky="ew")

        tk.Label(
            files_card,
            textvariable=self.file_count_text,
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
        ).grid(row=4, column=0, sticky="w", pady=(10, 0))

        settings_card = self._make_card(container)
        settings_card.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        settings_card.columnconfigure(1, weight=1)

        tk.Label(
            settings_card,
            text="Patch Settings",
            bg=COLORS["card"],
            fg=COLORS["text"],
            font=("Segoe UI Semibold", 12),
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(
            settings_card,
            text="Mode is fixed to auto so the EXE stays on canonical shiny generation.",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=("Segoe UI", 10),
            wraplength=400,
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
            text="1/16 works, but it can freeze. 1/128 or 1/256 are recommended for normal play.",
            bg=COLORS["card"],
            fg=COLORS["muted"],
            font=("Segoe UI", 9),
            wraplength=400,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 14))

        self.patch_button = self._make_button(settings_card, "Patch", self.start_patch, accent=True)
        self.patch_button.grid(row=5, column=0, columnspan=2, sticky="ew")

        log_card = self._make_card(container)
        log_card.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        log_card.columnconfigure(0, weight=1)

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
        log_shell.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        log_shell.grid_propagate(False)
        log_shell.columnconfigure(0, weight=1)
        log_shell.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            log_shell,
            height=10,
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
        status.grid(row=4, column=0, sticky="ew", pady=(12, 0))

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
        fg = COLORS["bg"] if accent else COLORS["text"]
        active_bg = COLORS["accent_active"] if accent else COLORS["field"]
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=active_bg,
            activeforeground=fg,
            disabledforeground=COLORS["muted"],
            relief="flat",
            bd=0,
            highlightthickness=0,
            padx=12,
            pady=10,
            cursor="hand2",
            font=("Segoe UI Semibold", 10),
        )

    def _make_scrollbar(self, parent: tk.Misc, command: object) -> tk.Scrollbar:
        return tk.Scrollbar(
            parent,
            orient="vertical",
            command=command,
            bg=COLORS["card_alt"],
            troughcolor=COLORS["bg"],
            activebackground=COLORS["accent"],
            highlightbackground=COLORS["card_alt"],
            highlightcolor=COLORS["card_alt"],
            elementborderwidth=0,
            borderwidth=0,
            relief="flat",
            width=12,
        )

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
        if msg == WM_DROPFILES:
            paths = self._extract_drop_paths(wparam)
            self.root.after(0, lambda drop_paths=paths: self._handle_drop(drop_paths))
            return 0
        return int(self._call_window_proc(self._old_wndproc, hwnd, msg, wparam, lparam))

    def _extract_drop_paths(self, hdrop: int) -> list[Path]:
        shell32 = ctypes.windll.shell32
        shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
        shell32.DragQueryFileW.restype = wintypes.UINT
        shell32.DragFinish.argtypes = [wintypes.HANDLE]

        count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
        paths: list[Path] = []
        for idx in range(count):
            length = shell32.DragQueryFileW(hdrop, idx, None, 0)
            buffer = ctypes.create_unicode_buffer(length + 1)
            shell32.DragQueryFileW(hdrop, idx, buffer, length + 1)
            paths.append(Path(buffer.value))
        shell32.DragFinish(hdrop)
        return paths

    def _handle_drop(self, dropped_paths: list[Path]) -> None:
        if not dropped_paths:
            return
        before = len(self.paths)
        self.add_paths(dropped_paths)
        added = len(self.paths) - before
        if added > 0:
            self.status_text.set(f"Added {added} file(s) by drag and drop.")
            self._append_log(f"Added {added} file(s) by drag and drop.\n")

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
        self.odds_combo.configure(state=combo_state)
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
            self.add_paths([Path(p) for p in selected])
            self.status_text.set("ROMs added.")

    def add_paths(self, new_paths: list[Path]) -> None:
        known = set()
        for path in self.paths:
            try:
                known.add(path.resolve())
            except OSError:
                continue

        for path in new_paths:
            if path.suffix.lower() != ".gba":
                continue
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in known:
                continue
            self.paths.append(path)
            self.file_list.insert("end", str(path))
            known.add(resolved)
        self._update_file_count()

    def remove_selected(self) -> None:
        indices = list(self.file_list.curselection())
        if not indices:
            return
        for idx in reversed(indices):
            self.file_list.delete(idx)
            del self.paths[idx]
        self._update_file_count()
        self.status_text.set("Selected ROMs removed.")

    def clear_files(self) -> None:
        self.file_list.delete(0, "end")
        self.paths.clear()
        self._update_file_count()
        self.status_text.set("ROM list cleared.")

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

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
        self.patch_button.configure(state=tk.DISABLED if busy else tk.NORMAL)
        self.odds_combo.configure(state="disabled" if busy else "readonly")
        self.custom_entry.configure(state="disabled" if busy else entry_state)

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
            with contextlib.redirect_stdout(buffer):
                rc = patch_rom(
                    input_path=path,
                    odds=odds,
                    mode="auto",
                    output_path=None,
                    overwrite_output=False,
                    auto_rename_output=True,
                )
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
                elif kind == "done":
                    summary = str(payload)
                    self._append_log(f"{summary}\n")
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
