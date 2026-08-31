#!/usr/bin/env python3
"""EXP-0216 Q1 — role classifier for a swept span, from register dumps only.

The seed vector is recovered EMPIRICALLY: seed[j] = the modal value of register
j over every case of that carrier (only one or two registers move per case, so
the mode is the untouched seed).  Nothing is read from a harness constant.

For every arm each case is then reduced to two index sets:

    WRITTEN(v)  = { j : vec[j] != seed[j] and vec[j] != 0 }
    RELEASED(v) = { j : seed[j] != 0 and vec[j] == 0 }      (EXP-0154 H3:
                  reading a GPR as a 32-bit source zeroes it)

and the arm is classified by which index set tracks the swept value:

  DST-SELECTOR      WRITTEN index == (value >> k) & 0xF over the sweep
  SRC-SELECTOR      RELEASED index == (value >> k) & 0xF over the sweep
  LIVE-NOT-SELECTOR something moves, no index law
  INERT-IN-CARRIER  nothing moves anywhere -> NO detection power; the arm can
                    not decide operand identity (Gate B), verdict `undecidable`

Both laws are reported when both fire.  The classifier reads `field`/`instr`
only to label its output rows.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0216 import REPO, dump, iter_records, outcome_of, span_of  # noqa

POISON = {0xDEADBEEF, 0xA8A8A8A8, 0x5A5A5A5A}


def obs_vec(r):
    o = r.get("observed") or {}
    for k in ("regs", "post"):
        v = o.get(k)
        if isinstance(v, list) and len(v) >= 16:
            return tuple(v[:16])
    d = o.get("digest")
    if isinstance(d, str) and len(d) >= 128:
        return tuple(int(d[i:i + 8], 16) for i in range(0, 128, 8))
    return None


def law(m, n_cases):
    """m: {value: index}. Return the best (k, hits, total) index law."""
    best = None
    for k in (0, 1, 2, 3):
        hit = sum(1 for v, j in m.items() if j == (v >> k) & 0xF)
        if best is None or hit > best[1]:
            best = (k, hit, len(m))
    if best and best[2] >= 6 and best[1] >= max(6, int(0.75 * best[2])):
        return {"law": "index == (value>>%d)&0xF" % best[0],
                "fit": "%d/%d" % (best[1], best[2])}
    return None


def classify(cases, seed):
    vecs = [c[1] for c in cases.values()]
    if len(set(vecs)) == 1:
        return {"role": "INERT-IN-CARRIER", "n_cases": len(cases),
                "detail": "all %d cases produced one identical register vector"
                          % len(cases)}
    wmap, rmap = {}, {}
    for v, (b, vec, o, pre) in cases.items():
        ref = pre if pre else seed
        w = [j for j in range(16)
             if vec[j] != ref[j] and vec[j] != 0 and vec[j] not in POISON]
        rl = [j for j in range(16) if ref[j] not in (0,) and vec[j] == 0]
        if len(w) == 1:
            wmap[v] = w[0]
        if len(rl) == 1:
            rmap[v] = rl[0]
    lw, lr = law(wmap, len(cases)), law(rmap, len(cases))
    out = {"n_cases": len(cases),
           "n_distinct_vectors": len(set(vecs)),
           "written_law": lw, "released_law": lr,
           "written_map_head": {str(v): wmap[v] for v in sorted(wmap)[:10]},
           "released_map_head": {str(v): rmap[v] for v in sorted(rmap)[:10]}}
    if lr and lw:
        out["role"] = "SRC-SELECTOR+DST-MOVE"
    elif lr:
        out["role"] = "SRC-SELECTOR"
    elif lw:
        out["role"] = "DST-SELECTOR"
    else:
        out["role"] = "LIVE-NOT-SELECTOR"
    return out


def run(expdir, instr):
    arms = defaultdict(dict)
    allvecs = defaultdict(list)
    for rel, ln, r in iter_records(expdir, instr, None):
        vec = obs_vec(r)
        v = r.get("value")
        if vec is None or not isinstance(v, int):
            continue
        car = r.get("carrier")
        key = (r.get("field"), r.get("fstart"), r.get("fwidth"),
               r.get("byte_index"), car, r.get("arm"), r.get("layout"))
        pre = (r.get("observed") or {}).get("pre")
        pre = tuple(pre[:16]) if isinstance(pre, list) and len(pre) >= 16 else None
        arms[key].setdefault(v, (r["bytes"], vec, outcome_of(r), pre))
        allvecs[car].append(vec)
    seeds = {}
    for car, vs in allvecs.items():
        seeds[car] = tuple(Counter(v[j] for v in vs).most_common(1)[0][0]
                           for j in range(16))
    out = []
    for key, cases in sorted(arms.items(), key=lambda kv: str(kv[0])):
        if len(cases) < 8:
            continue
        c = classify(cases, seeds[key[4]])
        c.update({"exp": expdir, "instr": instr, "field_key": key[0],
                  "declared_span": [key[1], key[2]], "byte_index": key[3],
                  "carrier": key[4], "arm": key[5], "layout": key[6],
                  "seed_vector": list(seeds[key[4]]),
                  "current_span_of_that_name":
                      span_of(instr, key[0]) if key[0] else None})
        out.append(c)
    return out


TARGETS = [
    ("EXP-0154-g17p-emit-alu", "imad"),
    ("EXP-0154-g17p-emit-alu", "iminmax"),
    ("EXP-0154-g17p-emit-alu", "falu3"),
    ("EXP-0154-g17p-emit-alu", "falu3_ext"),
    ("EXP-0154-g17p-emit-alu", "shift_amt_move"),
    ("EXP-0154-g17p-emit-alu", "mov_zext16"),
    ("EXP-0160-g17p-last-field", "iminmax"),
    ("EXP-0161-g17p-carry-fspecial", "fspecial"),
    ("EXP-0161-g17p-carry-fspecial", "mov_zext16"),
    ("EXP-0169-g17p-rerecord", "half_alu"),
    ("EXP-0169-g17p-rerecord", "reg_move_cb"),
    ("EXP-0180-g17p-halfalu-rerecord", "half_alu_ext8"),
    ("EXP-0180-g17p-halfalu-rerecord", "half_alu_fma12"),
    ("EXP-0203-g17p-half-oracle", "half_alu_fma12"),
]

if __name__ == "__main__":
    out = []
    for e, i in TARGETS:
        out += run(e, i)
    dump(out, "q1_roles.json")
    for c in out:
        print(f"{c['exp'][:22]:22s} {c['instr']:15s} {str(c['field_key'])[:14]:14s} "
              f"{str(c['declared_span']):11s}->{str(c['current_span_of_that_name']):9s} "
              f"n={c['n_cases']:4d} {c['role']:22s} "
              f"W:{(c.get('written_law') or {}).get('law','-')} {(c.get('written_law') or {}).get('fit','')} "
              f"R:{(c.get('released_law') or {}).get('law','-')} {(c.get('released_law') or {}).get('fit','')}")
