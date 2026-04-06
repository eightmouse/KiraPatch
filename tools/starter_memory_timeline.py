#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import gui_harness
from inspect_gen3_pk3 import NATURES, decode_string
from process_memory_gen3 import find_valid_named_mons_in_process
from starter_capture import (
    DEFAULT_CASES,
    DEFAULT_MGBA,
    load_cases,
    prepare_launch,
    resolve_capture_runtime,
    safe_focus,
    press_hotkey,
    press_soft_reset,
)


def parse_sample_times(raw: str) -> list[float]:
    values = []
    for part in raw.split(','):
        part = part.strip()
        if not part:
            continue
        values.append(float(part))
    if not values:
        raise ValueError('At least one sample time is required.')
    return values


def parse_mon(raw: bytes) -> dict[str, object]:
    pid = int.from_bytes(raw[0:4], 'little')
    otid = int.from_bytes(raw[4:8], 'little')
    tid = otid & 0xFFFF
    sid = (otid >> 16) & 0xFFFF
    shiny_xor = ((pid >> 16) ^ (pid & 0xFFFF) ^ tid ^ sid) & 0xFFFF
    return {
        'pid': f'0x{pid:08X}',
        'tid': tid,
        'sid': sid,
        'nickname': decode_string(raw[8:18]),
        'nature': NATURES[pid % 25],
        'level': raw[84],
        'shiny_xor': shiny_xor,
        'is_shiny': shiny_xor < 8,
    }


def run_input_sequence(window_handle: int, input_handle: int, keymap: dict[str, int], args, presses: int) -> float:
    safe_focus(window_handle)
    if args.fast_forward:
        press_hotkey('shift', 'tab')
    try:
        if args.reset_before_capture:
            safe_focus(window_handle)
            if args.reset_mode == 'soft':
                press_soft_reset(input_handle, keymap, args.hold)
            else:
                press_hotkey('control', 'r')
            time.sleep(args.reset_wait)

        pre_buttons = [part.strip().upper() for part in args.pre_buttons.split(',') if part.strip()]
        for button in pre_buttons:
            safe_focus(window_handle)
            gui_harness.post_key(input_handle, keymap[button], args.hold)
            time.sleep(args.press_interval)

        last_input_at = time.perf_counter()
        for _ in range(presses):
            safe_focus(window_handle)
            gui_harness.post_key(input_handle, keymap['A'], args.hold)
            last_input_at = time.perf_counter()
            time.sleep(args.press_interval)
        if getattr(args, 'post_wait', 0.0) > 0:
            time.sleep(args.post_wait)
        post_press_interval = getattr(args, 'post_press_interval', None) or args.press_interval
        post_buttons = [part.strip().upper() for part in getattr(args, 'post_buttons', '').split(',') if part.strip()]
        for button in post_buttons:
            safe_focus(window_handle)
            gui_harness.post_key(input_handle, keymap[button], args.hold)
            last_input_at = time.perf_counter()
            time.sleep(post_press_interval)
        for _ in range(getattr(args, 'post_presses', 0)):
            safe_focus(window_handle)
            gui_harness.post_key(input_handle, keymap['A'], args.hold)
            last_input_at = time.perf_counter()
            time.sleep(post_press_interval)
        return last_input_at
    finally:
        if args.fast_forward:
            safe_focus(window_handle)
            press_hotkey('shift', 'tab')


def main() -> int:
    parser = argparse.ArgumentParser(description='Sample live mGBA starter memory after the final scripted input.')
    parser.add_argument('case', choices=('firered', 'leafgreen', 'ruby', 'sapphire', 'emerald'))
    parser.add_argument('--cases', type=Path, default=DEFAULT_CASES)
    parser.add_argument('--mgba', type=Path, default=DEFAULT_MGBA)
    parser.add_argument('--rom', type=Path, help='Override ROM path')
    parser.add_argument('--save', type=Path, help='Override in-game .sav path')
    parser.add_argument('--launch-wait', type=float, default=6.0)
    parser.add_argument('--press-interval', type=float, default=None)
    parser.add_argument('--settle-wait', type=float, default=None)
    parser.add_argument('--presses', type=int)
    parser.add_argument('--fast-forward', action='store_true', default=True)
    parser.add_argument('--no-fast-forward', dest='fast_forward', action='store_false')
    parser.add_argument('--hold', type=float, default=0.05)
    parser.add_argument('--pre-buttons', default='')
    parser.add_argument('--post-wait', type=float, default=0.0)
    parser.add_argument('--post-buttons', default='')
    parser.add_argument('--post-presses', type=int, default=0)
    parser.add_argument('--post-press-interval', type=float, default=None)
    parser.add_argument('--sample-times', default='0.25,0.5,0.75,1.0,1.5,2.0')
    parser.add_argument('--output', type=Path, help='Optional JSON output path')
    parser.add_argument('--reset-before-capture', action='store_true')
    parser.add_argument('--reset-mode', choices=('host', 'soft'), default='host')
    parser.add_argument('--reset-wait', type=float, default=None)
    parser.add_argument('--unthrottled', action='store_true', default=None)
    parser.add_argument('--no-unthrottled', dest='unthrottled', action='store_false')
    args = parser.parse_args()

    cases = load_cases(args.cases)
    case_cfg = cases[args.case]
    rom = args.rom or (Path(__file__).resolve().parent.parent / Path(case_cfg['rom']))
    save_path = args.save or (Path(__file__).resolve().parent.parent / Path(case_cfg['save']))
    nickname = str(case_cfg['nickname'])
    presses, settled_wait, press_interval, reset_wait, unthrottled = resolve_capture_runtime(case_cfg, 'save', rom, args)
    args.settle_wait = settled_wait
    args.press_interval = press_interval
    args.reset_wait = reset_wait
    args.unthrottled = unthrottled
    args.attach_running = False
    args.entry = 'save'
    sample_times = parse_sample_times(args.sample_times)

    proc, source_desc = prepare_launch(args, case_cfg, rom, save_path, None)
    output: dict[str, object] = {
        'case': args.case,
        'rom': str(rom),
        'source_in': source_desc,
        'capture_presses': presses,
        'press_interval': args.press_interval,
        'reset_wait': args.reset_wait,
        'sample_times': sample_times,
        'nickname': nickname,
        'samples': [],
    }

    try:
        window = gui_harness.pick_window('mgba')
        input_wrapper = gui_harness.pick_input_wrapper('mgba')
        mgba_pid = gui_harness.get_window_pid(window.handle)
        keymap = gui_harness.load_mgba_keymap(gui_harness.MGBA_CONFIG)
        last_input_at = run_input_sequence(window.handle, input_wrapper.handle, keymap, args, presses)

        for sample_time in sample_times:
            target = last_input_at + sample_time
            while time.perf_counter() < target:
                time.sleep(0.01)
            matches = find_valid_named_mons_in_process(mgba_pid, nickname)
            parsed_matches = []
            for match in matches:
                mon = parse_mon(match.mon)
                mon['address'] = f'0x{match.absolute_address:016X}'
                parsed_matches.append(mon)
            output['samples'].append(
                {
                    'seconds_after_last_input': sample_time,
                    'match_count': len(parsed_matches),
                    'matches': parsed_matches,
                }
            )
    finally:
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass

    if args.output:
        args.output.write_text(json.dumps(output, indent=2), encoding='utf-8')
    print(json.dumps(output, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
