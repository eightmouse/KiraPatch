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
        attempts = 65536
    else:
        raw_attempts = math.log1p(-target_p) / math.log1p(-base_p)
        low = max(1, min(65536, int(math.floor(raw_attempts))))
        high = max(1, min(65536, int(math.ceil(raw_attempts))))
        if low == high:
            attempts = low
        else:
            low_p = 1.0 - ((1.0 - base_p) ** low)
            high_p = 1.0 - ((1.0 - base_p) ** high)
            attempts = low if abs(low_p - target_p) <= abs(high_p - target_p) else high

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
    if (hw1 & 0xF800) != 0xF000 or (hw2 & 0xD000) != 0xD000:
        raise ValueError(f"Expected BL at 0x{offset:06X}, found 0x{hw1:04X} 0x{hw2:04X}.")

    s = (hw1 >> 10) & 1
    imm10 = hw1 & 0x03FF
    j1 = (hw2 >> 13) & 1
    j2 = (hw2 >> 11) & 1
    imm11 = hw2 & 0x07FF
    i1 = (~(j1 ^ s)) & 1
    i2 = (~(j2 ^ s)) & 1
    imm25 = (s << 24) | (i1 << 23) | (i2 << 22) | (imm10 << 12) | (imm11 << 1)
    if s:
        imm25 |= ~((1 << 25) - 1)
    return (offset + 4 + imm25) & 0xFFFFFFFF


def encode_thumb_bl(from_addr: int, target_addr: int) -> bytes:
    delta = target_addr - (from_addr + 4)
    if delta % 2 != 0:
        raise ValueError(
            f"BL target alignment error: 0x{from_addr:06X} -> 0x{target_addr:06X}"
        )
    if delta < -(1 << 24) or delta > ((1 << 24) - 2):
        raise ValueError(
            f"BL out of range: 0x{from_addr:06X} -> 0x{target_addr:06X}"
        )

    imm25 = delta & ((1 << 25) - 1)
    s = (imm25 >> 24) & 1
    i1 = (imm25 >> 23) & 1
    i2 = (imm25 >> 22) & 1
    imm10 = (imm25 >> 12) & 0x03FF
    imm11 = (imm25 >> 1) & 0x07FF
    j1 = (~i1 ^ s) & 1
    j2 = (~i2 ^ s) & 1

    hw1 = 0xF000 | (s << 10) | imm10
    hw2 = 0xD000 | (j1 << 13) | (j2 << 11) | imm11
    return hw1.to_bytes(2, "little") + hw2.to_bytes(2, "little")


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


def build_canonical_reroll_hook(
    cave_offset: int,
    rng_target: int,
    rerolls_remaining: int,
    orig_hw0: int,
    orig_hw1: int,
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

    def emit_b(label: str) -> None:
        pos = cur_addr()
        emit_hw(0xE000)
        fixups.append(("b", pos, label, 0))

    emit_hw(0xB5F0)  # push {r4-r7,lr}
    emit_hw(0x0016)  # mov r6,r2
    emit_hw(0x6835)  # ldr r5,[r6]
    emit_ldr_literal(4, "rerolls_lit")

    mark("check")
    emit_hw(0x4648)  # mov r0,r9
    emit_hw(0x6803)  # ldr r3,[r0]
    emit_hw(0x0C29)  # lsr r1,r5,#16
    emit_hw(0x4069)  # eor r1,r5
    emit_hw(0x0C18)  # lsr r0,r3,#16
    emit_hw(0x4058)  # eor r0,r3
    emit_hw(0x4041)  # eor r1,r0
    emit_hw(0x0409)  # lsl r1,r1,#16
    emit_hw(0x0C09)  # lsr r1,r1,#16
    emit_hw(0x2907)  # cmp r1,#7
    emit_b_cond(9, "done")  # bls done
    emit_hw(0x2C00)  # cmp r4,#0
    emit_b_cond(0, "done")  # beq done
    emit_hw(0x3C01)  # subs r4,#1
    hook.extend(encode_thumb_bl(cur_addr(), rng_target))
    emit_hw(0x0405)  # lsl r5,r0,#16
    hook.extend(encode_thumb_bl(cur_addr(), rng_target))
    emit_hw(0x0400)  # lsl r0,r0,#16
    emit_hw(0x0C00)  # lsr r0,r0,#16
    emit_hw(0x4305)  # orr r5,r0
    emit_b("check")

    mark("done")
    emit_hw(0x6035)  # str r5,[r6]
    emit_hw(0x0032)  # mov r2,r6
    emit_hw(orig_hw0)
    emit_hw(orig_hw1)
    emit_hw(0xBDF0)  # pop {r4-r7,pc}

    while len(hook) % 4 != 0:
        emit_hw(0x46C0)  # nop

    mark("rerolls_lit")
    hook.extend((rerolls_remaining & 0xFFFFFFFF).to_bytes(4, "little"))

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
        elif kind == "b":
            hook[idx : idx + 2] = encode_thumb_b(pos, target)
        else:
            raise ValueError(f"Internal hook fixup kind error: {kind}")

    return bytes(hook)


def patch_data_canonical(data: bytearray, spec: RomSpec, plan: OddsPlan) -> list[str]:
    cmp_site = canonical_cmp_site(spec)
    cmp_offset = cmp_site.offset
    hook_callsite = cmp_offset - 0x48
    field0_call = hook_callsite + 4
    field1_call = cmp_offset + 0x3A
    rng_call_1 = cmp_offset - 0x2E
    rng_call_2 = cmp_offset - 0x28
    cave_offset = 0x00F00000

    if hook_callsite - 2 < 0 or field0_call + 4 > len(data):
        raise ValueError("ROM layout too small for canonical reroll hook patch.")

    if cave_offset + 0x100 > len(data):
        raise ValueError("ROM layout too small for canonical reroll code cave.")

    cmp_hw = read_halfword(data, cmp_offset)
    if (cmp_hw & 0xFF00) != 0x2900:
        raise ValueError(
            f"Canonical reroll validation failed at 0x{cmp_offset:06X}: "
            f"expected cmp Rx,#imm (0x29xx), found 0x{cmp_hw:04X}."
        )

    pre_hw = read_halfword(data, hook_callsite - 2)
    if (pre_hw & 0xFF00) != 0xAA00:
        raise ValueError(
            f"Canonical reroll validation failed at 0x{hook_callsite - 2:06X}: "
            f"expected add r2,sp,#imm (0xAAxx), found 0x{pre_hw:04X}."
        )

    orig_hw0 = read_halfword(data, hook_callsite)
    orig_hw1 = read_halfword(data, hook_callsite + 2)
    if orig_hw1 != 0x2100:
        raise ValueError(
            f"Canonical reroll validation failed at 0x{hook_callsite + 2:06X}: "
            f"expected movs r1,#0 (0x2100), found 0x{orig_hw1:04X}."
        )

    set_data_target_0 = decode_thumb_bl_target(data, field0_call)
    set_data_target_1 = decode_thumb_bl_target(data, field1_call)
    if set_data_target_0 != set_data_target_1:
        raise ValueError(
            f"Canonical reroll validation failed: SetMonData BL targets differ "
            f"(0x{set_data_target_0:06X} vs 0x{set_data_target_1:06X})."
        )

    rng_target_1 = decode_thumb_bl_target(data, rng_call_1)
    rng_target_2 = decode_thumb_bl_target(data, rng_call_2)
    if rng_target_1 != rng_target_2:
        raise ValueError(
            f"Canonical reroll validation failed: RNG BL targets differ "
            f"(0x{rng_target_1:06X} vs 0x{rng_target_2:06X})."
        )

    cave = data[cave_offset : cave_offset + 0x100]
    if any(b not in (0x00, 0xFF) for b in cave):
        raise ValueError(
            f"Code cave at 0x{cave_offset:06X} is not blank (not 0x00/0xFF)."
        )

    rerolls_remaining = max(0, plan.reroll_attempts - 1)
    hook = build_canonical_reroll_hook(
        cave_offset=cave_offset,
        rng_target=rng_target_1,
        rerolls_remaining=rerolls_remaining,
        orig_hw0=orig_hw0,
        orig_hw1=orig_hw1,
    )

    data[cave_offset : cave_offset + len(hook)] = hook
    data[hook_callsite : hook_callsite + 4] = encode_thumb_bl(hook_callsite, cave_offset)

    changes = [
        f"0x{hook_callsite:06X}: replaced personality SetMonData args with BL 0x{cave_offset:06X} (canonical reroll hook)",
        f"0x{cave_offset:06X}: wrote {len(hook)}-byte canonical reroll hook "
        f"(reroll_attempts={plan.reroll_attempts}, rng=0x{rng_target_1:06X}, set_data=0x{set_data_target_0:06X})",
    ]
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

