#!/usr/bin/env python3
from __future__ import annotations
import argparse
import binascii
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
        choices=("auto", "native", "reroll"),
        default="auto",
        help=(
            "Patch strategy: auto (default) picks native for 1/N >= 257 and reroll for "
            "higher rates; native uses vanilla-style threshold compares only; reroll uses "
            "bit-compressed shiny-value compares for higher odds."
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


def build_odds_plan(odds: int, mode: str) -> OddsPlan:
    if mode not in {"auto", "native", "reroll"}:
        raise ValueError(f"Unsupported mode: {mode}")
    if odds <= 0:
        raise ValueError("--odds must be a positive integer.")
    if mode == "native":
        return build_native_plan(odds)
    if mode == "reroll":
        return build_reroll_plan(odds)
    if round(BASE_SHINY_NUMERATOR / odds) <= MAX_NATIVE_THRESHOLD:
        plan = build_native_plan(odds)
        return OddsPlan(
            requested_odds=odds,
            requested_mode="auto",
            applied_mode=plan.applied_mode,
            threshold=plan.threshold,
            effective_bits=plan.effective_bits,
            effective_one_in=plan.effective_one_in,
        )
    plan = build_reroll_plan(odds)
    return OddsPlan(
        requested_odds=odds,
        requested_mode="auto",
        applied_mode=plan.applied_mode,
        threshold=plan.threshold,
        effective_bits=plan.effective_bits,
        effective_one_in=plan.effective_one_in,
    )


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


def patch_data(data: bytearray, spec: RomSpec, plan: OddsPlan) -> list[str]:
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
