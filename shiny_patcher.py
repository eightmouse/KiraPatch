#!/usr/bin/env python3
from __future__ import annotations
import argparse
import binascii
import math
from dataclasses import dataclass

from pathlib import Path
from typing import Iterable

@dataclass(frozen=True)
class PatchSite:
    offset: int
    default_value: int
    kind: str  # "odds" or "odds_minus_one"


@dataclass(frozen=True)
class RomSpec:
    name: str
    game_code: str
    revision: str
    crc32: int
    patch_sites: tuple[PatchSite, ...]


ROM_SPECS: tuple[RomSpec, ...] = (
    RomSpec(
        name="Pokemon Ruby Version (USA, Europe)",
        game_code="AXVE",
        revision="0",
        crc32=0xF0815EE7,
        patch_sites=(
            PatchSite(0x03A8A2, 0x07, "odds_minus_one"),
            PatchSite(0x040968, 0x07, "odds_minus_one"),
            PatchSite(0x0409DE, 0x07, "odds_minus_one"),
            PatchSite(0x040CF4, 0x07, "odds_minus_one"),
            PatchSite(0x14187A, 0x07, "odds_minus_one"),
        ),
    ),
    RomSpec(
        name="Pokemon Ruby Version (USA, Europe) (Rev 1)",
        game_code="AXVE",
        revision="1",
        crc32=0x61641576,
        patch_sites=(
            PatchSite(0x03A8A2, 0x07, "odds_minus_one"),
            PatchSite(0x040988, 0x07, "odds_minus_one"),
            PatchSite(0x0409FE, 0x07, "odds_minus_one"),
            PatchSite(0x040D14, 0x07, "odds_minus_one"),
            PatchSite(0x14189A, 0x07, "odds_minus_one"),
        ),
    ),
    RomSpec(
        name="Pokemon Ruby Version (USA, Europe) (Rev 2)",
        game_code="AXVE",
        revision="2",
        crc32=0xAEAC73E6,
        patch_sites=(
            PatchSite(0x03A8A2, 0x07, "odds_minus_one"),
            PatchSite(0x040988, 0x07, "odds_minus_one"),
            PatchSite(0x0409FE, 0x07, "odds_minus_one"),
            PatchSite(0x040D14, 0x07, "odds_minus_one"),
            PatchSite(0x14189A, 0x07, "odds_minus_one"),
        ),
    ),
    RomSpec(
        name="Pokemon Sapphire Version (USA, Europe)",
        game_code="AXPE",
        revision="0",
        crc32=0x554DEDC4,
        patch_sites=(
            PatchSite(0x03A8A2, 0x07, "odds_minus_one"),
            PatchSite(0x040968, 0x07, "odds_minus_one"),
            PatchSite(0x0409DE, 0x07, "odds_minus_one"),
            PatchSite(0x040CF4, 0x07, "odds_minus_one"),
            PatchSite(0x14187A, 0x07, "odds_minus_one"),
        ),
    ),
    RomSpec(
        name="Pokemon Sapphire Version (Europe) (Rev 1)",
        game_code="AXPE",
        revision="1",
        crc32=0xBAFEDAE5,
        patch_sites=(
            PatchSite(0x03A8A2, 0x07, "odds_minus_one"),
            PatchSite(0x040988, 0x07, "odds_minus_one"),
            PatchSite(0x0409FE, 0x07, "odds_minus_one"),
            PatchSite(0x040D14, 0x07, "odds_minus_one"),
            PatchSite(0x14189A, 0x07, "odds_minus_one"),
        ),
    ),
    RomSpec(
        name="Pokemon Sapphire Version (USA, Europe) (Rev 2)",
        game_code="AXPE",
        revision="2",
        crc32=0x9CC4410E,
        patch_sites=(
            PatchSite(0x03A8A2, 0x07, "odds_minus_one"),
            PatchSite(0x040988, 0x07, "odds_minus_one"),
            PatchSite(0x0409FE, 0x07, "odds_minus_one"),
            PatchSite(0x040D14, 0x07, "odds_minus_one"),
            PatchSite(0x14189A, 0x07, "odds_minus_one"),
        ),
    ),
    RomSpec(
        name="Pokemon FireRed Version (USA)",
        game_code="BPRE",
        revision="0",
        crc32=0xDD88761C,
        patch_sites=(
            PatchSite(0x104A24, 0x08, "odds"),
            PatchSite(0x03DB5E, 0x07, "odds_minus_one"),
            PatchSite(0x044120, 0x07, "odds_minus_one"),
            PatchSite(0x044196, 0x07, "odds_minus_one"),
            PatchSite(0x0444B0, 0x07, "odds_minus_one"),
            PatchSite(0x0F1776, 0x07, "odds_minus_one"),
        ),
    ),
    RomSpec(
        name="Pokemon FireRed Version (USA, Europe) (Rev 1)",
        game_code="BPRE",
        revision="1",
        crc32=0x84EE4776,
        patch_sites=(
            PatchSite(0x104A9C, 0x08, "odds"),
            PatchSite(0x03DB72, 0x07, "odds_minus_one"),
            PatchSite(0x044134, 0x07, "odds_minus_one"),
            PatchSite(0x0441AA, 0x07, "odds_minus_one"),
            PatchSite(0x0444C4, 0x07, "odds_minus_one"),
            PatchSite(0x0F17EE, 0x07, "odds_minus_one"),
        ),
    ),
    RomSpec(
        name="Pokemon LeafGreen Version (USA)",
        game_code="BPGE",
        revision="0",
        crc32=0xD69C96CC,
        patch_sites=(
            PatchSite(0x1049FC, 0x08, "odds"),
            PatchSite(0x03DB5E, 0x07, "odds_minus_one"),
            PatchSite(0x044120, 0x07, "odds_minus_one"),
            PatchSite(0x044196, 0x07, "odds_minus_one"),
            PatchSite(0x0444B0, 0x07, "odds_minus_one"),
            PatchSite(0x0F174E, 0x07, "odds_minus_one"),
        ),
    ),
    RomSpec(
        name="Pokemon LeafGreen Version (USA, Europe) (Rev 1)",
        game_code="BPGE",
        revision="1",
        crc32=0xDAFFECEC,
        patch_sites=(
            PatchSite(0x104A74, 0x08, "odds"),
            PatchSite(0x03DB72, 0x07, "odds_minus_one"),
            PatchSite(0x044134, 0x07, "odds_minus_one"),
            PatchSite(0x0441AA, 0x07, "odds_minus_one"),
            PatchSite(0x0444C4, 0x07, "odds_minus_one"),
            PatchSite(0x0F17C6, 0x07, "odds_minus_one"),
        ),
    ),
    RomSpec(
        name="Pokemon Emerald Version (USA, Europe)",
        game_code="BPEE",
        revision="0",
        crc32=0x1F1C08FB,
        patch_sites=(
            PatchSite(0x031910, 0x08, "odds"),
            PatchSite(0x0C0EE0, 0x08, "odds"),
            PatchSite(0x1346AC, 0x08, "odds"),
            PatchSite(0x067C56, 0x07, "odds_minus_one"),
            PatchSite(0x06E76C, 0x07, "odds_minus_one"),
            PatchSite(0x06E7E2, 0x07, "odds_minus_one"),
            PatchSite(0x06EBE4, 0x07, "odds_minus_one"),
            PatchSite(0x172F46, 0x07, "odds_minus_one"),
        ),
    ),
)

ROM_SPECS_BY_CRC = {spec.crc32: spec for spec in ROM_SPECS}

BASE_SHINY_NUMERATOR = 65536
BASE_THRESHOLD = 8
MAX_NATIVE_THRESHOLD = 255
MAX_CANONICAL_REROLL_ATTEMPTS = 1024
THUMB_BL_MIN_DELTA = -0x400000
THUMB_BL_MAX_DELTA = 0x3FFFFE
ROM_EXEC_BASE = 0x08000000


@dataclass(frozen=True)
class OddsPlan:
    requested_odds: int
    requested_mode: str
    applied_mode: str
    threshold: int
    effective_bits: int
    effective_one_in: float
    bonus_threshold8: int = 0
    reroll_attempts: int = 1
    reroll_capped: bool = False



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Patch Gen 3 Pokemon ROM shiny odds safely using CRC32 ROM detection "
            "and strict vanilla-byte validation."
        )
    )
    parser.add_argument(
        "input_rom",
        nargs="?",
        type=Path,
        help="Path to input .gba ROM (optional in guided mode)",
    )
    parser.add_argument(
        "--odds",
        type=int,
        metavar="N",
        help=(
            "Desired shiny rate as '1 in N'. Example: 4096 gives approximately 1/4096 "
            "(base game is 8192)."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("auto", "canonical", "legacy", "native", "reroll"),
        default="auto",
        help=(
            "Patch strategy: auto/canonical/reroll uses canonical PID rerolls (PKHeX-valid shinies). "
            "legacy/native keep the older visual-check threshold patch behavior."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output path for patched ROM. Defaults to <input_stem>.shiny_1inN.gba",
    )
    parser.add_argument(
        "--overwrite-output",
        action="store_true",
        help="Allow overwriting an existing output file.",
    )
    parser.add_argument(
        "--guided",
        action="store_true",
        help="Interactive wizard mode: scan a folder for ROMs and guide patching.",
    )
    parser.add_argument(
        "--folder",
        type=Path,
        default=Path.cwd(),
        help="Folder to scan in guided mode (default: current directory).",
    )
    return parser.parse_args()


def crc32_of_file(path: Path) -> int:
    crc = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            crc = binascii.crc32(chunk, crc)
    return crc & 0xFFFFFFFF


def threshold_from_one_in_n(denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("--odds must be a positive integer.")
    # Base game is threshold 8 => 1/8192. We round to closest representable threshold.
    threshold = round(BASE_SHINY_NUMERATOR / denominator)
    return max(1, min(MAX_NATIVE_THRESHOLD, threshold))


def native_limit_one_in() -> float:
    return BASE_SHINY_NUMERATOR / MAX_NATIVE_THRESHOLD


def build_native_plan(odds: int) -> OddsPlan:
    threshold = threshold_from_one_in_n(odds)
    if round(BASE_SHINY_NUMERATOR / odds) > MAX_NATIVE_THRESHOLD:
        limit = native_limit_one_in()
        raise ValueError(
            f"--mode native cannot represent 1/{odds}. "
            f"Lowest native denominator is about 1/{limit:.2f}."
        )
    return OddsPlan(
        requested_odds=odds,
        requested_mode="native",
        applied_mode="native",
        threshold=threshold,
        effective_bits=16,
        effective_one_in=BASE_SHINY_NUMERATOR / threshold,
    )


def build_reroll_plan(odds: int) -> OddsPlan:
    if odds <= 0:
        raise ValueError("--odds must be a positive integer.")
    target_p = 1.0 / odds
    best: tuple[float, int, int] | None = None
    for bits in range(1, 17):
        max_threshold = min(MAX_NATIVE_THRESHOLD, (1 << bits))
        ideal_threshold = target_p * (1 << bits)
        seed = int(round(ideal_threshold))
        for threshold in (seed - 1, seed, seed + 1):
            if threshold < 1 or threshold > max_threshold:
                continue
            p = threshold / float(1 << bits)
            error = abs(p - target_p)
            candidate = (error, -bits, threshold)
            if best is None or candidate < best:
                best = candidate
    if best is None:
        raise ValueError("Could not build reroll plan for requested odds.")
    _, neg_bits, threshold = best
    bits = -neg_bits
    return OddsPlan(
        requested_odds=odds,
        requested_mode="reroll",
        applied_mode="reroll",
        threshold=threshold,
        effective_bits=bits,
        effective_one_in=(1 << bits) / float(threshold),
    )


def build_canonical_plan(odds: int, requested_mode: str) -> OddsPlan:
    if odds <= 0:
        raise ValueError("--odds must be a positive integer.")
    if odds > 8192:
        raise ValueError(
            "Canonical reroll mode supports odds from 1/1 up to 1/8192 only."
        )

    base_p = 1.0 / 8192.0
    target_p = 1.0 / float(odds)
    if target_p < base_p:
        raise ValueError(
            "Canonical mode cannot make odds rarer than base 1/8192."
        )

    if target_p >= 1.0:
        uncapped_attempts = BASE_SHINY_NUMERATOR
    else:
        raw_attempts = math.log1p(-target_p) / math.log1p(-base_p)
        low = max(1, min(BASE_SHINY_NUMERATOR, int(math.floor(raw_attempts))))
        high = max(1, min(BASE_SHINY_NUMERATOR, int(math.ceil(raw_attempts))))
        if low == high:
            uncapped_attempts = low
        else:
            low_p = 1.0 - ((1.0 - base_p) ** low)
            high_p = 1.0 - ((1.0 - base_p) ** high)
            uncapped_attempts = low if abs(low_p - target_p) <= abs(high_p - target_p) else high

    attempts = min(uncapped_attempts, MAX_CANONICAL_REROLL_ATTEMPTS)
    reroll_capped = attempts != uncapped_attempts

    effective_p = 1.0 - ((1.0 - base_p) ** attempts)
    effective_one_in = (1.0 / effective_p) if effective_p > 0 else float("inf")

    return OddsPlan(
        requested_odds=odds,
        requested_mode=requested_mode,
        applied_mode="canonical",
        threshold=BASE_THRESHOLD,
        effective_bits=16,
        effective_one_in=effective_one_in,
        bonus_threshold8=0,
        reroll_attempts=attempts,
        reroll_capped=reroll_capped,
    )


def build_odds_plan(odds: int, mode: str) -> OddsPlan:
    if mode not in {"auto", "canonical", "legacy", "native", "reroll"}:
        raise ValueError(f"Unsupported mode: {mode}")
    if mode in {"auto", "canonical", "reroll"}:
        return build_canonical_plan(odds, mode)
    legacy_mode = "native" if mode == "legacy" else mode
    if odds <= 0:
        raise ValueError("--odds must be a positive integer.")
    if legacy_mode == "native":
        return build_native_plan(odds)
    raise ValueError(f"Unsupported legacy mode: {mode}")


def read_halfword(data: bytearray, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def write_halfword(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 2] = value.to_bytes(2, "little")


def is_thumb_lsr_imm(instr: int) -> bool:
    return (instr & 0xF800) == 0x0800


def lsr_imm_amount(instr: int) -> int:
    return (instr >> 6) & 0x1F


def with_lsr_imm_amount(instr: int, amount: int) -> int:
    return (instr & ~0x07C0) | ((amount & 0x1F) << 6)


def is_thumb_ldr_literal(instr: int) -> bool:
    return (instr & 0xF800) == 0x4800


def literal_address_from_ldr(instr_offset: int, instr: int) -> int:
    imm8 = instr & 0xFF
    return ((instr_offset + 4) & ~0x3) + (imm8 * 4)


def patch_reroll_context(
    data: bytearray,
    site_offset: int,
    effective_bits: int,
    seen_literals: set[int],
) -> list[str]:
    changes: list[str] = []
    shift_amount = 32 - effective_bits
    if shift_amount < 16 or shift_amount > 31:
        raise ValueError(
            f"Internal error: invalid shift amount {shift_amount} for reroll mode."
        )

    window_start = max(0, site_offset - 32)
    lsr_sites: list[int] = []
    for offset in range(window_start, site_offset, 2):
        instr = read_halfword(data, offset)
        if is_thumb_lsr_imm(instr) and lsr_imm_amount(instr) == 16:
            lsr_sites.append(offset)
    if len(lsr_sites) < 2:
        raise ValueError(
            f"Reroll mode validation failed near 0x{site_offset:06X}: "
            "could not find two LSR #16 instructions."
        )
    for offset in lsr_sites[-2:]:
        old_instr = read_halfword(data, offset)
        new_instr = with_lsr_imm_amount(old_instr, shift_amount)
        write_halfword(data, offset, new_instr)
        changes.append(
            f"0x{offset:06X}: LSR imm {lsr_imm_amount(old_instr)} -> "
            f"{lsr_imm_amount(new_instr)} (reroll_bits)"
        )

    literal_patched = False
    for offset in range(window_start, site_offset, 2):
        instr = read_halfword(data, offset)
        if not is_thumb_ldr_literal(instr):
            continue
        lit_addr = literal_address_from_ldr(offset, instr)
        if lit_addr < 0 or lit_addr + 4 > len(data):
            continue
        if lit_addr in seen_literals:
            literal_patched = True
            continue
        old_value = int.from_bytes(data[lit_addr : lit_addr + 4], "little")
        if old_value == 0x0000FFFF:
            data[lit_addr : lit_addr + 4] = (0).to_bytes(4, "little")
            seen_literals.add(lit_addr)
            literal_patched = True
            changes.append(
                f"0x{lit_addr:06X}: 0x0000FFFF -> 0x00000000 (reroll_mask_literal)"
            )
    if not literal_patched:
        changes.append(
            f"0x{site_offset:06X}: no local 0x0000FFFF literal found; "
            "kept existing low-half mask path"
        )
    return changes


def decode_thumb_bl_target(data: bytearray, offset: int) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise ValueError(f"BL decode offset out of range: 0x{offset:06X}")
    hw1 = int.from_bytes(data[offset : offset + 2], "little")
    hw2 = int.from_bytes(data[offset + 2 : offset + 4], "little")
    # ARMv4T Thumb BL pair: 11110xxxxxxxxxxx + 11111xxxxxxxxxxx
    if (hw1 & 0xF800) != 0xF000 or (hw2 & 0xF800) != 0xF800:
        raise ValueError(f"Expected Thumb BL at 0x{offset:06X}, found 0x{hw1:04X} 0x{hw2:04X}.")

    imm23 = ((hw1 & 0x07FF) << 12) | ((hw2 & 0x07FF) << 1)
    if hw1 & 0x0400:
        imm23 -= (1 << 23)
    return (offset + 4 + imm23) & 0xFFFFFFFF


def encode_thumb_bl(from_addr: int, target_addr: int) -> bytes:
    delta = target_addr - (from_addr + 4)
    if delta % 2 != 0:
        raise ValueError(
            f"BL target alignment error: 0x{from_addr:06X} -> 0x{target_addr:06X}"
        )
    if delta < THUMB_BL_MIN_DELTA or delta > THUMB_BL_MAX_DELTA:
        raise ValueError(
            f"Thumb BL out of range: 0x{from_addr:06X} -> 0x{target_addr:06X}"
        )

    imm23 = delta & ((1 << 23) - 1)
    hi = (imm23 >> 12) & 0x07FF
    lo = (imm23 >> 1) & 0x07FF
    hw1 = 0xF000 | hi
    hw2 = 0xF800 | lo
    return hw1.to_bytes(2, "little") + hw2.to_bytes(2, "little")


def is_thumb_add_imm0_into_r0(instr: int) -> bool:
    op = (instr >> 11) & 0x1F
    imm3 = (instr >> 6) & 0x07
    rd = instr & 0x07
    return op == 0x03 and imm3 == 0 and rd == 0


def find_code_cave_near(data: bytearray, branch_from: int, required_size: int) -> int:
    if required_size <= 0:
        raise ValueError("Internal error: required code cave size must be positive.")
    if required_size > len(data):
        raise ValueError("ROM too small for canonical reroll hook payload.")

    low = max(0, branch_from + THUMB_BL_MIN_DELTA)
    high = min(len(data) - required_size, branch_from + THUMB_BL_MAX_DELTA)
    low = (low + 3) & ~0x3
    high &= ~0x3
    if high < low:
        raise ValueError("No reachable code cave range for canonical reroll hook.")

    pad_ff = bytes([0xFF]) * required_size
    pad_00 = bytes([0x00]) * required_size

    for off in range(high, low - 1, -4):
        block = bytes(data[off : off + required_size])
        if block == pad_ff or block == pad_00:
            return off

    for off in range(high, low - 1, -4):
        block = data[off : off + required_size]
        if all(b in (0x00, 0xFF) for b in block):
            return off

    raise ValueError(
        f"Could not find a reachable blank code cave near 0x{branch_from:06X} "
        f"(need {required_size} bytes)."
    )


def _match_halfwords(data: bytearray, offset: int, words: tuple[int, ...]) -> bool:
    if offset < 0 or offset + (2 * len(words)) > len(data):
        return False
    return all(read_halfword(data, offset + (i * 2)) == words[i] for i in range(len(words)))


def find_canonical_create_mon_layout(data: bytearray, cmp_offset: int) -> tuple[int, int]:
    # Nearby function prologues are stable in all supported Gen 3 ROMs:
    # - CreateMon:    push {r4-r7,lr}; mov r7,r8; push {r7}; sub sp,#0x1c; mov r8,r0
    # - CreateBoxMon: push {r4-r7,lr}; mov r7,sl; mov r6,sb; mov r5,r8; push {r5-r7}
    create_mon_sig = (0xB5F0, 0x4647, 0xB480, 0xB087, 0x4680)
    create_box_sig = (0xB5F0, 0x4657, 0x464E, 0x4645, 0xB4E0)

    window_start = max(0, cmp_offset - 0x240)
    window_end = min(len(data) - (2 * len(create_mon_sig)), cmp_offset + 0x80)

    create_mon_start = -1
    create_box_start = -1
    for off in range(window_start, window_end + 1, 2):
        if _match_halfwords(data, off, create_mon_sig):
            create_mon_start = off
        if _match_halfwords(data, off, create_box_sig):
            create_box_start = off

    if create_mon_start < 0 or create_box_start < 0:
        raise ValueError(
            f"Canonical reroll validation failed near 0x{cmp_offset:06X}: "
            "could not locate CreateMon/CreateBoxMon prologues."
        )

    create_box_call = -1
    scan_end = min(len(data) - 4, create_mon_start + 0x80)
    for off in range(create_mon_start, scan_end, 2):
        try:
            target = decode_thumb_bl_target(data, off)
        except ValueError:
            continue
        if target == create_box_start:
            create_box_call = off
            break

    if create_box_call < 0:
        raise ValueError(
            f"Canonical reroll validation failed near 0x{cmp_offset:06X}: "
            "could not locate CreateMon -> CreateBoxMon callsite."
        )

    # Expected CreateMon sequence around callsite:
    #   ... mov r0,r8 ; str r3,[sp,#0x18] ; bl <helper>
    #   ... str r4,[sp,#0] ; str r7,[sp,#4] ; str r5,[sp,#8] ; ldr r0,[sp,#0x40] ; str r0,[sp,#0x0c]
    #   mov r0,r8 ; adds r1,r6,#0 ; add r2,sp,#0x10 ; ldrb r2,[r2] ; ldr r3,[sp,#0x18] ; bl CreateBoxMon
    #   mov r0,r8 ; movs r1,#0x38 ; add r2,sp,#0x10 ; bl SetMonData
    pre_helper_sig = (0x4640, 0x9306)
    if not _match_halfwords(data, create_box_call - 0x1C, pre_helper_sig):
        raise ValueError(
            f"Canonical reroll validation failed at 0x{create_box_call - 0x1C:06X}: "
            "unexpected CreateMon pre-helper sequence."
        )
    pre_sig = (0x4640, 0x1C31, 0xAA04, 0x7812, 0x9B06)
    if not _match_halfwords(data, create_box_call - 0x0A, pre_sig):
        raise ValueError(
            f"Canonical reroll validation failed at 0x{create_box_call - 0x0A:06X}: "
            "unexpected CreateMon argument setup sequence."
        )
    arg_reload_sig = (0x9400, 0x9701, 0x9502, 0x9810, 0x9003)
    if not _match_halfwords(data, create_box_call - 0x14, arg_reload_sig):
        raise ValueError(
            f"Canonical reroll validation failed at 0x{create_box_call - 0x14:06X}: "
            "unexpected CreateMon stack-argument reload sequence."
        )

    hook_callsite = create_box_call + 4
    if (
        read_halfword(data, hook_callsite) != 0x4640
        or read_halfword(data, hook_callsite + 2) != 0x2138
        or read_halfword(data, hook_callsite + 4) != 0xAA04
    ):
        raise ValueError(
            f"Canonical reroll validation failed at 0x{hook_callsite:06X}: "
            "unexpected post-CreateBoxMon sequence."
        )

    # Retry from the full pre-helper block so CreateMon replays the same setup as the first attempt.
    retry_target = create_box_call - 0x1C

    return hook_callsite, retry_target

def find_secondary_create_box_wrapper_sites(
    data: bytearray,
    primary_create_box_call: int,
) -> list[tuple[int, int, int, int, tuple[int, ...]]]:
    create_box_start = decode_thumb_bl_target(data, primary_create_box_call)
    wrapper_pre_sig = (0x9500, 0x990E, 0x9101, 0x9302, 0x9910, 0x9103, 0x4649, 0x4642, 0x1C23)
    wrapper_post_sig = (0xB005, 0xBC18, 0x4698, 0x46A1, 0xBCF0, 0xBC01, 0x4700)
    sites: list[tuple[int, int, int, int, tuple[int, ...]]] = []

    for off in range(0, len(data) - 4, 2):
        if off == primary_create_box_call:
            continue
        try:
            target = decode_thumb_bl_target(data, off)
        except ValueError:
            continue
        if target != create_box_start:
            continue
        if not _match_halfwords(data, off - 0x12, wrapper_pre_sig):
            continue
        if not _match_halfwords(data, off + 4, wrapper_post_sig):
            continue
        sites.append((off, off - 0x12, 2, 4, ()))

    return sites

def canonical_cmp_site(spec: RomSpec) -> PatchSite:
    candidates = [s for s in spec.patch_sites if s.kind == "odds_minus_one" and s.default_value == 0x07]
    if not candidates:
        raise ValueError("Canonical patch site not found for this ROM.")
    return min(candidates, key=lambda s: s.offset)


def encode_thumb_b_cond(from_addr: int, target_addr: int, cond_code: int) -> bytes:
    delta = target_addr - (from_addr + 4)
    if delta % 2 != 0:
        raise ValueError(
            f"Conditional branch alignment error: 0x{from_addr:06X} -> 0x{target_addr:06X}"
        )
    if delta < -256 or delta > 254:
        raise ValueError(
            f"Conditional branch out of range: 0x{from_addr:06X} -> 0x{target_addr:06X}"
        )
    imm8 = (delta >> 1) & 0xFF
    hw = 0xD000 | ((cond_code & 0xF) << 8) | imm8
    return hw.to_bytes(2, "little")


def encode_thumb_b(from_addr: int, target_addr: int) -> bytes:
    delta = target_addr - (from_addr + 4)
    if delta % 2 != 0:
        raise ValueError(
            f"Branch alignment error: 0x{from_addr:06X} -> 0x{target_addr:06X}"
        )
    if delta < -2048 or delta > 2046:
        raise ValueError(
            f"Branch out of range: 0x{from_addr:06X} -> 0x{target_addr:06X}"
        )
    imm11 = (delta >> 1) & 0x7FF
    hw = 0xE000 | imm11
    return hw.to_bytes(2, "little")


def build_canonical_create_mon_hook(
    cave_offset: int,
    retry_target: int,
    rerolls_remaining: int,
    counter_sp_word: int,
    restore_r3_sp_word: int,
    resume_halfwords: tuple[int, ...],
) -> bytes:
    hook = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[str, int, str, int]] = []

    def cur_addr() -> int:
        return cave_offset + len(hook)

    def emit_hw(value: int) -> None:
        hook.extend((value & 0xFFFF).to_bytes(2, "little"))

    def mark(name: str) -> None:
        labels[name] = cur_addr()

    def emit_ldr_literal(rd: int, label: str) -> None:
        pos = cur_addr()
        emit_hw(0x4800 | ((rd & 0x7) << 8))
        fixups.append(("ldr", pos, label, rd))

    def emit_b_cond(cond_code: int, label: str) -> None:
        pos = cur_addr()
        emit_hw(0xD000 | ((cond_code & 0xF) << 8))
        fixups.append(("bcond", pos, label, cond_code))

    emit_hw(0x4640)  # mov r0,r8 (struct Pokemon *)
    emit_hw(0x6802)  # ldr r2,[r0]    (PID)
    emit_hw(0x6843)  # ldr r3,[r0,#4] (OTID)
    emit_hw(0x0C11)  # lsr r1,r2,#16
    emit_hw(0x4051)  # eor r1,r2
    emit_hw(0x0C18)  # lsr r0,r3,#16
    emit_hw(0x4058)  # eor r0,r3
    emit_hw(0x4041)  # eor r1,r0
    emit_hw(0x0409)  # lsl r1,r1,#16
    emit_hw(0x0C09)  # lsr r1,r1,#16
    emit_hw(0x2907)  # cmp r1,#7
    emit_b_cond(9, "done")  # bls done (already shiny)

    # Use a caller-specific stack slot so retries persist without clobbering live args.
    emit_hw(0x9800 | (counter_sp_word & 0xFF))  # ldr r0,[sp,#counter_slot]
    emit_hw(0x0C01)  # lsr r1,r0,#16
    emit_ldr_literal(2, "counter_magic_hi")
    emit_hw(0x4291)  # cmp r1,r2
    emit_b_cond(0, "counter_ready")  # beq counter_ready
    emit_ldr_literal(0, "counter_init")
    emit_hw(0x9000 | (counter_sp_word & 0xFF))  # str r0,[sp,#counter_slot]

    mark("counter_ready")
    emit_hw(0x0401)  # lsl r1,r0,#16 (isolates low-16 retry counter)
    emit_hw(0x2900)  # cmp r1,#0
    emit_b_cond(0, "done")  # beq done (no retries left)
    emit_hw(0x3801)  # subs r0,#1
    emit_hw(0x9000 | (counter_sp_word & 0xFF))  # str r0,[sp,#counter_slot]
    emit_hw(0x9B00 | (restore_r3_sp_word & 0xFF))  # ldr r3,[sp,#restore_slot]
    emit_ldr_literal(0, "retry_addr")
    emit_hw(0x4700)  # bx r0 (jump back to caller retry-entry block)

    mark("done")
    for hw in resume_halfwords:
        emit_hw(hw)
    emit_hw(0x4770)  # bx lr

    while len(hook) % 4 != 0:
        emit_hw(0x46C0)  # nop

    mark("retry_addr")
    hook.extend((((ROM_EXEC_BASE + retry_target) | 1) & 0xFFFFFFFF).to_bytes(4, "little"))
    mark("counter_init")
    counter_value = 0xA5A50000 | (max(0, rerolls_remaining) & 0xFFFF)
    hook.extend(counter_value.to_bytes(4, "little"))
    mark("counter_magic_hi")
    hook.extend((0x0000A5A5).to_bytes(4, "little"))

    for kind, pos, label, extra in fixups:
        if label not in labels:
            raise ValueError(f"Internal hook fixup error: missing label {label}")
        target = labels[label]
        idx = pos - cave_offset
        if kind == "ldr":
            pc_aligned = (pos + 4) & ~0x3
            delta = target - pc_aligned
            if delta < 0 or delta % 4 != 0 or delta > 1020:
                raise ValueError(
                    f"Literal load out of range at 0x{pos:06X} -> 0x{target:06X}"
                )
            imm8 = delta // 4
            hw = 0x4800 | ((extra & 0x7) << 8) | imm8
            hook[idx : idx + 2] = hw.to_bytes(2, "little")
        elif kind == "bcond":
            hook[idx : idx + 2] = encode_thumb_b_cond(pos, target, extra)
        else:
            raise ValueError(f"Internal hook fixup kind error: {kind}")

    return bytes(hook)

def patch_data_canonical(data: bytearray, spec: RomSpec, plan: OddsPlan) -> list[str]:
    cmp_site = canonical_cmp_site(spec)
    cmp_offset = cmp_site.offset
    hook_payload_size = 0x100

    cmp_hw = read_halfword(data, cmp_offset)
    if (cmp_hw & 0xFF00) != 0x2900:
        raise ValueError(
            f"Canonical reroll validation failed at 0x{cmp_offset:06X}: "
            f"expected cmp Rx,#imm (0x29xx), found 0x{cmp_hw:04X}."
        )

    primary_hook_callsite, primary_retry_target = find_canonical_create_mon_layout(data, cmp_offset)
    if primary_hook_callsite < 0 or primary_hook_callsite + 4 > len(data):
        raise ValueError("ROM layout too small for canonical reroll hook patch.")

    primary_create_box_call = primary_hook_callsite - 4
    create_box_target = decode_thumb_bl_target(data, primary_create_box_call)
    hook_sites: list[tuple[int, int, int, int, tuple[int, ...]]] = [
        (primary_hook_callsite, primary_retry_target, 5, 6, (0x4640, 0x2138))
    ]
    hook_sites.extend(find_secondary_create_box_wrapper_sites(data, primary_create_box_call))

    changes: list[str] = []
    rerolls_remaining = max(0, plan.reroll_attempts - 1)

    for hook_callsite, retry_target, counter_sp_word, restore_r3_sp_word, resume_halfwords in hook_sites:
        cave_offset = find_code_cave_near(data, hook_callsite, hook_payload_size)
        cave = data[cave_offset : cave_offset + hook_payload_size]
        if any(b not in (0x00, 0xFF) for b in cave):
            raise ValueError(
                f"Code cave at 0x{cave_offset:06X} is not blank (not 0x00/0xFF)."
            )

        if resume_halfwords:
            orig_hw0 = read_halfword(data, hook_callsite)
            orig_hw1 = read_halfword(data, hook_callsite + 2)
            if orig_hw0 != resume_halfwords[0]:
                raise ValueError(
                    f"Canonical reroll validation failed at 0x{hook_callsite:06X}: "
                    f"expected 0x{resume_halfwords[0]:04X}, found 0x{orig_hw0:04X}."
                )
            if orig_hw1 != resume_halfwords[1]:
                raise ValueError(
                    f"Canonical reroll validation failed at 0x{hook_callsite + 2:06X}: "
                    f"expected 0x{resume_halfwords[1]:04X}, found 0x{orig_hw1:04X}."
                )
        else:
            if decode_thumb_bl_target(data, hook_callsite) != create_box_target:
                raise ValueError(
                    f"Canonical reroll validation failed at 0x{hook_callsite:06X}: "
                    "expected CreateBoxMon BL wrapper callsite."
                )

        hook = build_canonical_create_mon_hook(
            cave_offset=cave_offset,
            retry_target=retry_target,
            rerolls_remaining=rerolls_remaining,
            counter_sp_word=counter_sp_word,
            restore_r3_sp_word=restore_r3_sp_word,
            resume_halfwords=resume_halfwords,
        )

        data[cave_offset : cave_offset + len(hook)] = hook
        data[hook_callsite : hook_callsite + 4] = encode_thumb_bl(hook_callsite, cave_offset)

        changes.append(
            f"0x{hook_callsite:06X}: replaced with BL 0x{cave_offset:06X} (canonical reroll hook)"
        )
        changes.append(
            f"0x{cave_offset:06X}: wrote {len(hook)}-byte canonical reroll hook "
            f"(reroll_attempts={plan.reroll_attempts}, retry_target=0x{retry_target:06X})"
        )

    return changes

def detect_site_format(data: bytearray, site: PatchSite) -> str:
    if site.offset >= len(data):
        raise ValueError(f"Offset 0x{site.offset:06X} is outside ROM size.")

    one = data[site.offset]
    if one == site.default_value:
        return "u8"

    if site.offset + 1 < len(data):
        two = int.from_bytes(data[site.offset : site.offset + 2], "little")
        if two == site.default_value:
            return "u16"

    raise ValueError(
        f"Validation failed at 0x{site.offset:06X}: expected vanilla value "
        f"{site.default_value} (u8/u16), found byte=0x{one:02X}."
    )


def patch_data_legacy(data: bytearray, spec: RomSpec, plan: OddsPlan) -> list[str]:
    threshold = plan.threshold
    if threshold < 1 or threshold > MAX_NATIVE_THRESHOLD:
        raise ValueError("Internal error: threshold must be in range 1..255.")

    minus_one = max(0, threshold - 1)
    changes: list[str] = []
    seen_literals: set[int] = set()

    for site in spec.patch_sites:
        new_value = threshold if site.kind == "odds" else minus_one
        fmt = detect_site_format(data, site)

        if fmt == "u8":
            old = data[site.offset]
            data[site.offset] = new_value
        else:
            old = int.from_bytes(data[site.offset : site.offset + 2], "little")
            data[site.offset : site.offset + 2] = new_value.to_bytes(2, "little")

        changes.append(
            f"0x{site.offset:06X}: {old} -> {new_value} ({site.kind}, {fmt})"
        )

        if plan.applied_mode == "reroll" and plan.effective_bits < 16 and site.kind == "odds_minus_one":
            changes.extend(
                patch_reroll_context(
                    data=data,
                    site_offset=site.offset,
                    effective_bits=plan.effective_bits,
                    seen_literals=seen_literals,
                )
            )

    return changes


def patch_data(data: bytearray, spec: RomSpec, plan: OddsPlan) -> list[str]:
    if plan.applied_mode == "canonical":
        return patch_data_canonical(data, spec, plan)
    return patch_data_legacy(data, spec, plan)


def default_output_path(input_path: Path, odds_denominator: int) -> Path:
    return input_path.with_name(f"{input_path.stem}.shiny_1in{odds_denominator}.gba")


def unique_output_path(path: Path) -> Path:
    if not path.exists():
        return path
    for i in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_v{i}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError(f"Could not find unique output name for {path}")


def find_gba_files(folder: Path) -> list[Path]:
    return sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".gba"],
        key=lambda p: p.name.lower(),
    )


def choose_from_list(items: Iterable[str], prompt: str) -> int:
    options = list(items)
    if not options:
        raise ValueError("No options available.")
    while True:
        for i, text in enumerate(options, start=1):
            print(f"  {i}. {text}")
        raw = input(prompt).strip()
        try:
            idx = int(raw)
        except ValueError:
            print("Please enter a number.")
            continue
        if 1 <= idx <= len(options):
            return idx - 1
        print(f"Please choose a number between 1 and {len(options)}.")


def prompt_for_odds() -> int:
    preset_values = [8192, 4096, 2048, 1024]
    while True:
        print("Choose shiny odds (1 in N):")
        for i, n in enumerate(preset_values, start=1):
            print(f"  {i}. 1/{n}")
        print(f"  {len(preset_values) + 1}. Custom")
        choice = input("Select option: ").strip()
        try:
            selected = int(choice)
        except ValueError:
            print("Please enter a number.")
            continue

        if 1 <= selected <= len(preset_values):
            return preset_values[selected - 1]
        if selected == len(preset_values) + 1:
            custom = input("Enter custom N for 1/N: ").strip()
            try:
                odds = int(custom)
            except ValueError:
                print("Custom value must be an integer.")
                continue
            if odds > 0:
                return odds
            print("Custom value must be greater than zero.")
            continue
        print(f"Please choose a number between 1 and {len(preset_values) + 1}.")


def patch_rom(
    input_path: Path,
    odds: int,
    mode: str,
    output_path: Path | None,
    overwrite_output: bool,
    auto_rename_output: bool = False,
) -> int:
    if not input_path.exists():
        print(f"Error: input ROM not found: {input_path}")
        return 1

    crc = crc32_of_file(input_path)
    spec = ROM_SPECS_BY_CRC.get(crc)
    if spec is None:
        print(f"Error: unsupported ROM CRC32 0x{crc:08X}.")
        print("Supported CRC32 values:")
        for s in ROM_SPECS:
            print(f"  - 0x{s.crc32:08X}  {s.name}")
        return 1

    try:
        plan = build_odds_plan(odds, mode)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    output_path = output_path or default_output_path(input_path, odds)
    if output_path.resolve() == input_path.resolve():
        print("Error: output path resolves to input ROM. Refusing in-place overwrite.")
        return 1
    if output_path.exists():
        if overwrite_output:
            pass
        elif auto_rename_output:
            output_path = unique_output_path(output_path)
        else:
            print(
                f"Error: output already exists: {output_path}\n"
                "Use --overwrite-output to replace it."
            )
            return 1

    data = bytearray(input_path.read_bytes())
    try:
        changes = patch_data(data, spec, plan)
    except ValueError as exc:
        print(f"Error: {exc}")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    new_crc = crc32_of_file(output_path)

    print("ROM detected:")
    print(f"  Name:      {spec.name}")
    print(f"  Game code: {spec.game_code}")
    print(f"  Revision:  {spec.revision}")
    print(f"  CRC32:     0x{spec.crc32:08X}")
    print("")
    print("Patch summary:")
    print(f"  Requested odds: 1/{odds}")
    print(f"  Requested mode: {mode}")
    print(f"  Applied mode: {plan.applied_mode}")
    print(f"  Applied threshold: {plan.threshold} (base game is {BASE_THRESHOLD})")
    print(f"  Effective shiny bits: {plan.effective_bits}")
    print(f"  Effective odds: ~1/{plan.effective_one_in:.3f}")
    if plan.applied_mode == "canonical":
        print(f"  Canonical reroll attempts: {plan.reroll_attempts} total PID roll(s)")
        if plan.reroll_capped:
            if plan.requested_odds == 1:
                print(
                    "  Warning: requested 1/1 is capped in canonical mode to avoid severe lag; "
                    f"using {MAX_CANONICAL_REROLL_ATTEMPTS} rolls."
                )
            else:
                print(
                    "  Warning: requested odds required too many PID rerolls; "
                    f"capped at {MAX_CANONICAL_REROLL_ATTEMPTS} rolls for stability."
                )
        print("  Compatibility: PKHeX-canonical shiny logic preserved.")
    elif not (plan.effective_bits == 16 and plan.threshold == BASE_THRESHOLD):
        print("  Compatibility: non-vanilla shiny logic; PKHeX will only flag PID-valid shinies.")
    print(f"  Output ROM: {output_path}")
    print(f"  Output CRC32: 0x{new_crc:08X}")
    print("")
    print("Patched offsets:")
    for line in changes:
        print(f"  - {line}")
    return 0


def run_guided_mode(folder: Path) -> int:
    print("Gen 3 Shiny Odds Patcher (Guided Mode)")
    print(f"Scanning folder: {folder}")

    if not folder.exists() or not folder.is_dir():
        print(f"Error: folder does not exist or is not a directory: {folder}")
        return 1

    gba_files = find_gba_files(folder)
    if not gba_files:
        print("No .gba files found in this folder.")
        return 1

    detections: list[tuple[Path, int, RomSpec | None]] = []
    for rom in gba_files:
        crc = crc32_of_file(rom)
        detections.append((rom, crc, ROM_SPECS_BY_CRC.get(crc)))

    supported = [(p, c, s) for (p, c, s) in detections if s is not None]
    if not supported:
        print("No supported clean ROMs found in this folder.")
        print("Detected .gba files:")
        for path, crc, _ in detections:
            print(f"  - {path.name} (CRC32 0x{crc:08X})")
        return 1

    if len(supported) == 1:
        selected_path, selected_crc, selected_spec = supported[0]
        print(
            f"Found supported ROM: {selected_path.name} "
            f"({selected_spec.name}, CRC32 0x{selected_crc:08X})"
        )
    else:
        print("Multiple supported ROMs found. Choose one:")
        labels = [
            f"{path.name} | {spec.name} | CRC32 0x{crc:08X}"
            for path, crc, spec in supported
        ]
        idx = choose_from_list(labels, "Select ROM number: ")
        selected_path, selected_crc, selected_spec = supported[idx]
        print(
            f"Selected: {selected_path.name} "
            f"({selected_spec.name}, CRC32 0x{selected_crc:08X})"
        )

    odds = prompt_for_odds()
    default_out = default_output_path(selected_path, odds)
    final_out = unique_output_path(default_out) if default_out.exists() else default_out
    print(f"Output will be: {final_out.name}")

    confirm = input("Patch now? [Y/n]: ").strip().lower()
    if confirm in {"n", "no"}:
        print("Cancelled.")
        return 1

    return patch_rom(
        input_path=selected_path,
        odds=odds,
        mode="auto",
        output_path=final_out,
        overwrite_output=False,
        auto_rename_output=True,
    )


def main() -> int:
    args = parse_args()
    if args.guided or args.input_rom is None:
        try:
            return run_guided_mode(args.folder)
        except KeyboardInterrupt:
            print("\nCancelled.")
            return 1

    if args.odds is None:
        print("Error: --odds is required in non-guided mode.")
        return 1

    return patch_rom(
        input_path=args.input_rom,
        odds=args.odds,
        mode=args.mode,
        output_path=args.output,
        overwrite_output=args.overwrite_output,
        auto_rename_output=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())

