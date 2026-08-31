#!/usr/bin/env python3
"""EXP-0216 Q1 test I — what the swept bits ARE, from the register dumps.

For every arm of a suspect instruction in a register-dumping carrier, build the
observed map

    requested value  ->  (register(s) released-on-read, destination value)

and then ask the two pre-registered questions, WITHOUT consulting any name:

  1. Is `released register index == (value >> k)` for a fixed k?  If yes the
     swept bits are an operand REGISTER SELECTOR and k is its shift.
  2. Does the destination move as a PRODUCT of the selected register's seed, as
     a SUM, as a passthrough, or not at all?  A host oracle computes all four
     predictions from the frozen seed table and the arm's own baseline before
     the observed destination is read.

Both are properties of the committed bytes and the committed register dumps.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0216 import REPO, bits, dump, iter_records, outcome_of  # noqa

SEED_I = {0: 10, 1: 21, 2: 34, 3: 47, 4: 58, 5: 65, 6: 71, 7: 83,
          8: 94, 9: 101, 10: 113, 11: 119, 12: 125, 13: 127, 14: 3, 15: 0}
SEED_F = {0: 5.0, 1: 1.5, 2: 3.0, 3: 0.5, 4: 7.0, 5: 9.0, 6: 11.0, 7: 13.0,
          8: 0.25, 9: 18.0, 10: 22.0, 11: 26.0, 12: 30.0, 13: 0.75,
          14: 0.0, 15: 0.0}


def regs_of(r):
    o = r.get("observed") or {}
    for k in ("regs", "post"):
        v = o.get(k)
        if isinstance(v, list) and len(v) >= 16:
            return v
    return None


def pre_of(r):
    o = r.get("observed") or {}
    v = o.get("pre")
    if isinstance(v, list) and len(v) >= 16:
        return v
    return None


def collect(expdir, instr, kind="int"):
    """arm key -> {value: (bytes, regs, outcome, pre)}"""
    out = defaultdict(dict)
    for rel, ln, r in iter_records(expdir, instr, None):
        regs = regs_of(r)
        if regs is None:
            continue
        v = r.get("value")
        if not isinstance(v, int):
            continue
        key = (r.get("field"), r.get("fstart"), r.get("fwidth"),
               r.get("byte_index"), r.get("arm"), r.get("carrier"))
        if v not in out[key]:
            out[key][v] = (r["bytes"], tuple(regs), outcome_of(r),
                           tuple(pre_of(r) or ()), rel, ln)
    return out


def released(regs, pre, seeds):
    base = pre if pre else [seeds.get(i, 0) for i in range(16)]
    return [i for i in range(16)
            if base[i] not in (0,) and regs[i] == 0]


def selector_law(cases, seeds):
    """cases: {value: (bytes, regs, outcome, pre, file, line)}
    Return the best k such that released-register == value>>k."""
    best = None
    for k in range(0, 8):
        hit = tot = 0
        for v, (b, regs, o, pre, f, l) in cases.items():
            rel = released(list(regs), list(pre) if pre else None, seeds)
            if len(rel) != 1:
                continue
            tot += 1
            if rel[0] == (v >> k) & 0xF:
                hit += 1
        if tot >= 8:
            frac = hit / tot
            if best is None or frac > best[1]:
                best = (k, frac, hit, tot)
    return best


def dest_law(cases, seeds, k):
    """With reg = value>>k, does the destination equal seed*C, seed+C, seed?"""
    pts = []
    for v, (b, regs, o, pre, f, l) in cases.items():
        reg = (v >> k) & 0xF
        s = seeds.get(reg)
        if s is None:
            continue
        pts.append((v, reg, s, regs[0]))
    # fit dest = a*seed + b over integer points, using two distinct seeds
    fits = Counter()
    by_seed = defaultdict(set)
    for v, reg, s, d in pts:
        by_seed[s].add(d)
    seeds_seen = sorted(by_seed)
    # collapse: for each seed take the modal destination
    tab = {s: sorted(ds)[len(ds) // 2] for s, ds in by_seed.items()}
    model = None
    ss = [s for s in seeds_seen if s != 0]
    if len(ss) >= 3:
        s1, s2 = ss[0], ss[1]
        d1, d2 = tab[s1], tab[s2]
        if s2 != s1 and (d2 - d1) % (s2 - s1) == 0:
            a = (d2 - d1) // (s2 - s1)
            b = d1 - a * s1
            ok = sum(1 for s in ss if tab[s] == a * s + b)
            model = {"dest == %d*seed + %d" % (a, b): "%d/%d" % (ok, len(ss))}
    return {"seed_to_dest": tab, "affine_model": model}


def analyse(expdir, instr, kind="int", only_fields=None):
    seeds = SEED_I if kind == "int" else SEED_F
    arms = collect(expdir, instr, kind)
    res = []
    for key, cases in sorted(arms.items(), key=lambda kv: str(kv[0])):
        fname = key[0]
        if only_fields and fname not in only_fields:
            continue
        if len(cases) < 8:
            continue
        law = selector_law(cases, seeds)
        entry = {"exp": expdir, "instr": instr, "arm_key": list(key),
                 "n_values": len(cases),
                 "selector_law": None, "dest_law": None,
                 "sample": []}
        if law and law[1] > 0.9:
            entry["selector_law"] = {
                "reg == (value>>%d)&0xF" % law[0]: "%d/%d" % (law[2], law[3])}
            entry["dest_law"] = dest_law(cases, seeds, law[0])
        for v in sorted(cases)[:8]:
            b, regs, o, pre, f, l = cases[v]
            entry["sample"].append({
                "value": v, "bytes": b, "dest": regs[0],
                "released": released(list(regs), list(pre) if pre else None, seeds),
                "outcome": o, "file": f, "line": l})
        res.append(entry)
    return res


if __name__ == "__main__":
    out = []
    out += analyse("EXP-0154-g17p-emit-alu", "imad", "int")
    out += analyse("EXP-0154-g17p-emit-alu", "iminmax", "int")
    out += analyse("EXP-0154-g17p-emit-alu", "falu3", "float")
    out += analyse("EXP-0154-g17p-emit-alu", "falu3_ext", "float")
    out += analyse("EXP-0154-g17p-emit-alu", "shift_amt_move", "int")
    out += analyse("EXP-0154-g17p-emit-alu", "mov_zext16", "int")
    dump(out, "q1_identity_0154.json")
    for e in out:
        print(e["instr"], e["arm_key"][0], e["arm_key"][1:3], e["n_values"],
              e["selector_law"], (e["dest_law"] or {}).get("affine_model"))
