#!/usr/bin/env python3
from __future__ import annotations

import struct
from pathlib import Path

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def read_png_size(data: bytes) -> tuple[int, int]:
    if data[:8] != PNG_SIGNATURE:
        raise ValueError("Input is not a PNG file.")
    if data[12:16] != b"IHDR":
        raise ValueError("PNG is missing an IHDR chunk.")
    return struct.unpack(">II", data[16:24])


def build_ico_from_png(png_path: Path, ico_path: Path) -> None:
    png_bytes = png_path.read_bytes()
    width, height = read_png_size(png_bytes)
    if width != height:
        raise ValueError("ICO source image must be square.")

    width_byte = 0 if width >= 256 else width
    height_byte = 0 if height >= 256 else height
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack(
        "<BBBBHHII",
        width_byte,
        height_byte,
        0,
        0,
        1,
        32,
        len(png_bytes),
        6 + 16,
    )
    ico_path.write_bytes(header + entry + png_bytes)


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    assets_dir = repo_root / "assets"
    build_ico_from_png(assets_dir / "logo.png", assets_dir / "logo.ico")
    print("Wrote assets/logo.ico from assets/logo.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
