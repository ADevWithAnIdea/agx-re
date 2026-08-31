#!/usr/bin/env python3
"""EXP-0216 shared helpers.

READ-ONLY over committed artifacts. Never writes into raw/, never writes into
tools/agx-isa/.

Everything here works from the *committed dispatched bytes* of a raw record.
The record's `field` key and `instr` string are treated as UNTRUSTED LABELS:
they are carried through so they can be tested, never used as ground truth.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
EXP = Path(__file__).resolve().parents[1]
WORK = EXP / "work"

# The frozen copies, so a concurrent writer to tools/agx-isa cannot move the
# ground under this analysis mid-run (EXP-0215 §7.6 last bullet).
DB = json.loads((WORK / "db_frozen.json").read_text())
BY_MNEM = {i["mnemonic"]: i for i in DB["instructions"]}
VALIDATION = json.loads((WORK / "validation_frozen.json").read_text())


# ---------------------------------------------------------------- bit helpers
def bits(hexstr: str, start: int, width: int):
    """Decode [start, start+width) LSB-first across the little-endian byte
    string, exactly as db.json/casematrix.set_field define it. Returns None if
    the span runs off the end of the committed bytes."""
    try:
        raw = bytes.fromhex(hexstr)
    except Exception:
        return None
    if (start + width + 7) // 8 > len(raw):
        return None
    v = int.from_bytes(raw, "little")
    return (v >> start) & ((1 << width) - 1)


def match_ok(mnem: str, hexstr: str):
    """True iff `hexstr` satisfies mnemonic's match bits AND is long enough."""
    d = BY_MNEM.get(mnem)
    if d is None:
        return None
    raw = bytes.fromhex(hexstr)
    if len(raw) < d["length"]:
        return False
    v = int.from_bytes(raw[: d["length"]], "little")
    for (s, w, val) in d["match"]:
        if (v >> s) & ((1 << w) - 1) != val:
            return False
    return True


def span_of(mnem: str, field: str):
    d = BY_MNEM.get(mnem)
    if d is None:
        return None
    for f in d["fields"]:
        if f["name"] == field:
            return (f["start"], f["width"])
    return None


def fields_covering(mnem: str, start: int, width: int):
    """Every field of `mnem` whose bit span intersects [start, start+width)."""
    d = BY_MNEM.get(mnem)
    if d is None:
        return []
    out = []
    for f in d["fields"]:
        a0, a1 = f["start"], f["start"] + f["width"]
        b0, b1 = start, start + width
        if a0 < b1 and b0 < a1:
            out.append((f["name"], f["start"], f["width"]))
    return out


# --------------------------------------------------------------- raw scanning
def iter_records(expdir: str, want_instr=None, want_field=None, need_bytes=True):
    """Yield (path, lineno, record) for every JSONL record under
    experiments/<expdir>/raw/ matching the (untrusted) instr/field labels."""
    root = REPO / "experiments" / expdir / "raw"
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in sorted(filenames):
            if not fn.endswith(".jsonl"):
                continue
            p = Path(dirpath) / fn
            rel = str(p.relative_to(REPO))
            with p.open() as fh:
                for i, line in enumerate(fh, 1):
                    line = line.strip()
                    if not line or line[0] != "{":
                        continue
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    if want_instr is not None and r.get("instr") != want_instr:
                        continue
                    if want_field is not None and r.get("field") != want_field:
                        continue
                    if need_bytes and not r.get("bytes"):
                        continue
                    yield rel, i, r


def outcome_of(r):
    o = r.get("outcome")
    if o is None:
        a = r.get("attempts") or []
        if a and isinstance(a[0], dict):
            o = a[0].get("outcome")
    return o


def dump(obj, name):
    p = EXP / "analysis" / name
    p.write_text(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")
    print("wrote", p.relative_to(REPO))
