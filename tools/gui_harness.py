#!/usr/bin/env python3
from __future__ import annotations

import argparse
import configparser
import ctypes
import json
import math
import site
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from ctypes import wintypes

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_SITE = REPO_ROOT / '.vendor'
if str(VENDOR_SITE) not in sys.path:
    sys.path.insert(0, str(VENDOR_SITE))
USER_SITE = site.getusersitepackages()
if USER_SITE and USER_SITE not in sys.path:
    sys.path.append(USER_SITE)

USER32 = ctypes.windll.user32
USER32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
USER32.PostMessageW.restype = wintypes.BOOL
USER32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
USER32.SendMessageW.restype = ctypes.c_ssize_t
USER32.SetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPCWSTR)
USER32.SetWindowTextW.restype = wintypes.BOOL
USER32.OpenClipboard.argtypes = (wintypes.HWND,)
USER32.OpenClipboard.restype = wintypes.BOOL
USER32.EmptyClipboard.restype = wintypes.BOOL
USER32.SetClipboardData.argtypes = (wintypes.UINT, ctypes.c_void_p)
USER32.SetClipboardData.restype = ctypes.c_void_p
USER32.CloseClipboard.restype = wintypes.BOOL
KERNEL32 = ctypes.windll.kernel32
KERNEL32.GlobalAlloc.argtypes = (wintypes.UINT, ctypes.c_size_t)
KERNEL32.GlobalAlloc.restype = ctypes.c_void_p
KERNEL32.GlobalLock.argtypes = (ctypes.c_void_p,)
KERNEL32.GlobalLock.restype = ctypes.c_void_p
KERNEL32.GlobalUnlock.argtypes = (ctypes.c_void_p,)
KERNEL32.GlobalUnlock.restype = wintypes.BOOL
KERNEL32.GlobalFree.argtypes = (ctypes.c_void_p,)
KERNEL32.GlobalFree.restype = ctypes.c_void_p
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_COMMAND = 0x0111
WM_DROPFILES = 0x0233
WM_SETTEXT = 0x000C
BM_CLICK = 0x00F5
SW_RESTORE = 9
KEYEVENTF_KEYUP = 0x0002
SPI_GETWORKAREA = 0x0030
MF_BYPOSITION = 0x0400
GHND = 0x0042
CF_UNICODETEXT = 13
MGBA_CONFIG = Path('tools/mGBA-0.10.5-win64/config.ini')
MGBA_QT_SECTION = 'gba.input.QT_K'
BUTTON_ALIASES = {
    'A': 'A',
    'B': 'B',
    'START': 'Start',
    'SELECT': 'Select',
    'UP': 'Up',
    'DOWN': 'Down',
    'LEFT': 'Left',
    'RIGHT': 'Right',
    'L': 'L',
    'R': 'R',
}
QT_SPECIAL_TO_VK = {
    16777219: 0x08,
    16777220: 0x0D,
    16777234: 0x25,
    16777235: 0x26,
    16777236: 0x27,
    16777237: 0x28,
}
TARGET_FILTERS = {
    'mgba': ('mgba - ',),
    'pkhex': ('pkhex',),
}
HOST_HOTKEYS = {
    'control': 0x11,
    'ctrl': 0x11,
    'alt': 0x12,
    'r': 0x52,
    'm': 0x4D,
    'o': 0x4F,
    'v': 0x56,
    'd': 0x44,
    'enter': 0x0D,
    'shift': 0x10,
    'tab': 0x09,
    'f1': 0x70,
    'f2': 0x71,
    'f3': 0x72,
    'f4': 0x73,
    'f5': 0x74,
    'f6': 0x75,
    'f7': 0x76,
    'f8': 0x77,
    'f9': 0x78,
}


class RECT(ctypes.Structure):
    _fields_ = [('left', ctypes.c_long), ('top', ctypes.c_long), ('right', ctypes.c_long), ('bottom', ctypes.c_long)]


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


class DROPFILES(ctypes.Structure):
    _fields_ = [
        ('pFiles', wintypes.DWORD),
        ('pt', POINT),
        ('fNC', wintypes.BOOL),
        ('fWide', wintypes.BOOL),
    ]


@dataclass
class MenuItem:
    path: tuple[str, ...]
    text: str
    command_id: int | None

    @property
    def normalized_path(self) -> tuple[str, ...]:
        return tuple(normalize_menu_text(part) for part in self.path)

    @property
    def normalized_text(self) -> str:
        return normalize_menu_text(self.text)


@dataclass
class TargetWindow:
    handle: int
    title: str
    class_name: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


class WindowWrapper:
    def __init__(self, window: TargetWindow):
        self.handle = window.handle
        self.window = window

    def set_focus(self) -> None:
        activate_handle(self.handle)


def window_text(handle: int) -> str:
    length = USER32.GetWindowTextLengthW(handle)
    buf = ctypes.create_unicode_buffer(length + 1)
    USER32.GetWindowTextW(handle, buf, length + 1)
    return buf.value


def class_name(handle: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    USER32.GetClassNameW(handle, buf, 256)
    return buf.value


def get_window_rect(handle: int) -> RECT:
    rect = RECT()
    USER32.GetWindowRect(handle, ctypes.byref(rect))
    return rect


def get_window_pid(handle: int) -> int:
    pid = wintypes.DWORD()
    USER32.GetWindowThreadProcessId(handle, ctypes.byref(pid))
    return pid.value


def normalize_menu_text(text: str) -> str:
    cleaned = text.replace('&', '')
    cleaned = cleaned.split('\t', 1)[0]
    cleaned = cleaned.replace('...', '')
    return ' '.join(cleaned.split()).strip().lower()


def enum_windows() -> list[int]:
    result: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(handle, lparam):
        if USER32.IsWindowVisible(handle):
            result.append(handle)
        return True

    USER32.EnumWindows(callback, 0)
    return result


def enum_child_windows(parent: int) -> list[int]:
    result: list[int] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(handle, lparam):
        if USER32.IsWindowVisible(handle):
            result.append(handle)
        return True

    USER32.EnumChildWindows(parent, callback, 0)
    return result


def find_top_window(title: str | None = None, class_filter: str | None = None) -> int | None:
    for handle in enum_windows():
        current_title = window_text(handle)
        current_class = class_name(handle)
        if title is not None and current_title != title:
            continue
        if class_filter is not None and current_class != class_filter:
            continue
        return handle
    return None


def list_windows(target_name: str | None = None, pid: int | None = None) -> list[TargetWindow]:
    filters = TARGET_FILTERS.get(target_name) if target_name else None
    items: list[TargetWindow] = []
    for handle in enum_windows():
        title = window_text(handle)
        cls = class_name(handle)
        rect = get_window_rect(handle)
        if not title.strip():
            continue
        if rect.right - rect.left <= 4 or rect.bottom - rect.top <= 4:
            continue
        lower = title.lower()
        if filters and not any(token in lower for token in filters):
            continue
        if pid is not None and get_window_pid(handle) != pid:
            continue
        items.append(TargetWindow(handle, title, cls, rect.left, rect.top, rect.right, rect.bottom))
    return items


def pick_window(target_name: str, pid: int | None = None) -> TargetWindow:
    windows = list_windows(target_name, pid=pid)
    if not windows:
        raise SystemExit(f'No window found for target {target_name!r}.')
    windows.sort(key=lambda item: item.handle)
    return windows[-1]


def connect_window(window: TargetWindow) -> WindowWrapper:
    return WindowWrapper(window)


def activate_handle(handle: int) -> None:
    USER32.ShowWindow(handle, SW_RESTORE)
    try:
        USER32.SetForegroundWindow(handle)
    except Exception:
        pass


def get_work_area() -> RECT:
    rect = RECT()
    USER32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
    return rect


def move_window(handle: int, x: int, y: int, width: int, height: int) -> None:
    USER32.ShowWindow(handle, SW_RESTORE)
    USER32.MoveWindow(handle, x, y, width, height, True)


def get_menu(handle: int) -> int:
    return USER32.GetMenu(handle)


def get_menu_item_count(menu_handle: int) -> int:
    return USER32.GetMenuItemCount(menu_handle)


def get_sub_menu(menu_handle: int, pos: int) -> int:
    return USER32.GetSubMenu(menu_handle, pos)


def get_menu_item_id(menu_handle: int, pos: int) -> int:
    value = USER32.GetMenuItemID(menu_handle, pos)
    return int(value)


def get_menu_string(menu_handle: int, pos: int) -> str:
    length = USER32.GetMenuStringW(menu_handle, pos, None, 0, MF_BYPOSITION)
    if length <= 0:
        return ''
    buf = ctypes.create_unicode_buffer(length + 1)
    USER32.GetMenuStringW(menu_handle, pos, buf, length + 1, MF_BYPOSITION)
    return buf.value


def walk_menu(menu_handle: int, prefix: tuple[str, ...] = ()) -> list[MenuItem]:
    items: list[MenuItem] = []
    count = get_menu_item_count(menu_handle)
    for pos in range(count):
        text = get_menu_string(menu_handle, pos)
        if not text:
            continue
        path = prefix + (text,)
        submenu = get_sub_menu(menu_handle, pos)
        if submenu:
            items.extend(walk_menu(submenu, path))
            continue
        command_id = get_menu_item_id(menu_handle, pos)
        items.append(MenuItem(path=path, text=text, command_id=None if command_id < 0 else command_id))
    return items


def window_by_handle(handle: int) -> TargetWindow | None:
    for window in list_windows():
        if window.handle == handle:
            return window
    return None


def list_menu_items(handle: int) -> list[MenuItem]:
    menu_handle = get_menu(handle)
    if not menu_handle:
        return []
    return walk_menu(menu_handle)


def find_menu_item(handle: int, pattern: str, exact: bool = False) -> MenuItem:
    normalized = normalize_menu_text(pattern)
    items = list_menu_items(handle)
    matches = []
    for item in items:
        haystack = ' > '.join(item.normalized_path)
        if exact:
            if item.normalized_text == normalized or haystack == normalized:
                matches.append(item)
        else:
            if normalized in item.normalized_text or normalized in haystack:
                matches.append(item)
    if not matches:
        raise SystemExit(f'No menu item matched pattern {pattern!r}.')
    if len(matches) > 1:
        paths = ', '.join(' > '.join(item.path) for item in matches[:5])
        raise SystemExit(f'Ambiguous menu item pattern {pattern!r}: {paths}')
    return matches[0]


def invoke_menu_item(handle: int, pattern: str, exact: bool = False) -> MenuItem:
    item = find_menu_item(handle, pattern, exact=exact)
    if item.command_id is None:
        raise SystemExit(f'Menu item {item.path!r} does not have an invokable command id.')
    USER32.SendMessageW(handle, WM_COMMAND, item.command_id, 0)
    return item


def compute_tile_rect(index: int, count: int, width: int, height: int, padding: int = 12) -> tuple[int, int, int, int]:
    if count <= 0:
        raise ValueError('count must be >= 1')
    if not 0 <= index < count:
        raise ValueError(f'index {index} is out of range for count {count}')
    work = get_work_area()
    cols = min(max(1, count), 2 if count <= 4 else 3)
    rows = math.ceil(count / cols)
    col = index % cols
    row = index // cols
    target_width = width
    target_height = height
    cluster_width = cols * target_width + max(0, cols - 1) * padding
    cluster_height = rows * target_height + max(0, rows - 1) * padding
    max_width = max(320, work.right - work.left - padding * 2)
    max_height = max(240, work.bottom - work.top - padding * 2)
    if cluster_width > max_width:
        target_width = max(320, (max_width - max(0, cols - 1) * padding) // cols)
    if cluster_height > max_height:
        target_height = max(240, (max_height - max(0, rows - 1) * padding) // rows)
    x = work.left + padding + col * (target_width + padding)
    y = work.top + padding + row * (target_height + padding)
    return x, y, target_width, target_height


def tile_window(target_name: str, index: int, count: int, pid: int | None = None, padding: int = 12) -> TargetWindow:
    window = pick_window(target_name, pid=pid)
    x, y, width, height = compute_tile_rect(index, count, window.width, window.height, padding=padding)
    move_window(window.handle, x, y, width, height)
    time.sleep(0.2)
    return pick_window(target_name, pid=pid)


def tile_window_handle(handle: int, index: int, count: int, padding: int = 12) -> TargetWindow:
    window = window_by_handle(handle)
    if not window:
        raise SystemExit(f'Window handle 0x{handle:X} is no longer available.')
    x, y, width, height = compute_tile_rect(index, count, window.width, window.height, padding=padding)
    move_window(window.handle, x, y, width, height)
    time.sleep(0.2)
    refreshed = window_by_handle(handle)
    if not refreshed:
        raise SystemExit(f'Window handle 0x{handle:X} disappeared after tiling.')
    return refreshed


def pick_input_wrapper(target_name: str, pid: int | None = None) -> WindowWrapper:
    window = pick_window(target_name, pid=pid)
    if target_name != 'mgba':
        return WindowWrapper(window)
    children = []
    for handle in enum_child_windows(window.handle):
        rect = get_window_rect(handle)
        area = max(0, rect.right - rect.left) * max(0, rect.bottom - rect.top)
        children.append((area, handle, rect))
    if children:
        children.sort(reverse=True)
        _, handle, rect = children[0]
        return WindowWrapper(TargetWindow(handle, window_text(handle), class_name(handle), rect.left, rect.top, rect.right, rect.bottom))
    return WindowWrapper(window)


def find_child_window(parent: int, class_filter: str | None = None, text: str | None = None) -> int | None:
    for handle in enum_child_windows(parent):
        current_class = class_name(handle)
        current_text = window_text(handle)
        if class_filter is not None and current_class != class_filter:
            continue
        if text is not None and current_text != text:
            continue
        return handle
    return None


def set_window_text(handle: int, text: str) -> None:
    USER32.SetWindowTextW(handle, text)


def click_button(handle: int) -> None:
    USER32.SendMessageW(handle, BM_CLICK, 0, 0)


def wait_for_top_window(title: str | None = None, class_filter: str | None = None, timeout: float = 5.0) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        handle = find_top_window(title=title, class_filter=class_filter)
        if handle:
            return handle
        time.sleep(0.1)
    raise SystemExit(f'No top-level window matched title={title!r} class={class_filter!r} within {timeout:.1f}s.')


def save_window_screenshot(window: TargetWindow, output: Path) -> None:
    import mss
    from PIL import Image

    region = {'left': window.left, 'top': window.top, 'width': window.width, 'height': window.height}
    with mss.mss() as sct:
        raw = sct.grab(region)
    image = Image.frombytes('RGB', raw.size, raw.rgb)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def wait_for_new_window(target_name: str, existing_handles: set[int], timeout: float = 5.0, pid: int | None = None) -> TargetWindow:
    deadline = time.time() + timeout
    while time.time() < deadline:
        windows = list_windows(target_name, pid=pid)
        for window in windows:
            if window.handle not in existing_handles:
                return window
        time.sleep(0.1)
    raise SystemExit(f'No new {target_name!r} window appeared within {timeout:.1f}s.')


def wait_for_window_title_change(handle: int, previous_title: str, timeout: float = 5.0) -> TargetWindow:
    deadline = time.time() + timeout
    while time.time() < deadline:
        current = window_by_handle(handle)
        if current and current.title != previous_title:
            return current
        time.sleep(0.1)
    raise SystemExit(f'Window 0x{handle:X} did not change title within {timeout:.1f}s.')


def drop_files(handle: int, paths: list[str | Path]) -> None:
    normalized = [str(Path(path)) for path in paths]
    payload = '\0'.join(normalized) + '\0\0'
    encoded = payload.encode('utf-16le')
    dropfiles = DROPFILES()
    dropfiles.pFiles = ctypes.sizeof(DROPFILES)
    dropfiles.pt = POINT(0, 0)
    dropfiles.fNC = False
    dropfiles.fWide = True
    total_size = ctypes.sizeof(DROPFILES) + len(encoded)
    hglobal = KERNEL32.GlobalAlloc(GHND, total_size)
    if not hglobal:
        raise MemoryError('GlobalAlloc failed for WM_DROPFILES payload.')
    pointer = KERNEL32.GlobalLock(hglobal)
    if not pointer:
        KERNEL32.GlobalFree(hglobal)
        raise MemoryError('GlobalLock failed for WM_DROPFILES payload.')
    try:
        ctypes.memmove(pointer, ctypes.byref(dropfiles), ctypes.sizeof(DROPFILES))
        ctypes.memmove(pointer + ctypes.sizeof(DROPFILES), encoded, len(encoded))
    finally:
        KERNEL32.GlobalUnlock(hglobal)
    USER32.PostMessageW(handle, WM_DROPFILES, hglobal, 0)


def set_clipboard_text(text: str) -> None:
    USER32.OpenClipboard(None)
    try:
        USER32.EmptyClipboard()
        encoded = (text + '\0').encode('utf-16le')
        hglobal = KERNEL32.GlobalAlloc(GHND, len(encoded))
        if not hglobal:
            raise MemoryError('GlobalAlloc failed for clipboard text.')
        pointer = KERNEL32.GlobalLock(hglobal)
        if not pointer:
            KERNEL32.GlobalFree(hglobal)
            raise MemoryError('GlobalLock failed for clipboard text.')
        try:
            ctypes.memmove(pointer, encoded, len(encoded))
        finally:
            KERNEL32.GlobalUnlock(hglobal)
        if not USER32.SetClipboardData(CF_UNICODETEXT, hglobal):
            KERNEL32.GlobalFree(hglobal)
            raise OSError('SetClipboardData failed for clipboard text.')
    finally:
        USER32.CloseClipboard()


def print_windows(windows: list[TargetWindow]) -> None:
    if not windows:
        print('No matching windows found.')
        return
    for item in windows:
        print(f"handle=0x{item.handle:X} title={item.title!r} class={item.class_name!r} rect=({item.left},{item.top})-({item.right},{item.bottom}) size={item.width}x{item.height}")


def launch_targets(mgba: Path | None, state: Path | None, rom: Path | None, pkhex: Path | None, wait: float):
    launched = []
    if mgba:
        cmd = [str(mgba)]
        if state:
            cmd.extend(['-t', str(state)])
        if rom:
            cmd.append(str(rom))
        launched.append(('mGBA', cmd, subprocess.Popen(cmd)))
    if pkhex:
        cmd = [str(pkhex)]
        launched.append(('PKHeX', cmd, subprocess.Popen(cmd)))
    time.sleep(wait)
    for label, cmd, proc in launched:
        print(f'launched {label}: pid={proc.pid} cmd={cmd}')
    return launched


def terminate_launched(launched) -> None:
    for _, _, proc in reversed(launched):
        try:
            proc.terminate()
        except Exception:
            pass


def load_mgba_keymap(config_path: Path) -> dict[str, int]:
    parser = configparser.ConfigParser()
    if not config_path.exists():
        raise SystemExit(f'mGBA config not found: {config_path}')
    parser.read(config_path, encoding='utf-8')
    if MGBA_QT_SECTION not in parser:
        raise SystemExit(f'mGBA config is missing section {MGBA_QT_SECTION!r}.')
    section = parser[MGBA_QT_SECTION]
    mapping: dict[str, int] = {}
    for token, key_name in BUTTON_ALIASES.items():
        raw_value = section.get(f'key{key_name}')
        if raw_value is None:
            raise SystemExit(f'mGBA config is missing key{key_name}.')
        qt_code = int(raw_value)
        if qt_code in QT_SPECIAL_TO_VK:
            mapping[token] = QT_SPECIAL_TO_VK[qt_code]
        elif 32 <= qt_code <= 126:
            mapping[token] = qt_code
        else:
            raise SystemExit(f'Unsupported Qt key code for {token}: {qt_code}')
    return mapping


def post_key(handle: int, vk_code: int, hold: float) -> None:
    USER32.PostMessageW(handle, WM_KEYDOWN, vk_code, 0)
    time.sleep(hold)
    USER32.PostMessageW(handle, WM_KEYUP, vk_code, 0)


def post_key_down(handle: int, vk_code: int) -> None:
    USER32.PostMessageW(handle, WM_KEYDOWN, vk_code, 0)


def post_key_up(handle: int, vk_code: int) -> None:
    USER32.PostMessageW(handle, WM_KEYUP, vk_code, 0)


def post_combo(handle: int, vk_codes: list[int], hold: float = 0.05, stagger: float = 0.02) -> None:
    for vk_code in vk_codes:
        post_key_down(handle, vk_code)
        time.sleep(stagger)
    time.sleep(hold)
    for vk_code in reversed(vk_codes):
        post_key_up(handle, vk_code)
        time.sleep(stagger)


def hotkey(*keys: str) -> None:
    vk_codes = []
    for key in keys:
        normalized = key.lower()
        if normalized in HOST_HOTKEYS:
            vk_codes.append(HOST_HOTKEYS[normalized])
            continue
        if len(normalized) == 1 and normalized.isalnum():
            vk_codes.append(ord(normalized.upper()))
            continue
        raise KeyError(normalized)
    for vk in vk_codes:
        USER32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.03)
    time.sleep(0.05)
    for vk in reversed(vk_codes):
        USER32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.03)


def post_hotkey(handle: int, *keys: str, hold: float = 0.05, stagger: float = 0.03) -> None:
    vk_codes = []
    for key in keys:
        normalized = key.lower()
        if normalized in HOST_HOTKEYS:
            vk_codes.append(HOST_HOTKEYS[normalized])
            continue
        if len(normalized) == 1 and normalized.isalnum():
            vk_codes.append(ord(normalized.upper()))
            continue
        raise KeyError(normalized)
    for vk in vk_codes:
        post_key_down(handle, vk)
        time.sleep(stagger)
    time.sleep(hold)
    for vk in reversed(vk_codes):
        post_key_up(handle, vk)
        time.sleep(stagger)


def relative_click(window: TargetWindow, x: int, y: int, button: str = 'left') -> None:
    raise NotImplementedError('relative_click is not used in the current local harness.')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Minimal local GUI harness for mGBA and PKHeX.')
    sub = parser.add_subparsers(dest='cmd', required=True)

    probe = sub.add_parser('probe')
    probe.add_argument('--target', choices=tuple(TARGET_FILTERS))

    launch = sub.add_parser('launch')
    launch.add_argument('--mgba', type=Path)
    launch.add_argument('--state', type=Path)
    launch.add_argument('--rom', type=Path)
    launch.add_argument('--pkhex', type=Path)
    launch.add_argument('--wait', type=float, default=3.0)

    tile = sub.add_parser('tile')
    tile.add_argument('target', choices=tuple(TARGET_FILTERS))
    tile.add_argument('--pid', type=int)
    tile.add_argument('--index', type=int, required=True)
    tile.add_argument('--count', type=int, required=True)
    tile.add_argument('--padding', type=int, default=12)

    menu = sub.add_parser('menu')
    menu.add_argument('target', choices=tuple(TARGET_FILTERS))
    menu.add_argument('--pid', type=int)

    invoke = sub.add_parser('invoke')
    invoke.add_argument('target', choices=tuple(TARGET_FILTERS))
    invoke.add_argument('pattern')
    invoke.add_argument('--pid', type=int)
    invoke.add_argument('--exact', action='store_true')

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd == 'probe':
        if args.target:
            print_windows(list_windows(args.target))
        else:
            rows = []
            for name in TARGET_FILTERS:
                rows.extend(list_windows(name))
            print_windows(rows)
        return 0
    if args.cmd == 'launch':
        launch_targets(args.mgba, args.state, args.rom, args.pkhex, args.wait)
        return 0
    if args.cmd == 'tile':
        window = tile_window(args.target, args.index, args.count, pid=args.pid, padding=args.padding)
        print_windows([window])
        return 0
    if args.cmd == 'menu':
        window = pick_window(args.target, pid=args.pid)
        for item in list_menu_items(window.handle):
            path = ' > '.join(item.path)
            print(f'id={item.command_id} path={path}')
        return 0
    if args.cmd == 'invoke':
        window = pick_window(args.target, pid=args.pid)
        item = invoke_menu_item(window.handle, args.pattern, exact=args.exact)
        print(f'invoked id={item.command_id} path={" > ".join(item.path)}')
        return 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

