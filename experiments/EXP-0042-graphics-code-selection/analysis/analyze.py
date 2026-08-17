#!/usr/bin/env python3
"""Reproduce EXP-0042's derived selection/container tables.

The parser reads only DATA-TRACE dumps from our process and machine code proven
byte-identical to the output of our authored MSL. It does not parse or inspect
any Apple executable or Apple-authored helper program.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
HEX_LINE = re.compile(r"^([0-9a-f]{8}):\s+(.*)$")
HEADER = re.compile(r"gpu_va=0x([0-9a-f]+).*size=0x([0-9a-f]+)")
VDM_HEADER = (0x4000002E).to_bytes(4, "little")


@dataclass(frozen=True)
class BO:
    va: int
    size: int
    data: bytes
    path: Path


def load_hex(path: Path) -> BO:
    lines = path.read_text(errors="strict").splitlines()
    match = HEADER.search(lines[0])
    if not match:
        raise ValueError(f"no BO header: {path}")
    chunks = []
    for line in lines[1:]:
        item = HEX_LINE.match(line)
        if item:
            chunks.append(bytes.fromhex(item.group(2).replace(" ", "")))
    return BO(int(match.group(1), 16), int(match.group(2), 16),
              b"".join(chunks), path)


def bo(run: str, dump: int, va: int) -> BO:
    paths = list((RAW / run / "maps" / f"dump{dump:02d}").glob(f"*va{va:x}_*"))
    if len(paths) != 1:
        raise ValueError(f"wanted one va={va:#x} in {run}/dump{dump:02d}, got {paths}")
    return load_hex(paths[0])


def u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 4], "little")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def all_offsets(data: bytes, needle: bytes) -> list[int]:
    result = []
    start = 0
    while True:
        found = data.find(needle, start)
        if found < 0:
            return result
        result.append(found)
        start = found + 1


def own_bytes(path: Path) -> bytes:
    return bytes.fromhex("".join(path.read_text().split()))


def record_for(data: bytes, payload_offset: int, payload_size: int) -> tuple[int, int]:
    """Find the nearest zero-reserved, 0x40-aligned sized record containing payload."""
    for candidate in range(payload_offset & ~0x3F, -1, -0x40):
        size = u32(data, candidate)
        if (size >= 0x40 and size % 0x40 == 0 and
                candidate + size >= payload_offset + payload_size and
                not any(data[candidate + 4:candidate + 0x40])):
            return candidate, size
    raise ValueError(f"no record contains {payload_offset:#x}+{payload_size:#x}")


def stdout_resource(run: str, name: str) -> int:
    text = (RAW / run / "stdout.txt").read_text()
    match = re.search(rf"RESOURCE {re.escape(name)} va=0x([0-9a-f]+)", text)
    if not match:
        raise ValueError(f"missing {name} in {run}")
    return int(match.group(1), 16)


def vdm_records(data: bytes) -> list[int]:
    return all_offsets(data, VDM_HEADER)


def print_multipipe() -> None:
    print("[MULTIPIPE: queue/code window and VS switch token]")
    for run, order, prealloc in (("run_ab_p0", "AB", 0),
                                 ("run_ba_p0", "BA", 0),
                                 ("run_ab_p17", "AB", 17)):
        code = bo(run, 0, 0x10000000000)
        a = bo(run, 0, 0x18000).data
        b = bo(run, 1, 0x18000).data
        print(f"{run} order={order} prealloc={prealloc} code_va={code.va:#x} "
              f"code_sha256={sha(code.data)} vertices={stdout_resource(run, 'vertices'):#x} "
              f"A=(hdr8={u32(a, 8):#x},hdr10={u32(a, 0x10):#x},"
              f"bind={u32(a, 0x1c):#x},token={u32(a, 0x20):#x}) "
              f"B=(hdr8={u32(b, 8):#x},hdr10={u32(b, 0x10):#x},"
              f"bind={u32(b, 0x1c):#x},token={u32(b, 0x20):#x})")

    run = "run_ab_p0"
    sequences = ("A", "B", "AB", "BA", "ABAB", "BABA", "ABBA", "BAAB")
    for dump, sequence in enumerate(sequences):
        data = bo(run, dump, 0x18000).data
        rows = []
        for offset in vdm_records(data):
            pair = (u32(data, offset + 0x1c), u32(data, offset + 0x20))
            rows.append(f"{offset:#x}:h8={u32(data, offset + 8):#x},"
                        f"h10={u32(data, offset + 0x10):#x},pair={pair}")
        print(f"switch_sequence={sequence} records=[{' ; '.join(rows)}]")
    print()


def print_authored_layout() -> None:
    print("[AUTHORED A/B exact matches inside live code BO]")
    for run in ("run_ab_p0", "run_ba_p0", "run_ab_p17"):
        data = bo(run, 0, 0x10000000000).data
        print(f"{run} first_record_offset={u32(data, 0):#x}")
        for name in ("pipeline_a.fragment.main", "pipeline_a.vertex.main",
                     "pipeline_b.fragment.main", "pipeline_b.vertex.main"):
            payload = own_bytes(RAW / "own_shader" / f"{name}.hex")
            hits = all_offsets(data, payload)
            unique = hits[0] if len(hits) == 1 else None
            if unique is None:
                print(f"  {name} bytes={len(payload)} hits={[hex(x) for x in hits]} (not unique)")
                continue
            header, record_size = record_for(data, unique, len(payload))
            cp = own_bytes(RAW / "own_shader" /
                           f"{name.rsplit('.', 1)[0]}.constant_program.hex")
            cp_hits = all_offsets(data[header:header + record_size], cp)
            print(f"  {name} bytes={len(payload)} main={unique:#x} header={header:#x} "
                  f"record_size={record_size:#x} end={header + record_size:#x} "
                  f"constant_program_bytes={len(cp)} cp_rel_hits={[hex(x) for x in cp_hits]}")
    print()


def fs_record_from_selector(data: bytes, selector: int) -> tuple[int, int, int]:
    metadata_header = selector - 0x40
    if u32(data, metadata_header) != 0x80:
        raise ValueError(f"selector {selector:#x} does not address 0x80 record payload")
    for candidate in range(metadata_header - 0x40, -1, -0x40):
        size = u32(data, candidate)
        if size >= 0x40 and size % 0x40 == 0 and candidate + size == metadata_header:
            return candidate, size, metadata_header
    raise ValueError(f"no predecessor for metadata at {metadata_header:#x}")


def print_stage_matrix() -> None:
    print("[STAGE MATRIX: separate VS token and FS relative selector]")
    run = "run_stage_equal"
    code = bo(run, 10, 0x10000000000).data
    rows = ((6, "SS", "small", "small"), (7, "SF", "small", "large"),
            (8, "LS", "large", "small"), (9, "LF", "large", "large"),
            (10, "EA", "small", "equal_a"), (11, "EB", "small", "equal_b"))
    for dump, name, vs, fs in rows:
        vdm = bo(run, dump, 0x18000).data
        pool = bo(run, dump, 0x58000).data
        selector = u32(pool, 8)
        fs_header, fs_size, metadata_header = fs_record_from_selector(code, selector)
        print(f"{name} vs={vs} fs={fs} readback="
              f"{next(line for line in (RAW/run/'stdout.txt').read_text().splitlines() if f'submit={dump}' in line)}")
        print(f"  vdm_h8={u32(vdm, 8):#x} vdm_h10={u32(vdm, 0x10):#x} "
              f"vs_pair=({u32(vdm, 0x1c):#x},{u32(vdm, 0x20):#x}) "
              f"fs_selector={selector:#x} fs_header={fs_header:#x} "
              f"fs_record_size={fs_size:#x} metadata_header={metadata_header:#x} "
              f"formula={fs_header + fs_size + 0x40:#x}")

    ea = own_bytes(RAW / "own_shader_matrix" / "ea.fragment.main.hex")
    eb = own_bytes(RAW / "own_shader_matrix" / "eb.fragment.main.hex")
    ea_cp = own_bytes(RAW / "own_shader_matrix" / "ea.fragment.constant_program.hex")
    eb_cp = own_bytes(RAW / "own_shader_matrix" / "eb.fragment.constant_program.hex")
    print(f"equal_fragment_main bytes={len(ea)} byte_identical={ea == eb} "
          f"sha256={sha(ea)} live_hits={[hex(x) for x in all_offsets(code, ea)]}")
    print(f"equal_fragment_constant_program bytes={len(ea_cp)} "
          f"byte_identical={ea_cp == eb_cp} ea_sha256={sha(ea_cp)} eb_sha256={sha(eb_cp)} "
          f"ea_live_hits={[hex(x) for x in all_offsets(code, ea_cp)]} "
          f"eb_live_hits={[hex(x) for x in all_offsets(code, eb_cp)]}")
    payloads = [code[offset:offset + 0x40] for offset in (0x500, 0x9c0, 0xdc0, 0xfc0)]
    print(f"fs_selector_payloads offsets=0x500,0x9c0,0xdc0,0xfc0 "
          f"all_byte_identical={all(item == payloads[0] for item in payloads)} "
          f"payload_sha256={sha(payloads[0])}")


def main() -> None:
    print_multipipe()
    print_authored_layout()
    print_stage_matrix()


if __name__ == "__main__":
    main()
