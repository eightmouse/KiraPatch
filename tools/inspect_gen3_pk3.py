#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

NATURES = (
    'Hardy', 'Lonely', 'Brave', 'Adamant', 'Naughty',
    'Bold', 'Docile', 'Relaxed', 'Impish', 'Lax',
    'Timid', 'Hasty', 'Serious', 'Jolly', 'Naive',
    'Modest', 'Mild', 'Quiet', 'Bashful', 'Rash',
    'Calm', 'Gentle', 'Sassy', 'Careful', 'Quirky',
)

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

@dataclass
class Gen3MonCore:
    pid: int
    tid: int
    sid: int
    nickname: str
    nature: str
    shiny_xor: int
    is_shiny: bool
    level: int


def decode_string(raw: bytes) -> str:
    chars = []
    for value in raw:
        if value == 0xFF:
            break
        chars.append(CHARMAP.get(value, '?'))
    return ''.join(chars).strip() or '(empty)'


def parse_gen3_pk3(path: Path) -> Gen3MonCore:
    data = path.read_bytes()
    if len(data) != 100:
        raise ValueError(f'{path} is {len(data)} bytes, expected 100-byte Gen 3 PK3.')

    pid = int.from_bytes(data[0:4], 'little')
    otid = int.from_bytes(data[4:8], 'little')
    tid = otid & 0xFFFF
    sid = (otid >> 16) & 0xFFFF
    shiny_xor = ((pid >> 16) ^ (pid & 0xFFFF) ^ tid ^ sid) & 0xFFFF
    return Gen3MonCore(
        pid=pid,
        tid=tid,
        sid=sid,
        nickname=decode_string(data[8:18]),
        nature=NATURES[pid % 25],
        shiny_xor=shiny_xor,
        is_shiny=shiny_xor < 8,
        level=data[84],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description='Inspect core, trustworthy Gen 3 PK3 shiny fields.')
    parser.add_argument('pk3', nargs='+', type=Path, help='Path(s) to 100-byte Gen 3 .pk3 files')
    args = parser.parse_args()

    for path in args.pk3:
        mon = parse_gen3_pk3(path)
        print(path)
        print(f'  nickname:   {mon.nickname}')
        print(f'  pid:        0x{mon.pid:08X}')
        print(f'  tid/sid:    {mon.tid} / {mon.sid}')
        print(f'  nature:     {mon.nature}')
        print(f'  shiny_xor:  {mon.shiny_xor} -> {"shiny" if mon.is_shiny else "not shiny"}')
        print(f'  level:      {mon.level}')
        print()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
