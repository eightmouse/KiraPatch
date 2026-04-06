#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from dataclasses import dataclass

from extract_gen3_party_from_state import PARTY_LAYOUTS, encode_name, get_gen3_species, is_valid_gen3_party_mon

KERNEL32 = ctypes.windll.kernel32

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
MEM_COMMIT = 0x1000
PAGE_NOACCESS = 0x01
PAGE_GUARD = 0x100


class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('BaseAddress', ctypes.c_void_p),
        ('AllocationBase', ctypes.c_void_p),
        ('AllocationProtect', wintypes.DWORD),
        ('RegionSize', ctypes.c_size_t),
        ('State', wintypes.DWORD),
        ('Protect', wintypes.DWORD),
        ('Type', wintypes.DWORD),
    ]


@dataclass
class ProcessMonMatch:
    region_base: int
    offset: int
    mon: bytes

    @property
    def absolute_address(self) -> int:
        return self.region_base + self.offset


@dataclass
class ProcessTraceMatch:
    region_base: int
    offset: int
    blob: bytes

    @property
    def absolute_address(self) -> int:
        return self.region_base + self.offset


@dataclass
class ProcessPartyMonMatch:
    region_base: int
    region_size: int
    game_code: str
    slot_index: int
    party_count: int
    mon: bytes

    @property
    def absolute_address(self) -> int:
        layout = PARTY_LAYOUTS[self.game_code]
        party_offset = layout['party'] - 0x02000000
        return self.region_base + party_offset + self.slot_index * 100


@dataclass
class ProcessRawPartySlot:
    region_base: int
    game_code: str
    slot_index: int
    party_count: int
    mon: bytes

    @property
    def absolute_address(self) -> int:
        layout = PARTY_LAYOUTS[self.game_code]
        party_offset = layout['party'] - 0x02000000
        return self.region_base + party_offset + self.slot_index * 100


def open_process(pid: int):
    handle = KERNEL32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not handle:
        raise OSError(f'OpenProcess failed for pid {pid}')
    return handle


def close_process(handle) -> None:
    KERNEL32.CloseHandle(handle)


def iter_readable_regions(handle, min_size: int = 0x1000, max_size: int = 0x4000000):
    query = KERNEL32.VirtualQueryEx
    query.argtypes = (wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t)
    query.restype = ctypes.c_size_t
    address = 0
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(mbi)
    while query(handle, ctypes.c_void_p(address), ctypes.byref(mbi), mbi_size):
        base = int(mbi.BaseAddress or 0)
        size = int(mbi.RegionSize)
        protect = int(mbi.Protect)
        if (
            int(mbi.State) == MEM_COMMIT
            and min_size <= size <= max_size
            and not (protect & PAGE_GUARD)
            and not (protect & PAGE_NOACCESS)
        ):
            yield base, size
        next_address = base + max(size, 0x1000)
        if next_address <= address:
            break
        address = next_address


def read_region(handle, base: int, size: int) -> bytes | None:
    buffer = ctypes.create_string_buffer(size)
    bytes_read = ctypes.c_size_t()
    ok = KERNEL32.ReadProcessMemory(handle, ctypes.c_void_p(base), buffer, size, ctypes.byref(bytes_read))
    if not ok or bytes_read.value == 0:
        return None
    return buffer.raw[:bytes_read.value]


def find_valid_named_mons_in_process(pid: int, nickname: str, *, max_region_size: int = 0x4000000) -> list[ProcessMonMatch]:
    pattern = encode_name(nickname)
    matches: list[ProcessMonMatch] = []
    seen: set[tuple[int, int]] = set()
    handle = open_process(pid)
    try:
        for base, size in iter_readable_regions(handle, max_size=max_region_size):
            blob = read_region(handle, base, size)
            if not blob:
                continue
            cursor = 0
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
                key = (
                    int.from_bytes(mon[0:4], 'little'),
                    int.from_bytes(mon[4:8], 'little'),
                )
                if key in seen:
                    continue
                seen.add(key)
                matches.append(ProcessMonMatch(region_base=base, offset=start, mon=mon))
    finally:
        close_process(handle)
    return matches


def find_valid_mons_by_pid_otid_in_process(
    pid: int,
    mon_pid: int,
    mon_otid: int,
    *,
    max_region_size: int = 0x4000000,
) -> list[ProcessMonMatch]:
    pattern = int(mon_pid & 0xFFFFFFFF).to_bytes(4, 'little') + int(mon_otid & 0xFFFFFFFF).to_bytes(4, 'little')
    matches: list[ProcessMonMatch] = []
    seen_addresses: set[int] = set()
    handle = open_process(pid)
    try:
        for base, size in iter_readable_regions(handle, max_size=max_region_size):
            blob = read_region(handle, base, size)
            if not blob:
                continue
            cursor = 0
            while True:
                index = blob.find(pattern, cursor)
                if index < 0:
                    break
                cursor = index + 1
                start = index
                if start + 100 > len(blob):
                    continue
                mon = blob[start:start + 100]
                if not is_valid_gen3_party_mon(mon):
                    continue
                absolute_address = base + start
                if absolute_address in seen_addresses:
                    continue
                seen_addresses.add(absolute_address)
                matches.append(ProcessMonMatch(region_base=base, offset=start, mon=mon))
    finally:
        close_process(handle)
    return matches


def find_trace_records_in_process(
    pid: int,
    magic_word: int,
    *,
    tag_word: int | None = None,
    record_size: int = 0x40,
    expected_low16: int | None = None,
    max_region_size: int = 0x4000000,
) -> list[ProcessTraceMatch]:
    magic = int(magic_word & 0xFFFFFFFF).to_bytes(4, 'little')
    tag = int(tag_word & 0xFFFFFFFF).to_bytes(4, 'little') if tag_word is not None else None
    matches: list[ProcessTraceMatch] = []
    seen: set[tuple[int, ...]] = set()
    handle = open_process(pid)
    try:
        for base, size in iter_readable_regions(handle, max_size=max_region_size):
            blob = read_region(handle, base, size)
            if not blob:
                continue
            cursor = 0
            while True:
                index = blob.find(magic, cursor)
                if index < 0:
                    break
                cursor = index + 1
                if index + record_size > len(blob):
                    continue
                record = blob[index:index + record_size]
                if tag is not None and record[4:8] != tag:
                    continue
                absolute_address = base + index
                if expected_low16 is not None and (absolute_address & 0xFFFF) != expected_low16:
                    continue
                signature = tuple(int.from_bytes(record[i:i + 4], 'little') for i in range(0, min(record_size, 0x20), 4))
                if signature in seen:
                    continue
                seen.add(signature)
                matches.append(ProcessTraceMatch(region_base=base, offset=index, blob=record))
    finally:
        close_process(handle)
    return matches


def find_party_mons_in_process(
    pid: int,
    game_code: str,
    *,
    species_id: int | None = None,
    max_region_size: int = 0x4000000,
) -> list[ProcessPartyMonMatch]:
    if game_code not in PARTY_LAYOUTS:
        raise ValueError(f'Unsupported Gen 3 game code: {game_code}')
    layout = PARTY_LAYOUTS[game_code]
    party_offset = layout['party'] - 0x02000000
    count_offset = layout['count'] - 0x02000000
    matches: list[ProcessPartyMonMatch] = []
    seen_addresses: set[int] = set()
    handle = open_process(pid)
    try:
        for base, size in iter_readable_regions(handle, min_size=0x40000, max_size=max_region_size):
            blob = read_region(handle, base, size)
            if not blob:
                continue
            if count_offset >= len(blob) or party_offset + 100 > len(blob):
                continue
            party_count = blob[count_offset]
            if not 1 <= party_count <= 6:
                continue
            for slot_index in range(party_count):
                start = party_offset + slot_index * 100
                if start + 100 > len(blob):
                    break
                mon = blob[start:start + 100]
                if not is_valid_gen3_party_mon(mon):
                    continue
                if species_id is not None and get_gen3_species(mon) != species_id:
                    continue
                absolute_address = base + start
                if absolute_address in seen_addresses:
                    continue
                seen_addresses.add(absolute_address)
                matches.append(
                    ProcessPartyMonMatch(
                        region_base=base,
                        region_size=size,
                        game_code=game_code,
                        slot_index=slot_index,
                        party_count=party_count,
                        mon=mon,
                    )
                )
    finally:
        close_process(handle)
    return matches


def find_raw_party_slots_in_process(
    pid: int,
    game_code: str,
    *,
    slot_limit: int = 1,
    max_region_size: int = 0x4000000,
) -> list[ProcessRawPartySlot]:
    if game_code not in PARTY_LAYOUTS:
        raise ValueError(f'Unsupported Gen 3 game code: {game_code}')
    layout = PARTY_LAYOUTS[game_code]
    party_offset = layout['party'] - 0x02000000
    count_offset = layout['count'] - 0x02000000
    matches: list[ProcessRawPartySlot] = []
    seen_addresses: set[int] = set()
    handle = open_process(pid)
    try:
        for base, size in iter_readable_regions(handle, min_size=0x40000, max_size=max_region_size):
            blob = read_region(handle, base, size)
            if not blob:
                continue
            if count_offset >= len(blob):
                continue
            party_count = blob[count_offset]
            if not 0 <= party_count <= 6:
                continue
            slot_count = max(1, min(slot_limit, 6))
            if party_offset + (slot_count * 100) > len(blob):
                continue
            for slot_index in range(slot_count):
                start = party_offset + slot_index * 100
                mon = blob[start:start + 100]
                absolute_address = base + start
                if absolute_address in seen_addresses:
                    continue
                seen_addresses.add(absolute_address)
                matches.append(
                    ProcessRawPartySlot(
                        region_base=base,
                        game_code=game_code,
                        slot_index=slot_index,
                        party_count=party_count,
                        mon=mon,
                    )
                )
    finally:
        close_process(handle)
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description='Scan a live process for valid named Gen 3 mon structs.')
    parser.add_argument('pid', type=int)
    parser.add_argument('nickname')
    parser.add_argument('--max-region-size', type=lambda value: int(value, 0), default=0x4000000)
    args = parser.parse_args()
    matches = find_valid_named_mons_in_process(args.pid, args.nickname, max_region_size=args.max_region_size)
    print(f'matches: {len(matches)}')
    for match in matches:
        pid = int.from_bytes(match.mon[0:4], 'little')
        print(f'0x{match.absolute_address:016X} pid=0x{pid:08X}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
