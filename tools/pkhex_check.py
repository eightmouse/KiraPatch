#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import ctypes
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path
from ctypes import wintypes
import struct

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import gui_harness

USER32 = ctypes.windll.user32
GDI32 = ctypes.windll.gdi32
SRCCOPY = 0x00CC0020
BI_RGB = 0
DIB_RGB_COLORS = 0
LEGALITY_REGION = (0, 48, 40, 92)
BLANK_PKHEX_TITLE_TOKENS = ('SAV9ZA-MD', 'Legends: Z-A')
BLANK_EDITOR_FIELDS = {'00000000', 'Gholdengo'}


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', wintypes.LONG),
        ('biHeight', wintypes.LONG),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', wintypes.LONG),
        ('biYPelsPerMeter', wintypes.LONG),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', wintypes.DWORD * 3)]


def find_main_window(pid: int, timeout: float):
    deadline = time.time() + timeout
    while time.time() < deadline:
        windows = gui_harness.list_windows('pkhex', pid=pid)
        if not windows:
            windows = gui_harness.list_windows(pid=pid)
        if windows:
            preferred = [window for window in windows if 'pkhex' in window.title.lower()]
            target = preferred if preferred else windows
            target.sort(key=lambda item: len(item.title), reverse=True)
            return target[0]
        time.sleep(0.25)
    raise RuntimeError(f'Timed out waiting for PKHeX window (pid={pid}).')


def capture_screen_region(left: int, top: int, width: int, height: int) -> tuple[int, int, bytes]:
    hdc = USER32.GetDC(0)
    memdc = GDI32.CreateCompatibleDC(hdc)
    bitmap = GDI32.CreateCompatibleBitmap(hdc, width, height)
    old_bitmap = GDI32.SelectObject(memdc, bitmap)
    GDI32.BitBlt(memdc, 0, 0, width, height, hdc, left, top, SRCCOPY)

    bmi = BITMAPINFO()
    bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.bmiHeader.biWidth = width
    bmi.bmiHeader.biHeight = -height
    bmi.bmiHeader.biPlanes = 1
    bmi.bmiHeader.biBitCount = 32
    bmi.bmiHeader.biCompression = BI_RGB

    buffer = ctypes.create_string_buffer(width * height * 4)
    GDI32.GetDIBits(memdc, bitmap, 0, height, buffer, ctypes.byref(bmi), DIB_RGB_COLORS)

    GDI32.SelectObject(memdc, old_bitmap)
    GDI32.DeleteObject(bitmap)
    GDI32.DeleteDC(memdc)
    USER32.ReleaseDC(0, hdc)

    rgb = bytearray()
    raw = buffer.raw
    for offset in range(0, len(raw), 4):
        b = raw[offset]
        g = raw[offset + 1]
        r = raw[offset + 2]
        rgb.extend((r, g, b))
    return width, height, bytes(rgb)


def capture_region(window):
    left, top, right, bottom = LEGALITY_REGION
    return capture_screen_region(window.left + left, window.top + top, right - left, bottom - top)


def write_bmp(path: Path, capture: tuple[int, int, bytes]) -> None:
    width, height, rgb = capture
    row_stride = (width * 3 + 3) & ~3
    pixel_data = bytearray()
    for row in range(height - 1, -1, -1):
        start = row * width * 3
        row_rgb = rgb[start:start + width * 3]
        row_bgr = bytearray()
        for offset in range(0, len(row_rgb), 3):
            r = row_rgb[offset]
            g = row_rgb[offset + 1]
            b = row_rgb[offset + 2]
            row_bgr.extend((b, g, r))
        padding = row_stride - len(row_bgr)
        if padding > 0:
            row_bgr.extend(b'\x00' * padding)
        pixel_data.extend(row_bgr)

    file_size = 14 + 40 + len(pixel_data)
    header = struct.pack('<2sIHHI', b'BM', file_size, 0, 0, 54)
    dib = struct.pack(
        '<IIIHHIIIIII',
        40,
        width,
        height,
        1,
        24,
        0,
        len(pixel_data),
        2835,
        2835,
        0,
        0,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + dib + pixel_data)


def icon_stats(capture: tuple[int, int, bytes]) -> dict[str, int]:
    width, height, rgb = capture
    green = 0
    red = 0
    colored = 0
    for offset in range(0, len(rgb), 3):
        r = rgb[offset]
        g = rgb[offset + 1]
        b = rgb[offset + 2]
        if max(r, g, b) < 40:
            continue
        if min(r, g, b) > 235:
            continue
        colored += 1
        if g >= 90 and g > r + 20 and g > b + 10:
            green += 1
        if r >= 110 and r > g + 20 and r > b + 10:
            red += 1
    return {
        'width': width,
        'height': height,
        'colored_pixels': colored,
        'green_pixels': green,
        'red_pixels': red,
    }


def status_from_icon(stats: dict[str, int]) -> str:
    green = stats['green_pixels']
    red = stats['red_pixels']
    if green >= max(8, red * 2):
        return 'legal'
    if red >= max(8, green * 2):
        return 'invalid'
    return 'unknown'


def collect_editor_edits(window) -> list[str]:
    values: list[str] = []
    for child in gui_harness.enum_child_windows(window.handle):
        cls = gui_harness.class_name(child)
        if not cls.startswith('WindowsForms10.Edit'):
            continue
        text = gui_harness.window_text(child).strip()
        if text:
            values.append(text)
    return values


def infer_load_status(window_title: str, edit_values: list[str]) -> str:
    if any(token in window_title for token in BLANK_PKHEX_TITLE_TOKENS):
        if BLANK_EDITOR_FIELDS.issubset(set(edit_values)):
            return 'load_failed'
    return 'loaded'


def prepare_pkhex_cfg(pkhex_path: Path) -> tuple[Path | None, str | None]:
    cfg_path = pkhex_path.with_name('cfg.json')
    if not cfg_path.exists():
        return None, None
    try:
        original_text = cfg_path.read_text(encoding='utf-8')
        payload = json.loads(original_text)
    except Exception:
        return cfg_path, None

    startup = payload.setdefault('Startup', {})
    changed = False
    if startup.get('TryDetectRecentSave', True):
        startup['TryDetectRecentSave'] = False
        changed = True
    if startup.get('AutoLoadSaveOnStartup', 0) != 0:
        startup['AutoLoadSaveOnStartup'] = 0
        changed = True
    if startup.get('PluginLoadEnable', True):
        startup['PluginLoadEnable'] = False
        changed = True
    if not startup.get('SkipSplashScreen', False):
        startup['SkipSplashScreen'] = True
        changed = True

    if changed:
        cfg_path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return cfg_path, original_text


def restore_pkhex_cfg(cfg_path: Path | None, original_text: str | None) -> None:
    if cfg_path is None or original_text is None:
        return
    try:
        cfg_path.write_text(original_text, encoding='utf-8')
    except Exception:
        pass


def stage_pkhex_runtime(pkhex_path: Path) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    tempdir = tempfile.TemporaryDirectory(prefix='pkhex_check_')
    staged_dir = Path(tempdir.name)
    staged_exe = staged_dir / pkhex_path.name
    shutil.copy2(pkhex_path, staged_exe)
    cfg_path = pkhex_path.with_name('cfg.json')
    if cfg_path.exists():
        shutil.copy2(cfg_path, staged_dir / cfg_path.name)
    return tempdir, staged_exe


def sample_pkhex_launch(staged_pkhex: Path, target_file: Path, args) -> dict[str, object]:
    proc = subprocess.Popen([str(staged_pkhex), str(target_file)], cwd=staged_pkhex.parent)
    try:
        window = find_main_window(proc.pid, args.wait)
        gui_harness.activate_handle(window.handle)
        # PKHeX sometimes paints the legality sidebar a bit later than the
        # editor fields for standalone Gen 3 files, so give the window a moment
        # to settle before sampling the icon.
        time.sleep(0.8)
        edit_values = collect_editor_edits(window)
        load_status = infer_load_status(window.title, edit_values)
        def collect_icon_samples() -> list[dict[str, object]]:
            results = []
            for _ in range(max(1, args.retries)):
                capture = capture_region(window)
                stats = icon_stats(capture)
                status = status_from_icon(stats)
                results.append({'icon': stats, 'status': status})
                time.sleep(args.retry_interval)
            return results

        samples = collect_icon_samples()
        if load_status == 'loaded' and all(sample['status'] == 'unknown' for sample in samples):
            gui_harness.activate_handle(window.handle)
            time.sleep(0.8)
            samples = collect_icon_samples()
        capture = capture_region(window)
        if args.icon_output:
            write_bmp(args.icon_output, capture)
        statuses = [sample['status'] for sample in samples]
        counts = Counter(statuses)
        status = 'unknown'
        if counts.get('legal', 0) >= 1 and counts.get('invalid', 0) == 0:
            status = 'legal'
        elif counts.get('invalid', 0) >= 1 and counts.get('legal', 0) == 0:
            status = 'invalid'
        elif counts.get('legal', 0) > counts.get('invalid', 0):
            status = 'legal'
        elif counts.get('invalid', 0) > counts.get('legal', 0):
            status = 'invalid'
        if load_status != 'loaded':
            status = load_status
        return {
            'file': str(args.file),
            'window_title': window.title,
            'load_status': load_status,
            'editor_edits': edit_values[:12],
            'icon': samples[-1]['icon'],
            'icon_samples': samples,
            'tooltips': [],
            'dialog': None,
            'report': None,
            'status': status,
            'icon_status': status if status in {'legal', 'invalid'} else 'unknown',
            'text_status': 'unknown',
        }
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
                proc.wait(timeout=5)
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description='Launch PKHeX with a file and return a structured legality verdict.')
    parser.add_argument('--pkhex', type=Path, required=True)
    parser.add_argument('--file', type=Path, required=True)
    parser.add_argument('--wait', type=float, default=8.0)
    parser.add_argument('--retries', type=int, default=4, help='Number of icon samples to collect before deciding')
    parser.add_argument('--retry-interval', type=float, default=0.35, help='Seconds between icon samples')
    parser.add_argument('--launch-retries', type=int, default=3, help='How many times to relaunch PKHeX if it boots to a blank save instead of loading the target file')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--icon-output', type=Path)
    args = parser.parse_args()

    tempdir: tempfile.TemporaryDirectory[str] | None = None
    staged_pkhex = args.pkhex
    runtime_mode = 'in_place'
    try:
        tempdir, staged_pkhex = stage_pkhex_runtime(args.pkhex)
        runtime_mode = 'staged_copy'
    except OSError:
        tempdir = None
        staged_pkhex = args.pkhex
        runtime_mode = 'in_place'
    target_file = args.file.resolve()
    cfg_path, original_cfg = prepare_pkhex_cfg(staged_pkhex)
    try:
        result: dict[str, object] | None = None
        for attempt in range(max(1, args.launch_retries)):
            result = sample_pkhex_launch(staged_pkhex, target_file, args)
            if result.get('load_status') == 'loaded':
                break
            if attempt + 1 < max(1, args.launch_retries):
                time.sleep(0.5)
        if result is None:
            raise RuntimeError('PKHeX sampling did not produce a result.')
        result['runtime_mode'] = runtime_mode
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result, indent=2))
        return 0
    finally:
        restore_pkhex_cfg(cfg_path, original_cfg)
        if tempdir is not None:
            try:
                tempdir.cleanup()
            except Exception:
                pass


if __name__ == '__main__':
    raise SystemExit(main())
