#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import zlib
from dataclasses import dataclass
from pathlib import Path

STATE_CHUNK = b'gbAs'

# Offsets inside the decompressed mGBA GBA savestate blob.
SEGMENTS = (
    (0x00000, 0x03000000, 0x00008000),  # IWRAM
    (0x08000, 0x04000000, 0x00000400),  # IO
    (0x08400, 0x05000000, 0x00000400),  # Palette RAM
    (0x08800, 0x06000000, 0x00018000),  # VRAM
    (0x20800, 0x07000000, 0x00000400),  # OAM
    (0x21000, 0x02000000, 0x00040000),  # EWRAM
)

PARTY_LAYOUTS = {
    'BPRE': {'party': 0x2024284, 'count': 0x2024029, 'label': 'FireRed'},
    'BPGE': {'party': 0x2024284, 'count': 0x2024029, 'label': 'LeafGreen'},
    'BPEE': {'party': 0x20244EC, 'count': 0x20244E9, 'label': 'Emerald'},
    'AXVE': {'party': 0x3004360, 'count': 0x3004350, 'label': 'Ruby'},
    'AXPE': {'party': 0x3004360, 'count': 0x3004350, 'label': 'Sapphire'},
}

CHARMAP = {
    0xFF: '',
    0x00: ' ',
}
for index, ch in enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZ', start=0xBB):
    CHARMAP[index] = ch
for index, ch in enumerate('abcdefghijklmnopqrstuvwxyz', start=0xD5):
    CHARMAP[index] = ch
for index, ch in enumerate('0123456789', start=0xA1):
    CHARMAP[index] = ch
CHARMAP.update({
    0xAB: '!', 0xAC: '?', 0xAD: '.', 0xAE: '-', 0xB8: ',', 0xB4: "'",
    0xB5: 'M', 0xB6: 'F', 0xB7: '$', 0xBA: '/', 0x5B: '%',
})
ENCODE_MAP = {value: key for key, value in CHARMAP.items() if value}
SUBSTRUCT_ORDERS = (
    (0, 1, 2, 3), (0, 1, 3, 2), (0, 2, 1, 3), (0, 3, 1, 2), (0, 2, 3, 1), (0, 3, 2, 1),
    (1, 0, 2, 3), (1, 0, 3, 2), (2, 0, 1, 3), (3, 0, 1, 2), (2, 0, 3, 1), (3, 0, 2, 1),
    (1, 2, 0, 3), (1, 3, 0, 2), (2, 1, 0, 3), (3, 1, 0, 2), (2, 3, 0, 1), (3, 2, 0, 1),
    (1, 2, 3, 0), (1, 3, 2, 0), (2, 1, 3, 0), (3, 1, 2, 0), (2, 3, 1, 0), (3, 2, 1, 0),
)


@dataclass
class ExtractedParty:
    game_code: str
    title: str
    party_count: int
    mons: list[bytes]


def load_state_blob(path: Path) -> bytes:
    data = path.read_bytes()
    chunk_offset = data.find(STATE_CHUNK)
    if chunk_offset < 0:
        raise ValueError(f'{path} does not contain an mGBA gbAs chunk.')
    return zlib.decompress(data[chunk_offset + len(STATE_CHUNK):])


def detect_game(blob: bytes) -> tuple[str, str]:
    header = blob[:128]
    match = re.search(rb'POKEMON[^\x00]*?(AXPE|AXVE|BPEE|BPRE|BPGE)', header)
    if not match:
        raise ValueError('Unable to detect supported Gen 3 game code from savestate header.')
    code = match.group(1).decode('ascii')
    title = header[header.find(b'POKEMON'):match.end()].decode('ascii', errors='ignore')
    return code, title


def emu_addr_to_offset(address: int) -> int:
    for file_offset, base_addr, size in SEGMENTS:
        if base_addr <= address < base_addr + size:
            return file_offset + (address - base_addr)
    raise ValueError(f'Unsupported address 0x{address:08X} for this savestate mapper.')


def decrypt_gen3_box_data(mon: bytes) -> bytes | None:
    if len(mon) != 100:
        return None
    pid = int.from_bytes(mon[0:4], 'little')
    otid = int.from_bytes(mon[4:8], 'little')
    if pid == 0 or otid == 0:
        return None
    checksum = int.from_bytes(mon[28:30], 'little')
    key = pid ^ otid
    encrypted = [mon[32 + index * 12: 32 + (index + 1) * 12] for index in range(4)]
    decrypted = []
    for chunk in encrypted:
        out = bytearray()
        for index in range(0, 12, 4):
            word = int.from_bytes(chunk[index:index + 4], 'little') ^ key
            out.extend(word.to_bytes(4, 'little'))
        decrypted.append(bytes(out))
    ordered = [b''] * 4
    for src_index, dst_index in enumerate(SUBSTRUCT_ORDERS[pid % 24]):
        ordered[dst_index] = decrypted[src_index]
    data = b''.join(ordered)
    total = sum(int.from_bytes(data[index:index + 2], 'little') for index in range(0, 48, 2)) & 0xFFFF
    if total != checksum:
        return None
    return data


def is_valid_gen3_party_mon(mon: bytes) -> bool:
    if len(mon) != 100:
        return False
    level = mon[84]
    if not 1 <= level <= 100:
        return False
    data = decrypt_gen3_box_data(mon)
    if data is None:
        return False
    species = int.from_bytes(data[0:2], 'little')
    if species == 0:
        return False
    exp = int.from_bytes(data[4:8], 'little')
    friendship = data[9]
    if exp == 0 and friendship == 0:
        return False
    return True


def get_gen3_species(mon: bytes) -> int | None:
    data = decrypt_gen3_box_data(mon)
    if data is None or len(data) < 2:
        return None
    return int.from_bytes(data[0:2], 'little')


def encode_name(name: str) -> bytes:
    raw = bytearray()
    for ch in name.upper():
        if ch not in ENCODE_MAP:
            raise ValueError(f'Unsupported character {ch!r} in nickname search.')
        raw.append(ENCODE_MAP[ch])
    raw.append(0xFF)
    return bytes(raw)


def find_valid_named_mons(blob: bytes, nickname: str) -> list[tuple[int, bytes]]:
    pattern = encode_name(nickname)
    matches: list[tuple[int, bytes]] = []
    cursor = 0
    seen: set[tuple[int, int]] = set()
    while True:
        index = blob.find(pattern, cursor)
        if index < 0:
            break
        cursor = index + 1
        start = index - 8
        if start < 0 or start + 100 > len(blob):
            continue
        mon = blob[start:start + 100]
        if not is_valid_gen3_party_mon(mon):
            continue
        pid = int.from_bytes(mon[0:4], 'little')
        otid = int.from_bytes(mon[4:8], 'little')
        key = (pid, otid)
        if key in seen:
            continue
        seen.add(key)
        matches.append((start, mon))
    return matches


def extract_party(path: Path) -> ExtractedParty:
    blob = load_state_blob(path)
    game_code, title = detect_game(blob)
    if game_code not in PARTY_LAYOUTS:
        raise ValueError(f'Unsupported game code {game_code!r} in {path}.')
    layout = PARTY_LAYOUTS[game_code]
    count_offset = emu_addr_to_offset(layout['count'])
    party_offset = emu_addr_to_offset(layout['party'])
    party_count = blob[count_offset]
    mons = []
    for index in range(party_count):
        start = party_offset + index * 100
        mon = blob[start:start + 100]
        if is_valid_gen3_party_mon(mon):
            mons.append(mon)
    return ExtractedParty(game_code=game_code, title=title, party_count=party_count, mons=mons)


def default_output_dir(state_path: Path) -> Path:
    return state_path.parent / f'{state_path.stem}_party'


def write_mons(mons: list[bytes], out_dir: Path, prefix: str = 'party') -> None:
    for index, mon in enumerate(mons, start=1):
        pid = int.from_bytes(mon[0:4], 'little')
        out_path = out_dir / f'{index:02d}_{prefix}_0x{pid:08X}.pk3'
        out_path.write_bytes(mon)
        print(f'  wrote {out_path}')


def main() -> int:
    parser = argparse.ArgumentParser(description='Extract supported Gen 3 Pokemon directly from an mGBA savestate.')
    parser.add_argument('state', type=Path, help='Path to an mGBA savestate (.ss1, .ss2, etc.)')
    parser.add_argument('--output-dir', type=Path, help='Directory for extracted .pk3 files')
    parser.add_argument('--nickname', help='Optional exact nickname/species search to find valid mon structs anywhere in the state')
    args = parser.parse_args()

    blob = load_state_blob(args.state)
    game_code, title = detect_game(blob)
    out_dir = args.output_dir or default_output_dir(args.state)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f'state:      {args.state}')
    print(f'game:       {title} ({game_code})')

    if args.nickname:
        matches = find_valid_named_mons(blob, args.nickname)
        print(f'nickname:   {args.nickname}')
        print(f'matches:    {len(matches)}')
        write_mons([mon for _, mon in matches], out_dir, prefix=args.nickname.upper())
        return 0

    if game_code not in PARTY_LAYOUTS:
        raise ValueError(f'Unsupported game code {game_code!r} in {args.state}.')
    layout = PARTY_LAYOUTS[game_code]
    count_offset = emu_addr_to_offset(layout['count'])
    party_offset = emu_addr_to_offset(layout['party'])
    party_count = blob[count_offset]
    print(f'party_count:{party_count}')
    mons = []
    for index in range(party_count):
        start = party_offset + index * 100
        mon = blob[start:start + 100]
        if is_valid_gen3_party_mon(mon):
            mons.append(mon)
    write_mons(mons, out_dir)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
