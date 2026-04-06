#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import gui_harness
from extract_gen3_party_from_state import get_gen3_species
from inspect_gen3_pk3 import NATURES, decode_string
from process_memory_gen3 import (
    find_raw_party_slots_in_process,
    find_trace_records_in_process,
    find_party_mons_in_process,
    find_valid_mons_by_pid_otid_in_process,
    find_valid_named_mons_in_process,
)
from starter_capture import DEFAULT_CASES, DEFAULT_MGBA, load_cases, safe_focus
from starter_memory_timeline import run_input_sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
PATCHER = REPO_ROOT / "shiny_patcher.py"
ARTIFACTS = REPO_ROOT / "artifacts"
ROM_BY_CASE = {
    "firered": REPO_ROOT / ".roms" / "Pokemon - Fire Red.gba",
    "leafgreen": REPO_ROOT / ".roms" / "Pokemon - Leaf Green.gba",
    "ruby": REPO_ROOT / ".roms" / "Pokemon - Ruby.gba",
    "sapphire": REPO_ROOT / ".roms" / "Pokemon - Sapphire.gba",
    "emerald": REPO_ROOT / ".roms" / "Pokemon - Emerald.gba",
}
GAME_CODE_BY_CASE = {
    "firered": "BPRE",
    "leafgreen": "BPGE",
    "ruby": "AXVE",
    "sapphire": "AXPE",
    "emerald": "BPEE",
}


def resolve_odds_profile(case_cfg: dict[str, object], odds: int) -> dict[str, object]:
    profiles = case_cfg.get("save_profiles", {})
    if not isinstance(profiles, dict):
        return {}
    odds_profile = profiles.get(str(odds), {}) or {}
    return odds_profile if isinstance(odds_profile, dict) else {}

DEBUG_TRACE_MAGIC = 0x5254504B
DEBUG_TRACE_TAG_GIFT = 0x54464947
DEBUG_TRACE_TAG_PRIMARY = 0x4D495250
DEBUG_TRACE_TAG_STARTER_DIRECT = 0x52494453
DEBUG_TRACE_TAG_STARTER_ALT = 0x544C4153
DEBUG_TRACE_FLAG_ENTRY = 0x52544E45
DEBUG_TRACE_FLAG_RETRY = 0x59525452
DEBUG_TRACE_FLAG_DONE = 0x454E4F44
DEBUG_TRACE_FLAG_INIT = 0x54494E49
DEBUG_TRACE_FLAG_READY = 0x59444552
DEBUG_TRACE_FLAG_SHINY = 0x4E594853
DEBUG_TRACE_ADDR_LOW16 = 0xFE80
DEBUG_TRACE_PRIMARY_ADDR_LOW16 = 0xFEC0
DEBUG_TRACE_STARTER_DIRECT_ADDR_LOW16 = 0xFF00
DEBUG_TRACE_STARTER_ALT_ADDR_LOW16 = 0xFF80
DEBUG_TRACE_COUNT_ENTRY_INDEX = 11
DEBUG_TRACE_COUNT_RETRY_INDEX = 12
DEBUG_TRACE_COUNT_DONE_INDEX = 13
DEBUG_TRACE_COUNT_SHINY_INDEX = 14
DEBUG_TRACE_COUNT_OWNER_BLOCK_INDEX = 15


def parse_mon(raw: bytes) -> dict[str, object]:
    pid = int.from_bytes(raw[0:4], "little")
    otid = int.from_bytes(raw[4:8], "little")
    tid = otid & 0xFFFF
    sid = (otid >> 16) & 0xFFFF
    shiny_xor = ((pid >> 16) ^ (pid & 0xFFFF) ^ tid ^ sid) & 0xFFFF
    return {
        "pid": f"0x{pid:08X}",
        "otid": f"0x{otid:08X}",
        "tid": tid,
        "sid": sid,
        "nickname": decode_string(raw[8:18]),
        "nature": NATURES[pid % 25],
        "level": raw[84],
        "shiny_xor": shiny_xor,
        "is_shiny": shiny_xor < 8,
        "species_id": get_gen3_species(raw),
    }


def parse_trace(blob: bytes, address: int) -> dict[str, object]:
    words = [int.from_bytes(blob[idx:idx + 4], "little") for idx in range(0, min(len(blob), 0x40), 4)]
    pid = words[5] if len(words) > 5 else 0
    otid = words[6] if len(words) > 6 else 0
    counter_raw = words[7] if len(words) > 7 else 0
    caller_return = words[8] if len(words) > 8 else 0
    record = {
        "address": f"0x{address:016X}",
        "magic": f"0x{words[0]:08X}" if len(words) > 0 else None,
        "tag": f"0x{words[1]:08X}" if len(words) > 1 else None,
        "entry_seen": len(words) > 2 and words[2] == DEBUG_TRACE_FLAG_ENTRY,
        "retry_seen": len(words) > 3 and words[3] == DEBUG_TRACE_FLAG_RETRY,
        "done_seen": len(words) > 4 and words[4] == DEBUG_TRACE_FLAG_DONE,
        "pid": f"0x{pid:08X}",
        "otid": f"0x{otid:08X}",
        "counter_raw": f"0x{counter_raw:08X}",
        "counter_magic_ok": ((counter_raw >> 16) & 0xFFFF) == 0xA5A5,
        "counter_remaining": counter_raw & 0xFFFF,
        "caller_return": f"0x{caller_return:08X}",
        "shiny_seen": False,
        "entry_count": words[DEBUG_TRACE_COUNT_ENTRY_INDEX] if len(words) > DEBUG_TRACE_COUNT_ENTRY_INDEX else 0,
        "retry_count": words[DEBUG_TRACE_COUNT_RETRY_INDEX] if len(words) > DEBUG_TRACE_COUNT_RETRY_INDEX else 0,
        "done_count": words[DEBUG_TRACE_COUNT_DONE_INDEX] if len(words) > DEBUG_TRACE_COUNT_DONE_INDEX else 0,
        "shiny_count": words[DEBUG_TRACE_COUNT_SHINY_INDEX] if len(words) > DEBUG_TRACE_COUNT_SHINY_INDEX else 0,
        "owner_block_count": words[DEBUG_TRACE_COUNT_OWNER_BLOCK_INDEX] if len(words) > DEBUG_TRACE_COUNT_OWNER_BLOCK_INDEX else 0,
    }
    if len(words) > 1 and words[1] == DEBUG_TRACE_TAG_GIFT:
        ready_flag = words[9] if len(words) > 9 else 0
        record["init_seen"] = len(words) > 8 and words[8] == DEBUG_TRACE_FLAG_INIT
        record["ready_seen"] = len(words) > 9 and ready_flag == DEBUG_TRACE_FLAG_READY
        record["caller_return"] = None
        record["shiny_seen"] = len(words) > 10 and words[10] == DEBUG_TRACE_FLAG_SHINY
    else:
        record["shiny_seen"] = len(words) > 9 and words[9] == DEBUG_TRACE_FLAG_SHINY
    return record


def parse_raw_party_slot(raw: bytes, address: int, slot_index: int, party_count: int) -> dict[str, object]:
    pid = int.from_bytes(raw[0:4], "little")
    otid = int.from_bytes(raw[4:8], "little")
    return {
        "address": f"0x{address:016X}",
        "slot_index": slot_index,
        "party_count": party_count,
        "pid": f"0x{pid:08X}",
        "otid": f"0x{otid:08X}",
        "nickname": decode_string(raw[8:18]),
        "level": raw[84],
        "valid_party_mon": get_gen3_species(raw) is not None and raw[84] > 0,
    }


def get_pid_otid_pair(entry: dict[str, object]) -> tuple[int, int] | None:
    pid_raw = entry.get("pid")
    otid_raw = entry.get("otid")
    if not isinstance(pid_raw, str) or not isinstance(otid_raw, str):
        return None
    try:
        return int(pid_raw, 16), int(otid_raw, 16)
    except ValueError:
        return None


def summarize_trace_correlations(output: dict[str, object]) -> dict[str, object]:
    trace_records = [
        rec for rec in output.get("trace_records", [])
        if isinstance(rec, dict)
    ]
    trace_by_pair: dict[tuple[int, int], list[dict[str, object]]] = collections.defaultdict(list)
    for rec in trace_records:
        pair = get_pid_otid_pair(rec)
        if pair is None:
            continue
        trace_by_pair[pair].append(rec)

    def annotate_matches(matches: list[dict[str, object]]) -> list[dict[str, object]]:
        annotated: list[dict[str, object]] = []
        for match in matches:
            entry = dict(match)
            pair = get_pid_otid_pair(entry)
            linked_traces = trace_by_pair.get(pair, []) if pair is not None else []
            entry["matching_trace_kinds"] = [str(trace.get("kind")) for trace in linked_traces]
            entry["matching_trace_details"] = [
                {
                    "kind": trace.get("kind"),
                    "address": trace.get("address"),
                    "entry_count": trace.get("entry_count"),
                    "retry_count": trace.get("retry_count"),
                    "done_count": trace.get("done_count"),
                    "shiny_count": trace.get("shiny_count"),
                    "owner_block_count": trace.get("owner_block_count"),
                    "caller_return": trace.get("caller_return"),
                }
                for trace in linked_traces
            ]
            annotated.append(entry)
        return annotated

    party_matches = annotate_matches([
        match for match in output.get("party_matches", [])
        if isinstance(match, dict)
    ])
    generic_matches = annotate_matches([
        match for match in output.get("mons", [])
        if isinstance(match, dict)
    ])

    generic_pair_counts: collections.Counter[tuple[int, int]] = collections.Counter()
    for match in generic_matches:
        pair = get_pid_otid_pair(match)
        if pair is not None:
            generic_pair_counts[pair] += 1

    generic_groups: list[dict[str, object]] = []
    for pair, count in generic_pair_counts.most_common():
        pid, otid = pair
        linked_traces = trace_by_pair.get(pair, [])
        generic_groups.append(
            {
                "pid": f"0x{pid:08X}",
                "otid": f"0x{otid:08X}",
                "match_count": count,
                "matching_trace_kinds": [str(trace.get("kind")) for trace in linked_traces],
                "matching_trace_details": [
                    {
                        "kind": trace.get("kind"),
                        "address": trace.get("address"),
                        "entry_count": trace.get("entry_count"),
                        "retry_count": trace.get("retry_count"),
                        "done_count": trace.get("done_count"),
                        "shiny_count": trace.get("shiny_count"),
                        "owner_block_count": trace.get("owner_block_count"),
                        "caller_return": trace.get("caller_return"),
                    }
                    for trace in linked_traces
                ],
            }
        )

    primary_party = party_matches[0] if party_matches else None
    primary_generic = generic_groups[0] if generic_groups else None
    party_pair = get_pid_otid_pair(primary_party) if primary_party else None
    generic_pair = (
        (int(primary_generic["pid"], 16), int(primary_generic["otid"], 16))
        if isinstance(primary_generic, dict)
        else None
    )

    trace_summary = []
    for rec in trace_records:
        trace_summary.append(
            {
                "kind": rec.get("kind"),
                "pid": rec.get("pid"),
                "otid": rec.get("otid"),
                "entry_count": rec.get("entry_count"),
                "retry_count": rec.get("retry_count"),
                "done_count": rec.get("done_count"),
                "shiny_count": rec.get("shiny_count"),
                "owner_block_count": rec.get("owner_block_count"),
                "caller_return": rec.get("caller_return"),
            }
        )

    return {
        "trace_summary": trace_summary,
        "annotated_party_matches": party_matches,
        "annotated_generic_matches": generic_matches,
        "generic_pid_groups": generic_groups,
        "primary_party_pid": primary_party.get("pid") if primary_party else None,
        "primary_party_otid": primary_party.get("otid") if primary_party else None,
        "primary_party_matching_trace_kinds": primary_party.get("matching_trace_kinds") if primary_party else [],
        "primary_generic_pid": primary_generic.get("pid") if primary_generic else None,
        "primary_generic_otid": primary_generic.get("otid") if primary_generic else None,
        "primary_generic_matching_trace_kinds": primary_generic.get("matching_trace_kinds") if primary_generic else [],
        "party_generic_same_pair": party_pair == generic_pair if party_pair and generic_pair else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one starter capture and read the FR/LG GiveMon hook trace record from live mGBA memory.")
    parser.add_argument("case", choices=("firered", "leafgreen"))
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--mgba", type=Path, default=DEFAULT_MGBA)
    parser.add_argument("--odds", type=int, default=64)
    parser.add_argument("--mode", choices=("auto", "canonical", "legacy", "native", "reroll"), default="auto")
    parser.add_argument("--launch-wait", type=float, default=8.0)
    parser.add_argument("--press-interval", type=float, default=0.6)
    parser.add_argument("--settle-wait", type=float, default=0.5)
    parser.add_argument("--presses", type=int)
    parser.add_argument("--hold", type=float, default=0.05)
    parser.add_argument("--pre-buttons", default="")
    parser.add_argument("--post-wait", type=float, default=0.0)
    parser.add_argument("--post-buttons", default="")
    parser.add_argument("--post-presses", type=int, default=0)
    parser.add_argument("--post-press-interval", type=float, default=None)
    parser.add_argument("--sample-after", type=float, default=0.25)
    parser.add_argument("--output-prefix", default=None)
    parser.add_argument("--filter", default="gift-only")
    parser.add_argument("--primary-skip-mode", choices=("all", "fixed-only"), default="all")
    parser.add_argument("--disable-secondary-wrappers", action="store_true")
    parser.add_argument("--skip-gift-direct", action="store_true")
    parser.add_argument("--trace-primary", action="store_true")
    parser.add_argument("--trace-starters", action="store_true")
    parser.add_argument("--fast-forward", action="store_true", default=True)
    parser.add_argument("--no-fast-forward", dest="fast_forward", action="store_false")
    parser.add_argument("--reset-before-capture", action="store_true")
    parser.add_argument("--reset-mode", choices=("host", "soft"), default="host")
    parser.add_argument("--reset-wait", type=float, default=3.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    cases = load_cases(args.cases)
    case_cfg = cases[args.case]
    odds_profile = resolve_odds_profile(case_cfg, args.odds)
    rom = ROM_BY_CASE[args.case]
    profile_save = odds_profile.get("save")
    save_path = REPO_ROOT / Path(profile_save if profile_save is not None else case_cfg["save"])
    nickname = str(case_cfg["nickname"])
    presses = args.presses if args.presses is not None else int(odds_profile.get("presses", case_cfg["save_capture_presses"]))
    if args.launch_wait == parser.get_default("launch_wait") and odds_profile.get("launch_wait") is not None:
        args.launch_wait = float(odds_profile["launch_wait"])
    if args.press_interval == parser.get_default("press_interval") and odds_profile.get("press_interval") is not None:
        args.press_interval = float(odds_profile["press_interval"])
    if args.settle_wait == parser.get_default("settle_wait") and odds_profile.get("settle_wait") is not None:
        args.settle_wait = float(odds_profile["settle_wait"])
    if args.post_wait == parser.get_default("post_wait") and odds_profile.get("post_wait") is not None:
        args.post_wait = float(odds_profile["post_wait"])
    if args.post_buttons == parser.get_default("post_buttons") and odds_profile.get("post_buttons") is not None:
        args.post_buttons = str(odds_profile["post_buttons"])
    if args.post_press_interval == parser.get_default("post_press_interval") and odds_profile.get("post_press_interval") is not None:
        args.post_press_interval = float(odds_profile["post_press_interval"])

    prefix = args.output_prefix or f"trace_{args.case}_gift_1in{args.odds}"
    patched_rom = ARTIFACTS / f"{prefix}.gba"

    ARTIFACTS.mkdir(exist_ok=True)
    if not save_path.exists():
        raise SystemExit(f"Expected save file was not found: {save_path}")
    shutil.copyfile(save_path, patched_rom.with_suffix(".sav"))

    patch_env = os.environ.copy()
    patch_env["KIRAPATCH_DEBUG_TRACE_FRLG_GIFT"] = "1"
    if args.trace_primary:
        patch_env["KIRAPATCH_DEBUG_TRACE_PRIMARY"] = "1"
    else:
        patch_env.pop("KIRAPATCH_DEBUG_TRACE_PRIMARY", None)
    if args.trace_starters:
        patch_env["KIRAPATCH_DEBUG_TRACE_FRLG_STARTERS"] = "1"
    else:
        patch_env.pop("KIRAPATCH_DEBUG_TRACE_FRLG_STARTERS", None)
    patch_env["KIRAPATCH_DEBUG_FRLG_STARTER_FILTER"] = args.filter
    if args.primary_skip_mode != "all":
        patch_env["KIRAPATCH_DEBUG_PRIMARY_SKIP_MODE"] = args.primary_skip_mode
    else:
        patch_env.pop("KIRAPATCH_DEBUG_PRIMARY_SKIP_MODE", None)
    if args.disable_secondary_wrappers:
        patch_env["KIRAPATCH_DEBUG_DISABLE_SECONDARY_WRAPPERS"] = "1"
    else:
        patch_env.pop("KIRAPATCH_DEBUG_DISABLE_SECONDARY_WRAPPERS", None)
    if args.skip_gift_direct:
        patch_env["KIRAPATCH_DEBUG_SKIP_GIFT_DIRECT"] = "1"
    else:
        patch_env.pop("KIRAPATCH_DEBUG_SKIP_GIFT_DIRECT", None)

    patch_cmd = [
        "python", str(PATCHER), str(rom),
        "--odds", str(args.odds), "--mode", args.mode,
        "--output", str(patched_rom), "--overwrite-output",
    ]
    patch_result = subprocess.run(patch_cmd, cwd=REPO_ROOT, env=patch_env, check=False)
    if patch_result.returncode != 0:
        return patch_result.returncode

    proc = subprocess.Popen([str(args.mgba), str(patched_rom)], cwd=REPO_ROOT)
    output: dict[str, object] = {
        "case": args.case,
        "odds": args.odds,
        "filter": args.filter,
        "primary_skip_mode": args.primary_skip_mode,
        "disable_secondary_wrappers": args.disable_secondary_wrappers,
        "skip_gift_direct": args.skip_gift_direct,
        "trace_primary": args.trace_primary,
        "trace_starters": args.trace_starters,
        "capture_presses": presses,
        "sample_after": args.sample_after,
        "trace_records": [],
        "mons": [],
        "pid_otid_matches": [],
        "party_matches": [],
        "raw_party_slots": [],
    }

    try:
        time.sleep(args.launch_wait)
        window = gui_harness.pick_window("mgba", pid=proc.pid)
        input_wrapper = gui_harness.pick_input_wrapper("mgba", pid=proc.pid)
        mgba_pid = gui_harness.get_window_pid(window.handle)
        keymap = gui_harness.load_mgba_keymap(gui_harness.MGBA_CONFIG)
        last_input_at = run_input_sequence(window.handle, input_wrapper.handle, keymap, args, presses)
        target = last_input_at + args.sample_after
        while time.perf_counter() < target:
            time.sleep(0.01)
        safe_focus(window.handle)
        for match in find_valid_named_mons_in_process(mgba_pid, nickname):
            mon = parse_mon(match.mon)
            mon["address"] = f"0x{match.absolute_address:016X}"
            output["mons"].append(mon)
        for match in find_party_mons_in_process(mgba_pid, GAME_CODE_BY_CASE[args.case]):
            mon = parse_mon(match.mon)
            mon["address"] = f"0x{match.absolute_address:016X}"
            mon["source"] = "party_slot"
            mon["slot_index"] = match.slot_index
            mon["party_count"] = match.party_count
            output["party_matches"].append(mon)
        for slot in find_raw_party_slots_in_process(mgba_pid, GAME_CODE_BY_CASE[args.case], slot_limit=1):
            output["raw_party_slots"].append(
                parse_raw_party_slot(slot.mon, slot.absolute_address, slot.slot_index, slot.party_count)
            )
        for trace in find_trace_records_in_process(
            mgba_pid,
            DEBUG_TRACE_MAGIC,
            tag_word=DEBUG_TRACE_TAG_GIFT,
            expected_low16=DEBUG_TRACE_ADDR_LOW16,
        ):
            record = parse_trace(trace.blob, trace.absolute_address)
            record["kind"] = "gift"
            output["trace_records"].append(record)
        if args.trace_primary:
            for trace in find_trace_records_in_process(
                mgba_pid,
                DEBUG_TRACE_MAGIC,
                tag_word=DEBUG_TRACE_TAG_PRIMARY,
                expected_low16=DEBUG_TRACE_PRIMARY_ADDR_LOW16,
            ):
                record = parse_trace(trace.blob, trace.absolute_address)
                record["kind"] = "primary"
                output["trace_records"].append(record)
        if args.trace_starters:
            for trace in find_trace_records_in_process(
                mgba_pid,
                DEBUG_TRACE_MAGIC,
                tag_word=DEBUG_TRACE_TAG_STARTER_DIRECT,
                expected_low16=DEBUG_TRACE_STARTER_DIRECT_ADDR_LOW16,
            ):
                record = parse_trace(trace.blob, trace.absolute_address)
                record["kind"] = "starter_direct"
                output["trace_records"].append(record)
            for trace in find_trace_records_in_process(
                mgba_pid,
                DEBUG_TRACE_MAGIC,
                tag_word=DEBUG_TRACE_TAG_STARTER_ALT,
                expected_low16=DEBUG_TRACE_STARTER_ALT_ADDR_LOW16,
            ):
                record = parse_trace(trace.blob, trace.absolute_address)
                record["kind"] = "starter_alt"
                output["trace_records"].append(record)
        if not output["mons"]:
            candidate_records = [
                rec for rec in output["trace_records"]
                if rec.get("pid") not in {None, "0x00000000"} and rec.get("otid") not in {None, "0x00000000"}
            ]
            seen_pairs: set[tuple[int, int]] = set()
            for rec in candidate_records:
                mon_pid = int(str(rec["pid"]), 16)
                mon_otid = int(str(rec["otid"]), 16)
                key = (mon_pid, mon_otid)
                if key in seen_pairs:
                    continue
                seen_pairs.add(key)
                for match in find_valid_mons_by_pid_otid_in_process(mgba_pid, mon_pid, mon_otid):
                    mon = parse_mon(match.mon)
                    mon["address"] = f"0x{match.absolute_address:016X}"
                    mon["source"] = "pid_otid"
                    output["pid_otid_matches"].append(mon)
        output["correlation"] = summarize_trace_correlations(output)
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

    out_path = args.output or (ARTIFACTS / f"{prefix}_trace.json")
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))
    print(f"trace_json: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
