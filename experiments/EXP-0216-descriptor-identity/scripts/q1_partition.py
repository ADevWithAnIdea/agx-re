#!/usr/bin/env python3
"""EXP-0216 Q1 — the half_alu_fma12.ext partition.

`ext` moved from (32,64) = bytes 4..11 to (48,48) = bytes 6..11 (EXP-0212).
EXP-0203 swept it BYTE-WISE, so the committed records split exactly by which
byte each case perturbed relative to its own arm anchor.  Nothing needs to be
adjudicated: the records that touched bytes 6..11 are still `ext`; the ones that
touched bytes 4 and 5 are now sweeps of the fields EXP-0212 carved out.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0216 import dump, fields_covering, iter_records, outcome_of  # noqa


def run(expdir, instr, field):
    per_byte = Counter()
    out_by_byte = {}
    ex = {}
    for rel, ln, r in iter_records(expdir, instr, field):
        a = r.get("anchor")
        bh = r["bytes"]
        if not a or len(a) != len(bh):
            per_byte["no-anchor"] += 1
            continue
        d = [i for i in range(len(bh) // 2) if a[2 * i:2 * i + 2] != bh[2 * i:2 * i + 2]]
        k = d[0] if len(d) == 1 else ("multi" if d else "identical")
        per_byte[k] += 1
        out_by_byte.setdefault(k, Counter())[outcome_of(r)] += 1
        ex.setdefault(k, {"file": rel, "line": ln, "bytes": bh, "anchor": a})
    rows = {}
    for k, n in sorted(per_byte.items(), key=str):
        owners = fields_covering(instr, k * 8, 8) if isinstance(k, int) else None
        rows[str(k)] = {"n_records": n, "fields_now_covering_this_byte": owners,
                        "still_ext": bool(owners and owners[0][0] == field),
                        "outcomes": dict(out_by_byte.get(k, {})),
                        "example": ex.get(k)}
    return {"exp": expdir, "instr": instr, "field": field,
            "declared_span": [32, 64], "current_span": [48, 48],
            "per_swept_byte": rows}


if __name__ == "__main__":
    o = run("EXP-0203-g17p-half-oracle", "half_alu_fma12", "ext")
    dump([o], "q1_partition.json")
    still = sum(v["n_records"] for v in o["per_swept_byte"].values() if v["still_ext"])
    moved = sum(v["n_records"] for k, v in o["per_swept_byte"].items()
                if k.isdigit() and not v["still_ext"])
    print("still ext:", still, " moved to another field:", moved)
    for k, v in o["per_swept_byte"].items():
        print(" byte", k, v["n_records"], v["fields_now_covering_this_byte"],
              "still_ext" if v["still_ext"] else "MOVED")
