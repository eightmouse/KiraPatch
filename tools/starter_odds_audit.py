#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from inspect_gen3_pk3 import parse_gen3_pk3
import gui_harness

REPO_ROOT = Path(__file__).resolve().parent.parent
PATCHER = REPO_ROOT / 'shiny_patcher.py'
CAPTURE = REPO_ROOT / 'tools' / 'starter_capture.py'
PKHEX_CHECK = REPO_ROOT / 'tools' / 'pkhex_check.py'
CASES = REPO_ROOT / 'tools' / 'starter_cases.json'
ARTIFACTS = REPO_ROOT / 'artifacts'
DEFAULT_PKHEX = Path.home() / 'Desktop' / 'PKHeX' / 'PKHeX.exe'
DEFAULT_MGBA = REPO_ROOT / 'tools' / 'mGBA-0.10.5-win64' / 'mGBA.exe'
DEFAULT_SAVE_REUSE_JITTER_MS = 17
DEFAULT_PRESS_INTERVAL = 0.6
DEFAULT_RESET_WAIT = 3.0
PKHEX_RECHECK_ATTEMPTS = (
    {'wait': 8.0, 'retries': 4, 'retry_interval': 0.35, 'launch_retries': 3},
    {'wait': 10.0, 'retries': 6, 'retry_interval': 0.5, 'launch_retries': 4},
    {'wait': 12.0, 'retries': 8, 'retry_interval': 0.65, 'launch_retries': 5},
)
DECISIVE_PKHEX_STATUSES = {'legal', 'invalid'}
ROM_BY_CASE = {
    'firered': REPO_ROOT / '.roms' / 'Pokemon - Fire Red.gba',
    'leafgreen': REPO_ROOT / '.roms' / 'Pokemon - Leaf Green.gba',
    'ruby': REPO_ROOT / '.roms' / 'Pokemon - Ruby.gba',
    'sapphire': REPO_ROOT / '.roms' / 'Pokemon - Sapphire.gba',
    'emerald': REPO_ROOT / '.roms' / 'Pokemon - Emerald.gba',
}


def load_cases() -> dict[str, dict[str, object]]:
    return json.loads(CASES.read_text(encoding='utf-8'))


def resolve_odds_profile(case_cfg: dict[str, object], entry: str, odds: int) -> dict[str, object]:
    profile_root_key = 'save_profiles' if entry == 'save' else 'state_profiles'
    profiles = case_cfg.get(profile_root_key, {})
    if not isinstance(profiles, dict):
        return {}
    odds_profile = profiles.get(str(odds), {}) or {}
    return odds_profile if isinstance(odds_profile, dict) else {}


def prefer_profile_value(arg_value, default_value, profile_value):
    if profile_value is None:
        return arg_value
    return profile_value if arg_value == default_value else arg_value


def resolve_capture_profile(case_cfg: dict[str, object], entry: str, odds: int, args_presses: int | None, args_settle_wait: float | None) -> tuple[int, float]:
    default_press_key = 'save_capture_presses' if entry == 'save' else 'capture_presses'
    odds_profile = resolve_odds_profile(case_cfg, entry, odds)
    if args_presses is not None:
        presses = args_presses
    else:
        presses = int(odds_profile.get('presses', case_cfg[default_press_key]))
    if args_settle_wait is not None:
        settle_wait = args_settle_wait
    else:
        settle_wait = float(odds_profile.get('settle_wait', 0.0))
    return presses, settle_wait


def resolve_runtime_profile(
    case_cfg: dict[str, object],
    entry: str,
    odds: int,
    args_presses: int | None,
    args_settle_wait: float | None,
    args_press_interval: float | None,
    args_reset_wait: float | None,
) -> tuple[dict[str, object], int, float, float, float, int | None, bool]:
    odds_profile = resolve_odds_profile(case_cfg, entry, odds)
    presses, settle_wait = resolve_capture_profile(case_cfg, entry, odds, args_presses, args_settle_wait)
    press_interval = args_press_interval if args_press_interval is not None else float(odds_profile.get('press_interval', case_cfg.get(f'{entry}_press_interval', DEFAULT_PRESS_INTERVAL)))
    reset_wait = args_reset_wait if args_reset_wait is not None else float(odds_profile.get('reset_wait', case_cfg.get(f'{entry}_reset_wait', DEFAULT_RESET_WAIT)))
    launch_jitter_step_ms = odds_profile.get('launch_jitter_step_ms', case_cfg.get(f'{entry}_launch_jitter_step_ms'))
    launch_jitter_step_ms = int(launch_jitter_step_ms) if launch_jitter_step_ms is not None else None
    unthrottled = bool(odds_profile.get('unthrottled', case_cfg.get(f'{entry}_unthrottled', True)))
    return odds_profile, presses, settle_wait, press_interval, reset_wait, launch_jitter_step_ms, unthrottled


def pick_pk3s(directory: Path) -> list[Path]:
    matches = sorted(directory.glob('*.pk3'))
    if not matches:
        raise FileNotFoundError(f'No .pk3 files were produced in {directory}.')
    return matches


def extract_metric(stdout: str, label: str) -> float | None:
    prefix = f'{label}:'
    for line in stdout.splitlines():
        if not line.startswith(prefix):
            continue
        try:
            return float(line.split(':', 1)[1].strip())
        except ValueError:
            return None
    return None


def bounded_jitter_offset_ms(index: int, step_ms: int) -> int:
    if step_ms <= 0:
        return 0
    pattern = (0, 1, -1, 2, -2, 3, -3, 4, -4)
    return pattern[(index - 1) % len(pattern)] * step_ms


def build_summary(
    args: argparse.Namespace,
    prefix: str,
    presses: int,
    settle_wait: float,
    press_interval: float,
    reset_wait: float | None,
    effective_jitter_ms: int,
    results: list[dict[str, object]],
    shiny_hits: int,
    pkhex_legal_hits: int,
) -> dict[str, object]:
    successful_captures = sum(1 for row in results if row.get('capture_ok'))
    failed_captures = len(results) - successful_captures
    pids = [
        str(row['pid'])
        for row in results
        if row.get('capture_ok') and row.get('pid') is not None
    ]
    unique_pids = len(set(pids))
    generation_latencies = [
        row['generation_latency_s']
        for row in results
        if row.get('capture_ok') and row.get('generation_latency_s') is not None
    ]
    quicksave_latencies = [
        row['quicksave_write_latency_s']
        for row in results
        if row.get('capture_ok') and row.get('quicksave_write_latency_s') is not None
    ]
    return {
        'case': args.case,
        'odds': args.odds,
        'mode': args.mode,
        'iterations': args.iterations,
        'attempted_iterations': len(results),
        'completed_iterations': successful_captures,
        'failed_captures': failed_captures,
        'unique_pids': unique_pids,
        'duplicate_pids': len(pids) - unique_pids,
        'entry': args.entry,
        'capture_presses': presses,
        'launch_jitter_step_ms': effective_jitter_ms,
        'settle_wait': settle_wait,
        'press_interval': press_interval,
        'reuse_mgba': args.reuse_mgba,
        'reset_wait': reset_wait if args.reuse_mgba else None,
        'shiny_hits': shiny_hits,
        'observed_rate': (shiny_hits / successful_captures) if successful_captures else 0,
        'pkhex_legal_shiny_hits': pkhex_legal_hits,
        'avg_generation_latency_s': (sum(generation_latencies) / len(generation_latencies)) if generation_latencies else None,
        'max_generation_latency_s': max(generation_latencies) if generation_latencies else None,
        'avg_quicksave_write_latency_s': (sum(quicksave_latencies) / len(quicksave_latencies)) if quicksave_latencies else None,
        'max_quicksave_write_latency_s': max(quicksave_latencies) if quicksave_latencies else None,
        'results': results,
        'stopped_early': False,
        'stop_reason': None,
    }


def write_summary(path: Path, summary: dict[str, object]) -> None:
    path.write_text(json.dumps(summary, indent=2), encoding='utf-8')


def run_pkhex_check_with_retries(pkhex_path: Path, target_pk3: Path, json_base_path: Path) -> tuple[str, Path | None, dict[str, object] | None]:
    last_status = 'error'
    last_json_path: Path | None = None
    last_payload: dict[str, object] | None = None

    for attempt_index, config in enumerate(PKHEX_RECHECK_ATTEMPTS, start=1):
        json_path = json_base_path if attempt_index == 1 else json_base_path.with_name(
            f'{json_base_path.stem}_retry{attempt_index}{json_base_path.suffix}'
        )
        try:
            json_path.unlink()
        except FileNotFoundError:
            pass

        pkhex_cmd = [
            'python', str(PKHEX_CHECK),
            '--pkhex', str(pkhex_path),
            '--file', str(target_pk3),
            '--output', str(json_path),
            '--wait', str(config['wait']),
            '--retries', str(config['retries']),
            '--retry-interval', str(config['retry_interval']),
            '--launch-retries', str(config['launch_retries']),
        ]
        pkhex_result = subprocess.run(pkhex_cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)

        payload: dict[str, object] | None = None
        status = 'error' if pkhex_result.returncode != 0 else 'unknown'
        if json_path.exists():
            try:
                payload = json.loads(json_path.read_text(encoding='utf-8'))
                status = str(payload.get('status', 'unknown'))
            except Exception:
                status = 'error'

        last_status = status
        last_json_path = json_path if json_path.exists() else None
        last_payload = payload
        if status in DECISIVE_PKHEX_STATUSES:
            return status, last_json_path, last_payload

    return last_status, last_json_path, last_payload


def launch_reusable_mgba(
    mgba_path: Path,
    patched_rom: Path,
    save_source: Path,
    wait: float,
    tile_index: int | None = None,
    tile_count: int | None = None,
) -> subprocess.Popen:
    if not save_source.exists():
        raise FileNotFoundError(f'Expected save file was not found: {save_source}')
    target_save = patched_rom.with_suffix('.sav')
    shutil.copyfile(save_source, target_save)
    proc = subprocess.Popen([str(mgba_path), str(patched_rom)], cwd=REPO_ROOT)
    time.sleep(wait)
    if tile_index is not None and tile_count is not None:
        gui_harness.tile_window('mgba', tile_index, tile_count, pid=proc.pid)
    return proc


def restart_reusable_mgba(
    proc: subprocess.Popen | None,
    mgba_path: Path,
    patched_rom: Path,
    save_source: Path,
    wait: float,
    tile_index: int | None = None,
    tile_count: int | None = None,
) -> subprocess.Popen:
    if proc is not None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    return launch_reusable_mgba(
        mgba_path,
        patched_rom,
        save_source,
        wait,
        tile_index=tile_index,
        tile_count=tile_count,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='Run repeated starter generations to audit observed shiny odds.')
    parser.add_argument('case', choices=tuple(ROM_BY_CASE))
    parser.add_argument('--odds', type=int, default=16)
    parser.add_argument('--mode', default='auto', choices=('auto', 'canonical', 'legacy', 'native', 'reroll'))
    parser.add_argument('--iterations', type=int, default=20)
    parser.add_argument('--launch-wait', type=float, default=6.0)
    parser.add_argument('--launch-jitter-step-ms', type=int, default=None, help='Extra deterministic delay added per iteration before inputs start')
    parser.add_argument('--entry', choices=('state', 'save'), default='state', help='Use a savestate debug entry point or a real .sav boot entry point')
    parser.add_argument('--press-interval', type=float, default=None)
    parser.add_argument('--settle-wait', type=float, default=None, help='Extra wait after the scripted input sequence before quick-saving')
    parser.add_argument('--presses', type=int, help='Override capture timing; defaults to the local tuned case value')
    parser.add_argument('--save', type=Path, help='Override the in-game .sav source used for launched save-entry captures')
    parser.add_argument('--post-wait', type=float, default=0.0, help='Extra wait after the main scripted presses before sending any post-confirmation A presses')
    parser.add_argument('--post-buttons', default='', help='Comma-separated buttons to send after post-wait and before any repeated post-confirmation A presses')
    parser.add_argument('--post-presses', type=int, default=0, help='Extra A presses to send after post-wait')
    parser.add_argument('--post-press-interval', type=float, default=None, help='Spacing for post-confirmation A presses; defaults to --press-interval')
    parser.add_argument('--fast-forward', action='store_true', default=True, help='Use the starter_capture default fast-forward toggle')
    parser.add_argument('--no-fast-forward', dest='fast_forward', action='store_false', help='Disable focus-sensitive host fast-forward toggles during capture')
    parser.add_argument('--output-prefix', default=None)
    parser.add_argument('--pkhex', type=Path, default=DEFAULT_PKHEX)
    parser.add_argument('--check-shiny-pkhex', action='store_true', help='Run PKHeX only for shiny hits')
    parser.add_argument('--reuse-mgba', action='store_true', help='Launch one mGBA session and use Ctrl+R between iterations')
    parser.add_argument('--mgba', type=Path, default=DEFAULT_MGBA)
    parser.add_argument('--reset-mode', choices=('host', 'soft'), default='host', help='Use host Ctrl+R or in-game soft reset when reusing mGBA')
    parser.add_argument('--reset-wait', type=float, default=None, help='Seconds to wait after Ctrl+R before sending inputs when reusing mGBA')
    parser.add_argument('--tile-index', type=int, help='Tile slot index for the reusable mGBA window')
    parser.add_argument('--tile-count', type=int, help='Total number of tiled mGBA windows')
    parser.add_argument('--reuse-refresh-every', type=int, default=0, help='Restart the reusable mGBA session after this many iterations; 0 disables periodic refreshes')
    parser.add_argument('--reuse-reset-first', action='store_true', help='Apply the normal reuse reset before the first counted iteration too')
    parser.add_argument('--target-shiny-hits', type=int, default=0, help='Stop early once this many shiny hits have been captured')
    parser.add_argument('--target-legal-shiny-hits', type=int, default=0, help='Stop early once this many PKHeX-legal shiny hits have been captured')
    parser.add_argument('--extract-mode', choices=('auto', 'state', 'memory'), default='auto', help='Capture from savestate, live process memory, or automatic fallback')
    parser.add_argument('--memory-retry-timeout', type=float, default=2.0, help='Seconds to keep retrying process-memory extraction after the scripted input sequence')
    parser.add_argument('--memory-retry-interval', type=float, default=0.1, help='Seconds between process-memory extraction retries')
    args = parser.parse_args()

    if args.reuse_mgba and args.entry != 'save':
        raise SystemExit('--reuse-mgba currently requires --entry save.')

    cases = load_cases()
    case_cfg = cases[args.case]
    odds_profile, presses, resolved_settle_wait, resolved_press_interval, resolved_reset_wait, profile_launch_jitter_step_ms, resolved_unthrottled = resolve_runtime_profile(
        case_cfg,
        args.entry,
        args.odds,
        args.presses,
        args.settle_wait,
        args.press_interval,
        args.reset_wait,
    )
    resolved_launch_wait = float(prefer_profile_value(args.launch_wait, parser.get_default('launch_wait'), odds_profile.get('launch_wait')))
    resolved_post_wait = float(prefer_profile_value(args.post_wait, parser.get_default('post_wait'), odds_profile.get('post_wait')))
    resolved_post_buttons = str(prefer_profile_value(args.post_buttons, parser.get_default('post_buttons'), odds_profile.get('post_buttons')))
    resolved_post_presses = int(prefer_profile_value(args.post_presses, parser.get_default('post_presses'), odds_profile.get('post_presses', 0)))
    resolved_post_press_interval = prefer_profile_value(args.post_press_interval, parser.get_default('post_press_interval'), odds_profile.get('post_press_interval'))
    resolved_extract_mode = str(prefer_profile_value(args.extract_mode, parser.get_default('extract_mode'), odds_profile.get('extract_mode')))
    resolved_memory_retry_timeout = float(prefer_profile_value(args.memory_retry_timeout, parser.get_default('memory_retry_timeout'), odds_profile.get('memory_retry_timeout')))
    resolved_memory_retry_interval = float(prefer_profile_value(args.memory_retry_interval, parser.get_default('memory_retry_interval'), odds_profile.get('memory_retry_interval')))
    effective_jitter_ms = args.launch_jitter_step_ms
    if effective_jitter_ms is None:
        effective_jitter_ms = profile_launch_jitter_step_ms
    if effective_jitter_ms is None and args.reuse_mgba and args.entry == 'save':
        effective_jitter_ms = DEFAULT_SAVE_REUSE_JITTER_MS
    if effective_jitter_ms is None:
        effective_jitter_ms = 0
    args.reset_wait = resolved_reset_wait
    prefix = args.output_prefix or f'odds_{args.case}_{args.mode}_1in{args.odds}'
    patched_rom = ARTIFACTS / f'{prefix}.gba'
    capture_dir = ARTIFACTS / f'{prefix}_party'
    summary_path = ARTIFACTS / f'{prefix}_summary.json'

    ARTIFACTS.mkdir(exist_ok=True)
    capture_dir.mkdir(parents=True, exist_ok=True)
    for stale in capture_dir.glob('*.pk3'):
        stale.unlink()

    patch_cmd = [
        'python', str(PATCHER), str(ROM_BY_CASE[args.case]),
        '--odds', str(args.odds), '--mode', args.mode,
        '--output', str(patched_rom), '--overwrite-output',
    ]
    patch_env = os.environ.copy()
    for patch_env_map in (case_cfg.get('patch_env'), odds_profile.get('patch_env')):
        if isinstance(patch_env_map, dict):
            for key, value in patch_env_map.items():
                patch_env[str(key)] = str(value)
    patch_result = subprocess.run(patch_cmd, cwd=REPO_ROOT, env=patch_env, check=False)
    if patch_result.returncode != 0:
        return patch_result.returncode

    mgba_proc: subprocess.Popen | None = None
    save_source: Path | None = None
    profile_save = odds_profile.get('save')
    resolved_save_source = args.save if args.save is not None else (REPO_ROOT / Path(profile_save if profile_save is not None else case_cfg['save']))
    if args.reuse_mgba:
        save_source = resolved_save_source
        mgba_proc = launch_reusable_mgba(
            args.mgba,
            patched_rom,
            save_source,
            resolved_launch_wait,
            tile_index=args.tile_index,
            tile_count=args.tile_count,
        )

    shiny_hits = 0
    pkhex_legal_hits = 0
    results = []
    stop_reason: str | None = None
    last_success_pid: str | None = None
    duplicate_streak = 0
    try:
        for index in range(1, args.iterations + 1):
            for stale in capture_dir.glob('*.pk3'):
                stale.unlink()
            if (
                args.reuse_mgba
                and save_source is not None
                and args.reuse_refresh_every > 0
                and index > 1
                and (index - 1) % args.reuse_refresh_every == 0
            ):
                mgba_proc = restart_reusable_mgba(
                    mgba_proc,
                    args.mgba,
                    patched_rom,
                    save_source,
                    resolved_launch_wait,
                    tile_index=args.tile_index,
                    tile_count=args.tile_count,
                )
            jitter_offset_ms = bounded_jitter_offset_ms(index, effective_jitter_ms)
            iter_launch_wait = max(0.0, resolved_launch_wait + (jitter_offset_ms / 1000.0))
            iter_reset_wait = max(0.0, resolved_reset_wait + (jitter_offset_ms / 1000.0))
            capture_cmd = [
                'python', str(CAPTURE), args.case,
                '--cases', str(CASES), '--entry', args.entry, '--rom', str(patched_rom),
                '--launch-wait', str(iter_launch_wait), '--output-dir', str(capture_dir),
                '--press-interval', str(resolved_press_interval), '--settle-wait', str(resolved_settle_wait), '--presses', str(presses),
                '--extract-mode', resolved_extract_mode,
                '--memory-retry-timeout', str(resolved_memory_retry_timeout),
                '--memory-retry-interval', str(resolved_memory_retry_interval),
            ]
            if args.entry == 'save':
                capture_cmd.extend(['--save', str(resolved_save_source)])
            capture_cmd.append('--unthrottled' if resolved_unthrottled else '--no-unthrottled')
            if resolved_post_wait > 0:
                capture_cmd.extend(['--post-wait', str(resolved_post_wait)])
            if resolved_post_buttons:
                capture_cmd.extend(['--post-buttons', resolved_post_buttons])
            if resolved_post_presses > 0:
                capture_cmd.extend(['--post-presses', str(resolved_post_presses)])
            if resolved_post_press_interval is not None:
                capture_cmd.extend(['--post-press-interval', str(resolved_post_press_interval)])
            if not args.fast_forward:
                capture_cmd.append('--no-fast-forward')
            if args.reuse_mgba:
                capture_cmd.extend(['--attach-running', '--mgba-pid', str(mgba_proc.pid)])
                if index > 1 or args.reuse_reset_first:
                    capture_cmd.extend(['--reset-before-capture', '--reset-mode', args.reset_mode, '--reset-wait', str(iter_reset_wait)])
            capture_result = subprocess.run(capture_cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
            if capture_result.returncode != 0:
                failure_text = ((capture_result.stdout or '') + (capture_result.stderr or '')).strip()
                results.append({'iteration': index, 'capture_ok': False, 'error': failure_text})
                last_success_pid = None
                duplicate_streak = 0
                if args.reuse_mgba and save_source is not None:
                    mgba_proc = restart_reusable_mgba(
                        mgba_proc,
                        args.mgba,
                        patched_rom,
                        save_source,
                        resolved_launch_wait,
                        tile_index=args.tile_index,
                        tile_count=args.tile_count,
                    )
                    # After a failed capture, restart the reuse session from a
                    # clean .sav so stale process memory cannot masquerade as a
                    # fresh result on the next iteration.
                continue
            pk3s = pick_pk3s(capture_dir)
            parsed_candidates = [(pk3, parse_gen3_pk3(pk3)) for pk3 in pk3s]
            pk3, mon = parsed_candidates[0]
            capture_text = (capture_result.stdout or '') + '\n' + (capture_result.stderr or '')
            generation_latency_s = extract_metric(capture_text, 'generation_latency_s')
            quicksave_write_latency_s = extract_metric(capture_text, 'quicksave_write_latency_s')
            pid_text = f'0x{mon.pid:08X}'
            if args.reuse_mgba:
                if pid_text == last_success_pid:
                    duplicate_streak += 1
                else:
                    last_success_pid = pid_text
                    duplicate_streak = 1
                if duplicate_streak >= 3:
                    while results and results[-1].get('capture_ok') and results[-1].get('pid') == pid_text:
                        results.pop()
                    results.append(
                        {
                            'iteration': index,
                            'capture_ok': False,
                            'error': f'repeated_pid_storm:{pid_text}',
                        }
                    )
                    last_success_pid = None
                    duplicate_streak = 0
                    if save_source is not None:
                        mgba_proc = restart_reusable_mgba(
                            mgba_proc,
                            args.mgba,
                            patched_rom,
                            save_source,
                            resolved_launch_wait,
                            tile_index=args.tile_index,
                            tile_count=args.tile_count,
                        )
                    summary = build_summary(
                        args,
                        prefix,
                        presses,
                        resolved_settle_wait,
                        resolved_press_interval,
                        resolved_reset_wait,
                        effective_jitter_ms,
                        results,
                        shiny_hits,
                        pkhex_legal_hits,
                    )
                    write_summary(summary_path, summary)
                    continue
            else:
                last_success_pid = pid_text
                duplicate_streak = 1
            row = {
                'iteration': index,
                'capture_ok': True,
                'pk3': str(pk3),
                'pid': pid_text,
                'shiny_xor': mon.shiny_xor,
                'is_shiny': mon.is_shiny,
                'nature': mon.nature,
                'launch_wait': iter_launch_wait,
                'reset_wait': iter_reset_wait if args.reuse_mgba and index > 1 else None,
                'generation_latency_s': generation_latency_s,
                'quicksave_write_latency_s': quicksave_write_latency_s,
                'candidate_count': len(parsed_candidates),
            }
            shiny_candidates = [(candidate_pk3, candidate_mon) for candidate_pk3, candidate_mon in parsed_candidates if candidate_mon.is_shiny]
            if shiny_candidates:
                shiny_hits += 1
                row['any_shiny_candidate'] = True
                row['shiny_candidate_count'] = len(shiny_candidates)
                copied_shiny_pk3s: list[str] = []
                legal_shiny_found = False
                last_pkhex_status = 'unknown'
                last_pkhex_json: str | None = None
                for shiny_index, (shiny_candidate_pk3, _) in enumerate(shiny_candidates, start=1):
                    suffix = '' if len(shiny_candidates) == 1 else f'_cand{shiny_index:02d}'
                    shiny_pk3 = ARTIFACTS / f'{prefix}_shiny_{index:03d}{suffix}.pk3'
                    shutil.copyfile(shiny_candidate_pk3, shiny_pk3)
                    copied_shiny_pk3s.append(str(shiny_pk3))
                    if not (args.check_shiny_pkhex and args.pkhex.exists()):
                        continue
                    pkhex_json = ARTIFACTS / f'{prefix}_shiny_{index:03d}{suffix}.json'
                    last_pkhex_status, resolved_pkhex_json, payload = run_pkhex_check_with_retries(args.pkhex, shiny_pk3, pkhex_json)
                    if resolved_pkhex_json is not None:
                        last_pkhex_json = str(resolved_pkhex_json)
                    if last_pkhex_status == 'legal':
                        pkhex_legal_hits += 1
                        row['pkhex_status'] = 'legal'
                        if last_pkhex_json is not None:
                            row['pkhex_json'] = last_pkhex_json
                        row['legal_shiny_pk3'] = str(shiny_pk3)
                        legal_shiny_found = True
                        break
                row['shiny_pk3s'] = copied_shiny_pk3s
                if args.check_shiny_pkhex and args.pkhex.exists():
                    if not legal_shiny_found:
                        row['pkhex_status'] = last_pkhex_status
                        if last_pkhex_json is not None:
                            row['pkhex_json'] = last_pkhex_json
            else:
                row['any_shiny_candidate'] = False
            results.append(row)
            summary = build_summary(args, prefix, presses, resolved_settle_wait, resolved_press_interval, resolved_reset_wait, effective_jitter_ms, results, shiny_hits, pkhex_legal_hits)
            if args.target_shiny_hits > 0 and shiny_hits >= args.target_shiny_hits:
                stop_reason = f'target_shiny_hits={args.target_shiny_hits}'
            if args.target_legal_shiny_hits > 0 and pkhex_legal_hits >= args.target_legal_shiny_hits:
                stop_reason = f'target_legal_shiny_hits={args.target_legal_shiny_hits}'
            if stop_reason:
                summary['stopped_early'] = True
                summary['stop_reason'] = stop_reason
                write_summary(summary_path, summary)
                break
            write_summary(summary_path, summary)
    finally:
        if mgba_proc is not None:
            try:
                mgba_proc.terminate()
            except Exception:
                pass

    summary = build_summary(args, prefix, presses, resolved_settle_wait, resolved_press_interval, resolved_reset_wait, effective_jitter_ms, results, shiny_hits, pkhex_legal_hits)
    summary['stopped_early'] = stop_reason is not None
    summary['stop_reason'] = stop_reason
    write_summary(summary_path, summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'results'}, indent=2))
    print(f'summary_json: {summary_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
