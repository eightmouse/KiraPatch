#!/usr/bin/env python3
from __future__ import annotations

import argparse
import configparser
import ctypes
import importlib
import json
import re
import shutil
import site
import subprocess
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENDOR_SITE = REPO_ROOT / '.vendor'
if str(VENDOR_SITE) not in sys.path:
    sys.path.insert(0, str(VENDOR_SITE))
USER_SITE = site.getusersitepackages()
if USER_SITE and USER_SITE not in sys.path:
    sys.path.append(USER_SITE)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import gui_harness
from extract_gen3_party_from_state import (
    decrypt_gen3_box_data,
    encode_name,
    find_valid_named_mons,
    get_gen3_species,
    load_state_blob,
)
from process_memory_gen3 import find_party_mons_in_process, find_valid_named_mons_in_process

DEFAULT_CASES = REPO_ROOT / 'tools' / 'starter_cases.json'
DEFAULT_MGBA = REPO_ROOT / 'tools' / 'mGBA-0.10.5-win64' / 'mGBA.exe'
DEFAULT_PRESS_INTERVAL = 0.6
DEFAULT_RESET_WAIT = 3.0
DEFAULT_MEMORY_RETRY_TIMEOUT = 2.0
DEFAULT_MEMORY_RETRY_INTERVAL = 0.1
DEFAULT_UNTHROTTLED = True
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
USER32 = ctypes.windll.user32
GDI32 = ctypes.windll.gdi32
GAME_CODE_BY_CASE = {
    'firered': 'BPRE',
    'leafgreen': 'BPGE',
    'ruby': 'AXVE',
    'sapphire': 'AXPE',
    'emerald': 'BPEE',
}
EXPECTED_SPECIES_BY_NICKNAME = {
    'BULBASAUR': 1,
    'SQUIRTLE': 7,
    'TORCHIC': 255,
}
METHOD1_BLOCK_ORDERS = (
    'GAEM', 'GAME', 'GEAM', 'GEMA', 'GMAE', 'GMEA',
    'AGEM', 'AGME', 'AEGM', 'AEMG', 'AMGE', 'AMEG',
    'EGAM', 'EGMA', 'EAGM', 'EAMG', 'EMGA', 'EMAG',
    'MGAE', 'MGEA', 'MAGE', 'MAEG', 'MEGA', 'MEAG',
)
METHOD1_BLOCK_LABELS = {'G': 'growth', 'A': 'attacks', 'E': 'evs', 'M': 'misc'}
METHOD1_LCRNG_MULT = 0x41C64E6D
METHOD1_LCRNG_ADD = 0x6073


@dataclass
class MemoryMonCandidate:
    absolute_address: int
    mon: bytes
    source: str


def load_cases(path: Path) -> dict[str, dict[str, object]]:
    return json.loads(path.read_text(encoding='utf-8'))


def resolve_odds_profile(case_cfg: dict[str, object], entry: str, rom: Path) -> dict[str, object]:
    profiles_key = 'save_profiles' if entry == 'save' else 'state_profiles'
    profiles = case_cfg.get(profiles_key, {})
    if not isinstance(profiles, dict):
        return {}
    stem = rom.stem.lower()
    marker = '_1in'
    if marker not in stem:
        match = re.search(r'(?:^|[_-])(fr|lg|ruby|sapphire|emerald)(64|128|256)(?:[_-]|$)', stem)
        if not match:
            return {}
        profile_key = match.group(2)
    else:
        suffix = stem.split(marker, 1)[1]
        digits = []
        for char in suffix:
            if char.isdigit():
                digits.append(char)
            else:
                break
        if not digits:
            return {}
        profile_key = ''.join(digits)
    odds_profile = profiles.get(profile_key, {}) or {}
    return odds_profile if isinstance(odds_profile, dict) else {}


def resolve_capture_runtime(case_cfg: dict[str, object], entry: str, rom: Path, args) -> tuple[int, float, float, float, bool]:
    default_press_key = 'save_capture_presses' if entry == 'save' else 'capture_presses'
    odds_profile = resolve_odds_profile(case_cfg, entry, rom)
    presses = args.presses if args.presses is not None else int(odds_profile.get('presses', case_cfg[default_press_key]))
    settle_wait = args.settle_wait if args.settle_wait is not None else float(odds_profile.get('settle_wait', 0.0))
    press_interval = args.press_interval if args.press_interval is not None else float(odds_profile.get('press_interval', case_cfg.get(f'{entry}_press_interval', DEFAULT_PRESS_INTERVAL)))
    reset_wait = args.reset_wait if args.reset_wait is not None else float(odds_profile.get('reset_wait', case_cfg.get(f'{entry}_reset_wait', DEFAULT_RESET_WAIT)))
    unthrottled = args.unthrottled if args.unthrottled is not None else bool(odds_profile.get('unthrottled', case_cfg.get(f'{entry}_unthrottled', DEFAULT_UNTHROTTLED)))
    return presses, settle_wait, press_interval, reset_wait, unthrottled


def write_matches(matches: list[MemoryMonCandidate], out_dir: Path, nickname: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for index, candidate in enumerate(matches, start=1):
        mon = candidate.mon
        pid = int.from_bytes(mon[0:4], 'little')
        out_path = out_dir / (
            f'{index:02d}_{nickname.upper()}_0x{pid:08X}_{candidate.source}_0x{candidate.absolute_address:08X}.pk3'
        )
        out_path.write_bytes(mon)
        written.append(out_path)
    return written


def safe_focus(handle: int) -> None:
    try:
        gui_harness.activate_handle(handle)
    except Exception:
        pass


def import_without_vendor(module_name: str):
    vendor_path = str(VENDOR_SITE)
    removed = False
    if vendor_path in sys.path:
        sys.path.remove(vendor_path)
        removed = True
    try:
        sys.modules.pop(module_name, None)
        return importlib.import_module(module_name)
    finally:
        if removed:
            sys.path.insert(0, vendor_path)


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ('biSize', wintypes.DWORD),
        ('biWidth', ctypes.c_long),
        ('biHeight', ctypes.c_long),
        ('biPlanes', wintypes.WORD),
        ('biBitCount', wintypes.WORD),
        ('biCompression', wintypes.DWORD),
        ('biSizeImage', wintypes.DWORD),
        ('biXPelsPerMeter', ctypes.c_long),
        ('biYPelsPerMeter', ctypes.c_long),
        ('biClrUsed', wintypes.DWORD),
        ('biClrImportant', wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [
        ('bmiHeader', BITMAPINFOHEADER),
        ('bmiColors', wintypes.DWORD * 3),
    ]


def capture_screen_region_rgb(left: int, top: int, width: int, height: int) -> bytes:
    screen_dc = USER32.GetDC(0)
    if not screen_dc:
        raise OSError('GetDC failed for adaptive naming capture.')
    memory_dc = GDI32.CreateCompatibleDC(screen_dc)
    bitmap = GDI32.CreateCompatibleBitmap(screen_dc, width, height)
    if not memory_dc or not bitmap:
        if bitmap:
            GDI32.DeleteObject(bitmap)
        if memory_dc:
            GDI32.DeleteDC(memory_dc)
        USER32.ReleaseDC(0, screen_dc)
        raise OSError('CreateCompatibleDC/CreateCompatibleBitmap failed for adaptive naming capture.')
    old_obj = GDI32.SelectObject(memory_dc, bitmap)
    try:
        if not GDI32.BitBlt(memory_dc, 0, 0, width, height, screen_dc, left, top, SRCCOPY):
            raise OSError('BitBlt failed for adaptive naming capture.')
        bitmap_info = BITMAPINFO()
        bitmap_info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bitmap_info.bmiHeader.biWidth = width
        bitmap_info.bmiHeader.biHeight = -height
        bitmap_info.bmiHeader.biPlanes = 1
        bitmap_info.bmiHeader.biBitCount = 32
        bitmap_info.bmiHeader.biCompression = 0
        buffer = ctypes.create_string_buffer(width * height * 4)
        rows = GDI32.GetDIBits(
            memory_dc,
            bitmap,
            0,
            height,
            buffer,
            ctypes.byref(bitmap_info),
            DIB_RGB_COLORS,
        )
        if rows != height:
            raise OSError('GetDIBits failed for adaptive naming capture.')
        bgra = buffer.raw
        rgb = bytearray(width * height * 3)
        out_index = 0
        for index in range(0, len(bgra), 4):
            rgb[out_index] = bgra[index + 2]
            rgb[out_index + 1] = bgra[index + 1]
            rgb[out_index + 2] = bgra[index]
            out_index += 3
        return bytes(rgb)
    finally:
        if old_obj:
            GDI32.SelectObject(memory_dc, old_obj)
        GDI32.DeleteObject(bitmap)
        GDI32.DeleteDC(memory_dc)
        USER32.ReleaseDC(0, screen_dc)


def press_hotkey(*keys: str, handle: int | None = None) -> None:
    if handle is not None:
        gui_harness.post_hotkey(handle, *keys)
    else:
        gui_harness.hotkey(*keys)
    time.sleep(0.2)


def capture_lower_center_stats(window_handle: int) -> tuple[float, int, int]:
    window = gui_harness.window_by_handle(window_handle)
    if window is None:
        raise SystemExit(f'Unable to locate window 0x{window_handle:X} for adaptive naming detection.')
    left = window.left + (window.width // 4)
    top = window.top + (window.height // 2)
    width = max(1, window.width // 2)
    height = max(1, window.height // 2)
    region = {'left': left, 'top': top, 'width': width, 'height': height}
    rgb: bytes
    try:
        mss = import_without_vendor('mss')

        with mss.mss() as sct:
            raw = sct.grab(region)
        rgb = raw.rgb
    except (ImportError, PermissionError, OSError):
        try:
            image_grab = import_without_vendor('PIL.ImageGrab')
            screenshot = image_grab.grab(bbox=(left, top, left + width, top + height))
            rgb = screenshot.convert('RGB').tobytes()
        except (ImportError, PermissionError, OSError):
            rgb = capture_screen_region_rgb(left, top, width, height)
    total = 0
    bright = 0
    dark = 0
    pixel_count = max(1, width * height)
    for index in range(0, len(rgb), 3):
        pixel_sum = rgb[index] + rgb[index + 1] + rgb[index + 2]
        total += pixel_sum
        if pixel_sum >= 600:
            bright += 1
        elif pixel_sum < 300:
            dark += 1
    return (total / pixel_count), bright, dark


def measure_firered_naming_state(window_handle: int) -> tuple[str, float, int, int]:
    mean_sum, bright, dark = capture_lower_center_stats(window_handle)
    if mean_sum < 100 and dark > 30000:
        return 'pre', mean_sum, bright, dark
    if bright >= 4000:
        return 'confirm', mean_sum, bright, dark
    if bright >= 500:
        return 'keyboard', mean_sum, bright, dark
    return 'prompt', mean_sum, bright, dark


def press_soft_reset(input_handle: int, keymap: dict[str, int], hold: float) -> None:
    gui_harness.post_combo(
        input_handle,
        [keymap['A'], keymap['B'], keymap['START'], keymap['SELECT']],
        hold=max(hold, 0.08),
        stagger=0.02,
    )
    time.sleep(0.2)


def filter_named_matches(blob: bytes, nickname: str) -> list[tuple[int, bytes]]:
    target = encode_name(nickname)[:-1]
    matches = []
    for start, mon in find_valid_named_mons(blob, nickname):
        if mon[8:18].startswith(target) and 1 <= mon[84] <= 100:
            matches.append((start, mon))
    return matches


def is_method1_correlated(mon: bytes) -> bool:
    pid = int.from_bytes(mon[0:4], 'little')
    otid = int.from_bytes(mon[4:8], 'little')
    xor_key = pid ^ otid
    encrypted = mon[32:80]
    decrypted = bytearray()
    for offset in range(0, 48, 4):
        word = int.from_bytes(encrypted[offset:offset + 4], 'little') ^ xor_key
        decrypted.extend(word.to_bytes(4, 'little'))
    order = METHOD1_BLOCK_ORDERS[pid % 24]
    blocks: dict[str, bytes] = {}
    for index, label in enumerate(order):
        blocks[METHOD1_BLOCK_LABELS[label]] = bytes(decrypted[index * 12:(index + 1) * 12])
    iv_word = int.from_bytes(blocks['misc'][4:8], 'little') & 0x3FFFFFFF
    pid_hi = (pid >> 16) & 0xFFFF
    pid_lo = pid & 0xFFFF
    for output_1, output_2 in ((pid_hi, pid_lo), (pid_lo, pid_hi)):
        for low16 in range(0x10000):
            seed_1 = (output_1 << 16) | low16
            seed_2 = (seed_1 * METHOD1_LCRNG_MULT + METHOD1_LCRNG_ADD) & 0xFFFFFFFF
            if (seed_2 >> 16) != output_2:
                continue
            seed_3 = (seed_2 * METHOD1_LCRNG_MULT + METHOD1_LCRNG_ADD) & 0xFFFFFFFF
            seed_4 = (seed_3 * METHOD1_LCRNG_MULT + METHOD1_LCRNG_ADD) & 0xFFFFFFFF
            iv_high = (seed_3 >> 16) & 0xFFFF
            iv_low = (seed_4 >> 16) & 0xFFFF
            candidate = (
                (iv_high & 31)
                | (((iv_high >> 5) & 31) << 5)
                | (((iv_high >> 10) & 31) << 10)
                | ((iv_low & 31) << 15)
                | (((iv_low >> 5) & 31) << 20)
                | (((iv_low >> 10) & 31) << 25)
            )
            if candidate == iv_word:
                return True
    return False


def looks_like_clean_starter_candidate(mon: bytes, expected_species_id: int | None) -> bool:
    data = decrypt_gen3_box_data(mon)
    if data is None:
        return False
    species = int.from_bytes(data[0:2], 'little')
    if expected_species_id is not None and species != expected_species_id:
        return False
    attacks = data[12:24]
    evs = data[24:36]
    move_1 = int.from_bytes(attacks[0:2], 'little')
    move_2 = int.from_bytes(attacks[2:4], 'little')
    if move_1 == 0 and move_2 == 0:
        return False
    if any(evs):
        return False
    return True


def has_clean_nickname_tail(mon: bytes) -> bool:
    nickname = mon[8:18]
    try:
        terminator = nickname.index(0xFF)
    except ValueError:
        return False
    return all(value in (0x00, 0xFF) for value in nickname[terminator + 1 :])


def sort_memory_matches(matches: list[MemoryMonCandidate]) -> list[MemoryMonCandidate]:
    def key(candidate: MemoryMonCandidate) -> tuple[int, int]:
        # For FireRed starter captures, later generic copies have proven to be
        # the more reliable final-state candidates. Clean nickname padding is
        # a cheap way to demote obviously stale intermediate copies first.
        clean_tail = 1 if has_clean_nickname_tail(candidate.mon) else 0
        return (clean_tail, candidate.absolute_address)

    return sorted(matches, key=key, reverse=True)


def collect_memory_matches(
    pid: int,
    nickname: str,
    *,
    game_code: str | None = None,
    timeout_s: float,
    interval_s: float,
    stable_scans: int = 2,
    prefer_method1_generic: bool = False,
    wait_for_party_match: bool = False,
) -> list[MemoryMonCandidate]:
    deadline = time.perf_counter() + max(timeout_s, 0.0)
    required_stable_scans = max(stable_scans, 1)
    last_signature: tuple[tuple[int, int], ...] | None = None
    stable_count = 0
    last_matches: list[MemoryMonCandidate] = []
    expected_species_id = EXPECTED_SPECIES_BY_NICKNAME.get(nickname.upper())
    while True:
        generic_matches_map: dict[tuple[int, int], MemoryMonCandidate] = {}
        party_matches_map: dict[tuple[int, int], MemoryMonCandidate] = {}

        process_matches = find_valid_named_mons_in_process(pid, nickname)
        for match in process_matches:
            mon = match.mon
            key = (
                int.from_bytes(mon[0:4], 'little'),
                int.from_bytes(mon[4:8], 'little'),
            )
            generic_matches_map[key] = MemoryMonCandidate(
                absolute_address=match.absolute_address,
                mon=mon,
                source='generic',
            )

        if game_code is not None:
            target = encode_name(nickname)[:-1]
            for match in find_party_mons_in_process(pid, game_code, species_id=expected_species_id):
                mon = match.mon
                if not mon[8:18].startswith(target):
                    continue
                key = (
                    int.from_bytes(mon[0:4], 'little'),
                    int.from_bytes(mon[4:8], 'little'),
                )
                party_matches_map[key] = MemoryMonCandidate(
                    absolute_address=match.absolute_address,
                    mon=mon,
                    source='party',
                )

        raw_generic_matches = list(generic_matches_map.values())
        generic_matches = raw_generic_matches
        if expected_species_id is not None:
            generic_matches = [
                match for match in generic_matches
                if get_gen3_species(match.mon) == expected_species_id
            ]
        clean_party_matches = [
            match for match in party_matches_map.values()
            if looks_like_clean_starter_candidate(match.mon, expected_species_id)
        ]
        clean_generic_matches = [
            match for match in generic_matches
            if looks_like_clean_starter_candidate(match.mon, expected_species_id)
        ]
        method1_party_matches = [
            match for match in clean_party_matches
            if is_method1_correlated(match.mon)
        ]
        method1_generic_matches = [
            match for match in clean_generic_matches
            if is_method1_correlated(match.mon)
        ]
        has_any_party_match = bool(party_matches_map)
        if method1_party_matches:
            matches = method1_party_matches
        elif method1_generic_matches:
            matches = method1_generic_matches
        elif clean_party_matches:
            matches = clean_party_matches
        elif clean_generic_matches:
            matches = clean_generic_matches
        elif party_matches_map:
            matches = list(party_matches_map.values())
        elif generic_matches:
            matches = generic_matches
        else:
            matches = raw_generic_matches
        if matches:
            matches = sort_memory_matches(matches)
            if wait_for_party_match and not has_any_party_match:
                last_matches = matches
                if time.perf_counter() >= deadline:
                    return last_matches
                time.sleep(interval_s)
                continue
            if prefer_method1_generic and not method1_party_matches and not method1_generic_matches:
                last_matches = matches
                if time.perf_counter() >= deadline:
                    return last_matches
                time.sleep(interval_s)
                continue
            signature = tuple(
                sorted(
                    (
                        int.from_bytes(match.mon[0:4], 'little'),
                        int.from_bytes(match.mon[4:8], 'little'),
                    )
                    for match in matches
                )
            )
            if signature == last_signature:
                stable_count += 1
            else:
                last_signature = signature
                stable_count = 1
                last_matches = matches
            if stable_count >= required_stable_scans:
                return last_matches
        if time.perf_counter() >= deadline:
            return last_matches if last_matches else []
        time.sleep(interval_s)


def prepare_launch(args, case_cfg: dict[str, object], rom: Path, save_path: Path, state: Path) -> tuple[subprocess.Popen | None, str]:
    if args.attach_running:
        source_desc = f'attached-running:{args.mgba_pid if args.mgba_pid is not None else "latest"}'
        return None, source_desc

    launch_cmd = [str(args.mgba)]
    if args.entry == 'state':
        launch_cmd.extend(['-t', str(state), str(rom)])
        source_desc = str(state)
    else:
        if not save_path.exists():
            raise SystemExit(f'Expected save file was not found: {save_path}')
        target_save = rom.with_suffix('.sav')
        shutil.copyfile(save_path, target_save)
        launch_cmd.append(str(rom))
        source_desc = str(save_path)
    proc = subprocess.Popen(launch_cmd, cwd=REPO_ROOT)
    time.sleep(args.launch_wait)
    return proc, source_desc


def apply_unthrottled_config(config_path: Path) -> str | None:
    if not config_path.exists():
        return None
    original = config_path.read_text(encoding='utf-8')
    cfg = configparser.ConfigParser()
    cfg.optionxform = str
    cfg.read_string(original)
    section = 'ports.qt'
    if section not in cfg:
        cfg[section] = {}
    cfg[section]['audioSync'] = '0'
    cfg[section]['videoSync'] = '0'
    cfg[section]['frameskip'] = '0'
    with config_path.open('w', encoding='utf-8') as fh:
        cfg.write(fh)
    return original


def restore_config(config_path: Path, original: str | None) -> None:
    if original is None:
        return
    config_path.write_text(original, encoding='utf-8')


def run_capture_sequence(window_handle: int, input_handle: int, keymap: dict[str, int], args, presses: int, state_out: Path) -> tuple[float, float]:
    if state_out.exists():
        state_out.unlink()

    generation_latency_s = 0.0
    quicksave_write_latency_s = 0.0

    use_live_fast_forward = args.fast_forward and not args.unthrottled
    safe_focus(window_handle)
    if use_live_fast_forward:
        press_hotkey('shift', 'tab', handle=input_handle)
    try:
        if args.reset_before_capture:
            safe_focus(window_handle)
            if args.reset_mode == 'soft':
                press_soft_reset(input_handle, keymap, args.hold)
            else:
                press_hotkey('control', 'r', handle=input_handle)
            time.sleep(args.reset_wait)

        pre_buttons = [part.strip().upper() for part in args.pre_buttons.split(',') if part.strip()]
        for button in pre_buttons:
            safe_focus(window_handle)
            gui_harness.post_key(input_handle, keymap[button], args.hold)
            time.sleep(args.press_interval)

        post_press_interval = args.post_press_interval if args.post_press_interval is not None else args.press_interval
        post_buttons = [part.strip().upper() for part in args.post_buttons.split(',') if part.strip()]
        adaptive_keyboard_buttons = [
            part.strip().upper()
            for part in getattr(args, 'adaptive_naming_keyboard_buttons', '').split(',')
            if part.strip()
        ]
        adaptive_prompt_handled = False
        adaptive_min_presses = getattr(args, 'adaptive_naming_min_presses', None)
        adaptive_prompt_wait = getattr(args, 'adaptive_naming_prompt_wait', 0.0)
        adaptive_probe_delay = getattr(args, 'adaptive_naming_probe_delay', 0.15)
        last_input_at = time.perf_counter()
        for _ in range(presses):
            safe_focus(window_handle)
            gui_harness.post_key(input_handle, keymap['A'], args.hold)
            last_input_at = time.perf_counter()
            if adaptive_min_presses is not None and (_ + 1) >= adaptive_min_presses:
                if adaptive_probe_delay > 0:
                    time.sleep(adaptive_probe_delay)
                state, mean_sum, bright, dark = measure_firered_naming_state(window_handle)
                if state == 'pre':
                    remaining_wait = max(args.press_interval - max(adaptive_probe_delay, 0.0), 0.0)
                    if remaining_wait > 0:
                        time.sleep(remaining_wait)
                    continue
                buttons_to_send = post_buttons
                if state in ('keyboard', 'confirm'):
                    buttons_to_send = adaptive_keyboard_buttons or ['START']
                if adaptive_prompt_wait > 0:
                    time.sleep(adaptive_prompt_wait)
                for button in buttons_to_send:
                    safe_focus(window_handle)
                    gui_harness.post_key(input_handle, keymap[button], args.hold)
                    last_input_at = time.perf_counter()
                    time.sleep(post_press_interval)
                adaptive_prompt_handled = True
                break
            else:
                time.sleep(args.press_interval)
        if not adaptive_prompt_handled:
            if args.post_wait > 0:
                time.sleep(args.post_wait)
            for button in post_buttons:
                safe_focus(window_handle)
                gui_harness.post_key(input_handle, keymap[button], args.hold)
                last_input_at = time.perf_counter()
                time.sleep(post_press_interval)
        for _ in range(args.post_presses):
            safe_focus(window_handle)
            gui_harness.post_key(input_handle, keymap['A'], args.hold)
            last_input_at = time.perf_counter()
            time.sleep(post_press_interval)
        if args.settle_wait > 0:
            time.sleep(args.settle_wait)

        safe_focus(window_handle)
        quicksave_trigger_at = time.perf_counter()
        generation_latency_s = quicksave_trigger_at - last_input_at
        if args.extract_mode != 'memory':
            press_hotkey('shift', f'f{args.slot}')
            wait_start = time.perf_counter()
            deadline = wait_start + 5.0
            while time.perf_counter() < deadline:
                if state_out.exists():
                    quicksave_write_latency_s = time.perf_counter() - wait_start
                    break
                time.sleep(0.05)
    finally:
        if use_live_fast_forward:
            safe_focus(window_handle)
            press_hotkey('shift', 'tab', handle=input_handle)

    return generation_latency_s, quicksave_write_latency_s


def main() -> int:
    parser = argparse.ArgumentParser(description='Advance a starter entry point to a post-generation quick-save and extract the starter .pk3.')
    parser.add_argument('case', choices=('firered', 'leafgreen', 'ruby', 'sapphire', 'emerald'))
    parser.add_argument('--cases', type=Path, default=DEFAULT_CASES)
    parser.add_argument('--mgba', type=Path, default=DEFAULT_MGBA)
    parser.add_argument('--rom', type=Path, help='Override ROM path')
    parser.add_argument('--state', type=Path, help='Override savestate path')
    parser.add_argument('--save', type=Path, help='Override in-game .sav path')
    parser.add_argument('--entry', choices=('state', 'save'), default='state', help='Use a savestate debug entry point or a real .sav boot entry point')
    parser.add_argument('--launch-wait', type=float, default=3.0)
    parser.add_argument('--press-interval', type=float, default=None)
    parser.add_argument('--settle-wait', type=float, default=None, help='Extra wait after the scripted input sequence before quick-saving')
    parser.add_argument('--presses', type=int, help='Override the case default A-press count')
    parser.add_argument('--fast-forward', action='store_true', default=True)
    parser.add_argument('--no-fast-forward', dest='fast_forward', action='store_false')
    parser.add_argument('--hold', type=float, default=0.05)
    parser.add_argument('--slot', type=int, default=2, choices=range(1, 10))
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--nickname')
    parser.add_argument('--pre-buttons', default='')
    parser.add_argument('--post-wait', type=float, default=0.0, help='Extra wait after the main scripted presses before sending any post-confirmation A presses')
    parser.add_argument('--post-buttons', default='', help='Comma-separated buttons to send after post-wait and before any repeated post-confirmation A presses')
    parser.add_argument('--post-presses', type=int, default=0, help='Extra A presses to send after post-wait, for paths that only advance after generation settles')
    parser.add_argument('--post-press-interval', type=float, default=None, help='Spacing for post-confirmation A presses; defaults to --press-interval')
    parser.add_argument('--adaptive-naming-min-presses', type=int, default=None, help='Start FireRed naming-screen detection after this many A presses')
    parser.add_argument('--adaptive-naming-prompt-wait', type=float, default=0.0, help='Extra wait after FireRed naming-prompt detection before sending post buttons')
    parser.add_argument('--adaptive-naming-probe-delay', type=float, default=0.15, help='Delay after each checked A press before sampling the FireRed naming screen')
    parser.add_argument('--adaptive-naming-keyboard-buttons', default='', help='Comma-separated buttons to send if FireRed is already on the naming keyboard/confirm state')
    parser.add_argument('--attach-running', action='store_true', help='Attach to an already running mGBA instance instead of launching a new one')
    parser.add_argument('--mgba-pid', type=int, help='Restrict attachment to a specific mGBA process id')
    parser.add_argument('--reset-before-capture', action='store_true', help='Reset before the scripted button sequence when reusing mGBA')
    parser.add_argument('--reset-mode', choices=('host', 'soft'), default='host', help='Use host Ctrl+R or in-game A+B+Start+Select for reuse resets')
    parser.add_argument('--reset-wait', type=float, default=None, help='Seconds to wait after the reset before sending game input')
    parser.add_argument('--extract-mode', choices=('auto', 'state', 'memory'), default='auto', help='Prefer savestate extraction, process-memory extraction, or automatic fallback')
    parser.add_argument('--memory-retry-timeout', type=float, default=DEFAULT_MEMORY_RETRY_TIMEOUT, help='Seconds to keep retrying process-memory extraction after input completes')
    parser.add_argument('--memory-retry-interval', type=float, default=DEFAULT_MEMORY_RETRY_INTERVAL, help='Seconds between process-memory extraction retries')
    parser.add_argument('--wait-for-party-match', action='store_true', help='Keep scanning until a party-slot starter appears before falling back to generic named matches')
    parser.add_argument('--unthrottled', action='store_true', default=None, help='Temporarily disable sync limits in the local mGBA config during launched runs')
    parser.add_argument('--no-unthrottled', dest='unthrottled', action='store_false')
    args = parser.parse_args()

    cases = load_cases(args.cases)
    case_cfg = cases[args.case]
    rom = args.rom or (REPO_ROOT / Path(case_cfg['rom']))
    odds_profile = resolve_odds_profile(case_cfg, args.entry, rom)
    state = args.state or (REPO_ROOT / Path(case_cfg['state']))
    profile_save = odds_profile.get('save')
    save_path = args.save or (REPO_ROOT / Path(profile_save if profile_save is not None else case_cfg['save']))
    nickname = args.nickname or str(case_cfg['nickname'])
    presses, settled_wait, press_interval, reset_wait, unthrottled = resolve_capture_runtime(case_cfg, args.entry, rom, args)
    state_out = rom.with_suffix(f'.ss{args.slot}')
    args.settle_wait = settled_wait
    args.press_interval = press_interval
    args.reset_wait = reset_wait
    args.unthrottled = unthrottled
    if args.launch_wait == 3.0 and odds_profile.get('launch_wait') is not None:
        args.launch_wait = float(odds_profile['launch_wait'])
    if args.post_wait == 0.0 and odds_profile.get('post_wait') is not None:
        args.post_wait = float(odds_profile['post_wait'])
    if not args.post_buttons and odds_profile.get('post_buttons') is not None:
        args.post_buttons = str(odds_profile['post_buttons'])
    if args.post_presses == 0 and odds_profile.get('post_presses') is not None:
        args.post_presses = int(odds_profile['post_presses'])
    if args.post_press_interval is None and odds_profile.get('post_press_interval') is not None:
        args.post_press_interval = float(odds_profile['post_press_interval'])
    if args.adaptive_naming_min_presses is None and odds_profile.get('adaptive_naming_min_presses') is not None:
        args.adaptive_naming_min_presses = int(odds_profile['adaptive_naming_min_presses'])
    if args.adaptive_naming_prompt_wait == 0.0 and odds_profile.get('adaptive_naming_prompt_wait') is not None:
        args.adaptive_naming_prompt_wait = float(odds_profile['adaptive_naming_prompt_wait'])
    if args.adaptive_naming_probe_delay == 0.15 and odds_profile.get('adaptive_naming_probe_delay') is not None:
        args.adaptive_naming_probe_delay = float(odds_profile['adaptive_naming_probe_delay'])
    if not args.adaptive_naming_keyboard_buttons and odds_profile.get('adaptive_naming_keyboard_buttons') is not None:
        args.adaptive_naming_keyboard_buttons = str(odds_profile['adaptive_naming_keyboard_buttons'])
    if args.extract_mode == 'auto' and odds_profile.get('extract_mode') is not None:
        args.extract_mode = str(odds_profile['extract_mode'])
    if args.memory_retry_timeout == DEFAULT_MEMORY_RETRY_TIMEOUT and odds_profile.get('memory_retry_timeout') is not None:
        args.memory_retry_timeout = float(odds_profile['memory_retry_timeout'])
    if args.memory_retry_interval == DEFAULT_MEMORY_RETRY_INTERVAL and odds_profile.get('memory_retry_interval') is not None:
        args.memory_retry_interval = float(odds_profile['memory_retry_interval'])
    if not args.wait_for_party_match and odds_profile.get('wait_for_party_match') is not None:
        args.wait_for_party_match = bool(odds_profile['wait_for_party_match'])
    prefer_method1_generic = bool(odds_profile.get('prefer_method1_generic', case_cfg.get(f'{args.entry}_prefer_method1_generic', False)))

    original_mgba_config: str | None = None
    if args.unthrottled and not args.attach_running:
        original_mgba_config = apply_unthrottled_config(gui_harness.MGBA_CONFIG)
    proc, source_desc = prepare_launch(args, case_cfg, rom, save_path, state)
    generation_latency_s = 0.0
    quicksave_write_latency_s = 0.0
    expected_mgba_pid = args.mgba_pid if args.mgba_pid is not None else (proc.pid if proc is not None else None)
    mgba_pid = expected_mgba_pid
    selected_window_info: dict[str, object] | None = None
    try:
        window = gui_harness.pick_window('mgba', pid=expected_mgba_pid)
        input_wrapper = gui_harness.pick_input_wrapper('mgba', pid=expected_mgba_pid)
        mgba_pid = gui_harness.get_window_pid(window.handle)
        selected_window_info = {
            'window_title': window.title,
            'window_handle': window.handle,
            'input_handle': input_wrapper.handle,
            'mgba_pid': mgba_pid,
            'window_rect': (
                window.left,
                window.top,
                window.right,
                window.bottom,
            ),
        }
        keymap = gui_harness.load_mgba_keymap(gui_harness.MGBA_CONFIG)
        generation_latency_s, quicksave_write_latency_s = run_capture_sequence(window.handle, input_wrapper.handle, keymap, args, presses, state_out)

        out_dir = args.output_dir or (rom.parent / f'{rom.stem}_party')
        out_dir.mkdir(parents=True, exist_ok=True)
        extraction_source = None
        written: list[Path] = []

        if args.extract_mode in ('auto', 'state') and state_out.exists():
            blob = load_state_blob(state_out)
            matches = filter_named_matches(blob, nickname)
            if matches:
                written = write_matches(matches, out_dir, nickname)
                extraction_source = str(state_out)
        elif args.extract_mode == 'state':
            raise SystemExit(f'Expected quick-save was not created: {state_out}')

        if not written and args.extract_mode in ('auto', 'memory') and mgba_pid:
            memory_matches = collect_memory_matches(
                mgba_pid,
                nickname,
                game_code=GAME_CODE_BY_CASE.get(args.case),
                timeout_s=args.memory_retry_timeout,
                interval_s=args.memory_retry_interval,
                prefer_method1_generic=prefer_method1_generic,
                wait_for_party_match=args.wait_for_party_match,
            )
            if memory_matches:
                written = write_matches(memory_matches, out_dir, nickname)
                extraction_source = f'process:{mgba_pid}'
        elif not written and args.extract_mode == 'memory':
            raise SystemExit(f'No valid {nickname} mon structs found in process memory for pid {mgba_pid}.')

        if not written:
            if selected_window_info is not None:
                print(f"debug_window_title:{selected_window_info['window_title']}")
                print(f"debug_window_handle:{selected_window_info['window_handle']}")
                print(f"debug_input_handle:{selected_window_info['input_handle']}")
                print(f"debug_mgba_pid:{selected_window_info['mgba_pid']}")
                print(f"debug_window_rect:{selected_window_info['window_rect']}")
                print(f"debug_generation_latency_s:{generation_latency_s:.3f}")
                print(f"debug_quicksave_write_latency_s:{quicksave_write_latency_s:.3f}")
                print(f"debug_extract_mode:{args.extract_mode}")
            if state_out.exists():
                raise SystemExit(f'No valid {nickname} mon structs found in {state_out}.')
            if args.extract_mode == 'memory':
                raise SystemExit(f'No valid {nickname} mon structs found in process memory for pid {mgba_pid}.')
            if args.extract_mode == 'auto':
                raise SystemExit(f'No quick-save was created and no valid {nickname} mon structs were found in process memory for pid {mgba_pid}.')
            raise SystemExit(f'Expected quick-save was not created: {state_out}')

        print(f'case:       {args.case}')
        print(f'rom:        {rom}')
        print(f'entry:      {args.entry}')
        print(f'source_in:  {source_desc}')
        print(f'extract_from:{extraction_source}')
        print(f'state_out:  {state_out}')
        print(f'settle_wait:{args.settle_wait}')
        print(f'press_interval:{args.press_interval}')
        if args.post_wait > 0 or args.post_buttons or args.post_presses > 0:
            effective_post_press_interval = args.post_press_interval if args.post_press_interval is not None else args.press_interval
            print(f'post_wait:{args.post_wait}')
            print(f'post_buttons:{args.post_buttons}')
            print(f'post_presses:{args.post_presses}')
            print(f'post_press_interval:{effective_post_press_interval}')
        if args.reset_before_capture or args.attach_running:
            print(f'reset_wait:{args.reset_wait}')
        print(f'generation_latency_s:{generation_latency_s:.3f}')
        print(f'quicksave_write_latency_s:{quicksave_write_latency_s:.3f}')
        print(f'nickname:   {nickname}')
        print(f'matches:    {len(written)}')
        for path in written:
            print(f'  wrote {path}')
        return 0
    finally:
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
        restore_config(gui_harness.MGBA_CONFIG, original_mgba_config)


if __name__ == '__main__':
    raise SystemExit(main())
