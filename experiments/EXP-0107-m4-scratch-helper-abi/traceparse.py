#!/usr/bin/env python3
"""Shared parsing for harness/maptrace.c output. Imported by run.py (to build
the gated per-case record), verify.py (selftest fixtures reuse the identical
parse), and analysis/*.py (which additionally wants the raw VA that run.py's
gated payload deliberately omits).

Two representations of the same maptrace capture:
  - GATED (`resource_map_shape`, `bo_content_seq_sha256`): no GPU address
    anywhere. `resource_map_shape` is a (class,size)->count multiset;
    `bo_content_seq_sha256` hashes the FIRST-SEEN-ORDER sequence of
    (class, size, content_sha256) -- ordering by call sequence, never by VA,
    so it is stable even if the allocator places semantically-identical BOs
    at different addresses across processes.
  - RAW (`parse_resource_maps` returns the VA too): for analysis only, never
    fed into a byte-compared gate.
"""
import hashlib
import json
import re
from pathlib import Path

RESOURCE_MAP_RE = re.compile(
    r"RESOURCE_MAP class=(\S+) gpu_va=(0x[0-9a-fA-F]+) size=(0x[0-9a-fA-F]+) "
    r"handle=(\d+) cpu_present=(\d) outcpu_present=(\d)")
ALLBO_DUMP_RE = re.compile(
    r"ALLBO_PREFIX_DUMP gpu_va=(0x[0-9a-fA-F]+) size=(0x[0-9a-fA-F]+) class=(\S+) "
    r"kr=(0x[0-9a-fA-F]+) got=(0x[0-9a-fA-F]+) path=(\S+)")


def parse_resource_maps(log_text):
    """Every RESOURCE_MAP line, in file order, as (class, va, size, handle)."""
    out = []
    for line in log_text.splitlines():
        m = RESOURCE_MAP_RE.match(line)
        if m:
            out.append({"class": m.group(1), "gpu_va": int(m.group(2), 16),
                       "size": int(m.group(3), 16), "handle": int(m.group(4))})
    return out


def resource_map_shape(maps):
    """Address-free (class,size)->count multiset, sorted for determinism."""
    counts = {}
    for m in maps:
        key = (m["class"], m["size"])
        counts[key] = counts.get(key, 0) + 1
    return sorted([{"class": c, "size": s, "count": n} for (c, s), n in counts.items()],
                 key=lambda r: (r["class"], r["size"]))


def parse_allbo_dumps(log_text):
    """ALLBO_PREFIX_DUMP lines, in FILE ORDER (== first-seen/creation order,
    since maptrace.c iterates its append-only bos[] table at dump time)."""
    out = []
    for line in log_text.splitlines():
        m = ALLBO_DUMP_RE.match(line)
        if m:
            out.append({"gpu_va": int(m.group(1), 16), "size": int(m.group(2), 16),
                       "class": m.group(3), "kr": m.group(4), "got": int(m.group(5), 16),
                       "path": m.group(6)})
    return out


def hex_file_content(path):
    """Read a maptrace hex dump (comment line + `off: xx xx ...` lines) back
    to raw bytes."""
    data = bytearray()
    p = Path(path)
    if not p.is_file():
        return b""
    for line in p.read_text().splitlines():
        if line.startswith("#"):
            continue
        if ":" not in line:
            continue
        _, body = line.split(":", 1)
        data.extend(bytes.fromhex("".join(body.split())))
    return bytes(data)


def bo_content_sequence(allbo_dumps, dump_root):
    """[{class,size,content_sha256}] in first-seen order, reading each
    dump's actual bytes from disk (dump_root is the MAPTRACE_DUMP_DIR)."""
    seq = []
    for d in allbo_dumps:
        content = hex_file_content(d["path"])
        seq.append({"class": d["class"], "size": d["size"],
                    "content_sha256": hashlib.sha256(content).hexdigest()})
    return seq


def bo_content_seq_sha256(seq):
    blob = json.dumps(seq, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()
