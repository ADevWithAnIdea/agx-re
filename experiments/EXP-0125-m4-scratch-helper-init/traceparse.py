#!/usr/bin/env python3
"""Shared parsing for harness/inittrace.c checkpoint dumps. Imported by
run.py (builds the gated per-checkpoint record), verify.py (selftest
fixtures reuse the identical parse shape), and analysis/*.py.

Ground truth for "what BOs exist as of checkpoint N" is NOT the trace log's
running RESOURCE_MAP lines (those are timestamped only by call order, not
bucketed by checkpoint) -- it is the literal file listing under
<dump_dir>/cpNN/allbo/*.hex, which harness/inittrace.c writes by iterating
its own current bos[] table at the instant of that checkpoint's SIGUSR1.
Each file's own header comment line carries (gpu_va, size, class); reading
the directory listing at each checkpoint is therefore a complete, address-
labeled snapshot of that exact moment, with no timestamp-bucketing logic
needed on our side.

CODE_WINDOW_VA is the EXP-0042/EXP-0108-established location of our own
compiled VS/FS/CS machine code (the 4 GiB-aligned window); its PRESENCE and
SIZE at each checkpoint is one of this experiment's two direct H2 probes.
"""
import hashlib
import json
import re
from pathlib import Path

CODE_WINDOW_VA = 0x10000000000  # EXP-0042 / EXP-0108 convention

HDR_RE = re.compile(
    r"^#\s+ALLBO_PREFIX\s+gpu_va=(0x[0-9a-fA-F]+)\s+size=(0x[0-9a-fA-F]+)\s+"
    r"class=(\S+)\s+captured=(0x[0-9a-fA-F]+)")
CHECKPOINT_RE = re.compile(
    r"CHECKPOINT idx=(\d+) mach_time=(\d+) nbo=(\d+) nshared=(\d+)")


def parse_checkpoint_log_lines(log_text):
    """{idx: {"mach_time":int,"nbo":int,"nshared":int}} from inittrace.c's
    own CHECKPOINT lines -- used only as a cross-check against the directory
    listing, never as the primary source of nbo/nshared."""
    out = {}
    for line in log_text.splitlines():
        m = CHECKPOINT_RE.search(line)
        if m:
            idx = int(m.group(1))
            out[idx] = {"mach_time": int(m.group(2)), "nbo": int(m.group(3)),
                       "nshared": int(m.group(4))}
    return out


def _bo_header(path):
    with open(path) as f:
        first = f.readline()
    m = HDR_RE.match(first.strip())
    if not m:
        return None
    return {"gpu_va": int(m.group(1), 16), "size": int(m.group(2), 16),
           "class": m.group(3), "captured": int(m.group(4), 16)}


def checkpoint_snapshot(cp_dir):
    """Read <cp_dir>/allbo/*.hex, return (bo_list, resource_map_shape,
    bo_total_bytes, code_window_present, code_window_size)."""
    allbo = Path(cp_dir) / "allbo"
    bos = []
    if allbo.is_dir():
        for p in sorted(allbo.glob("*.hex")):
            h = _bo_header(p)
            if h:
                bos.append(h)
    counts = {}
    for b in bos:
        key = (b["class"], b["size"])
        counts[key] = counts.get(key, 0) + 1
    shape = sorted([{"class": c, "size": s, "count": n} for (c, s), n in counts.items()],
                   key=lambda r: (r["class"], r["size"]))
    total = sum(b["size"] for b in bos)
    code_bo = next((b for b in bos if b["gpu_va"] == CODE_WINDOW_VA), None)
    return bos, shape, total, (code_bo is not None), (code_bo["size"] if code_bo else None)


def shared_pages_snapshot(cp_dir):
    """Whether cpNN/shared/shared_*_addr0.hex / addr1.hex exist (i.e. a
    best-effort selector-5 CPU-pointer read actually captured bytes)."""
    sdir = Path(cp_dir) / "shared"
    a0 = list(sdir.glob("shared_*_addr0.hex")) if sdir.is_dir() else []
    a1 = list(sdir.glob("shared_*_addr1.hex")) if sdir.is_dir() else []
    return len(a0) > 0, len(a1) > 0


def read_checkpoints_jsonl(path):
    out = []
    p = Path(path)
    if p.is_file():
        for line in p.read_text().splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


def hex_file_bo_bytes(path):
    """Read one <hash>.hex dump (comment + hex-dump body) back to raw bytes,
    for analysis-time content comparisons (never part of the gated schema)."""
    data = bytearray()
    for line in Path(path).read_text().splitlines():
        if line.startswith("#") or ":" not in line:
            continue
        _, body = line.split(":", 1)
        data.extend(bytes.fromhex("".join(body.split())))
    return bytes(data)
