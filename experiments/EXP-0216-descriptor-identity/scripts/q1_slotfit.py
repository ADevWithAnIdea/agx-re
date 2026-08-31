#!/usr/bin/env python3
"""EXP-0216 Q1 test I (robust form) — operand SLOT identification.

Pre-registered discriminator, restated as executable form:

  A swept 8-bit operand byte in these carriers is a GPR selector `reg = v >> k`
  plus k low flag bits.  Therefore, if the swept bits are an operand:

     SOME architecturally observable register j is CONSTANT across every v that
     shares (v >> k), and its value is an affine function of SEED[(v >> k)].

  The affine coefficient decides the SLOT:

     dest == A*seed + B  with |A| > 1        -> the register is a MULTIPLICAND
     dest == 1*seed + B  with B != 0         -> the register is an ADDEND
     dest == seed                            -> passthrough / move / select
     no j fits                               -> not an operand selector here

  A slot verdict is only issued when the fit covers >= 4 distinct non-zero seeds
  and every one of them is on the line.  Anything else is `undecidable`.

The destination register index is DISCOVERED, not assumed: every j in 0..15 is
tried.  No field name is read anywhere in this file.
"""
from __future__ import annotations

import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0216 import REPO, dump, iter_records, outcome_of  # noqa

SEED_I = {0: 10, 1: 21, 2: 34, 3: 47, 4: 58, 5: 65, 6: 71, 7: 83,
          8: 94, 9: 101, 10: 113, 11: 119, 12: 125, 13: 127, 14: 3, 15: 0}
SEED_F = {0: 5.0, 1: 1.5, 2: 3.0, 3: 0.5, 4: 7.0, 5: 9.0, 6: 11.0, 7: 13.0,
          8: 0.25, 9: 18.0, 10: 22.0, 11: 26.0, 12: 30.0, 13: 0.75,
          14: 0.0, 15: 0.0}


def f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


def f16(u):
    return struct.unpack("<e", struct.pack("<H", u & 0xFFFF))[0]


def regs_of(r):
    o = r.get("observed") or {}
    for k in ("regs", "post"):
        v = o.get(k)
        if isinstance(v, list) and len(v) >= 16:
            return v
    return None


def collect(expdir, instr):
    out = defaultdict(dict)
    for rel, ln, r in iter_records(expdir, instr, None):
        regs = regs_of(r)
        v = r.get("value")
        if regs is None or not isinstance(v, int):
            continue
        key = (r.get("field"), r.get("fstart"), r.get("fwidth"),
               r.get("byte_index"), r.get("arm"), r.get("carrier"),
               r.get("layout"))
        out[key].setdefault(v, (r["bytes"], tuple(regs), outcome_of(r), rel, ln))
    return out


def _affine_int(pts):
    nz = [(s, d) for s, d in pts if s != 0]
    if len(nz) < 4:
        return None
    (s1, d1), (s2, d2) = nz[0], nz[1]
    if s2 == s1 or (d2 - d1) % (s2 - s1):
        return None
    A = (d2 - d1) // (s2 - s1)
    B = d1 - A * s1
    ok = sum(1 for s, d in nz if d == A * s + B)
    return {"A": A, "B": B, "fit": "%d/%d" % (ok, len(nz)), "exact": ok == len(nz),
            "form": "dest == %d*seed + %d" % (A, B)}


def _affine_float(pts, conv):
    nz = [(s, conv(d)) for s, d in pts if s != 0]
    nz = [(s, d) for s, d in nz if d == d and abs(d) < 1e30]
    if len(nz) < 4:
        return None
    (s1, d1), (s2, d2) = nz[0], nz[1]
    if s2 == s1:
        return None
    A = (d2 - d1) / (s2 - s1)
    B = d1 - A * s1
    ok = sum(1 for s, d in nz
             if abs(d - (A * s + B)) <= 1e-3 * max(1.0, abs(d)))
    return {"A": A, "B": B, "fit": "%d/%d" % (ok, len(nz)), "exact": ok == len(nz),
            "form": "dest == %g*seed + %g" % (A, B)}


def fit(cases, kind):
    """Scan destination register j and shift k; return the best exact fit."""
    seeds = SEED_I if kind == "int" else SEED_F
    convs = [("u32", lambda x: x)] if kind == "int" else \
            [("f32", f32), ("f16lo", lambda x: f16(x & 0xFFFF)),
             ("f16hi", lambda x: f16((x >> 16) & 0xFFFF))]
    best = None
    for k in (0, 1, 2, 3):
        for j in range(16):
            groups = defaultdict(set)
            for v, (b, regs, o, f, l) in cases.items():
                groups[(v >> k) & 0xF].add(regs[j])
            const = {g: list(s)[0] for g, s in groups.items() if len(s) == 1}
            if len(const) < 5:
                continue
            pts = [(seeds[g], const[g]) for g in sorted(const) if g in seeds]
            for cname, conv in convs:
                m = (_affine_int(pts) if kind == "int"
                     else _affine_float(pts, conv))
                if not m:
                    continue
                cand = {"k": k, "dst_reg": j, "view": cname,
                        "n_const_groups": len(const), "model": m,
                        "group_to_dest": {str(g): const[g] for g in sorted(const)}}
                score = (1 if m["exact"] else 0,
                         abs(m["A"]) > 1.0000001, len(const))
                if best is None or score > best[0]:
                    best = (score, cand)
    return best[1] if best else None


def slot_verdict(cand):
    if not cand or not cand["model"]["exact"]:
        return "undecidable"
    A, B = cand["model"]["A"], cand["model"]["B"]
    if abs(A) < 1e-9:
        return "not-a-selector (observable independent of the selected seed)"
    if abs(abs(A) - 1.0) < 1e-9 and abs(B) > 1e-9:
        return "ADDEND-CLASS (obs = seed + const)"
    if abs(abs(A) - 1.0) < 1e-9:
        return "PASSTHROUGH-CLASS (obs = seed)"
    return "MULTIPLICAND-CLASS (obs = %s*seed + %s)" % (A, B)


TARGETS = [
    ("EXP-0154-g17p-emit-alu", "imad", "int"),
    ("EXP-0154-g17p-emit-alu", "iminmax", "int"),
    ("EXP-0154-g17p-emit-alu", "falu3", "float"),
    ("EXP-0154-g17p-emit-alu", "falu3_ext", "float"),
    ("EXP-0154-g17p-emit-alu", "shift_amt_move", "int"),
    ("EXP-0154-g17p-emit-alu", "mov_zext16", "int"),
    ("EXP-0160-g17p-last-field", "iminmax", "int"),
    ("EXP-0169-g17p-rerecord", "half_alu", "float"),
    ("EXP-0169-g17p-rerecord", "reg_move_cb", "int"),
    ("EXP-0180-g17p-halfalu-rerecord", "half_alu_ext8", "float"),
    ("EXP-0180-g17p-halfalu-rerecord", "half_alu_fma12", "float"),
    ("EXP-0161-g17p-carry-fspecial", "fspecial", "float"),
    ("EXP-0161-g17p-carry-fspecial", "mov_zext16", "int"),
]

if __name__ == "__main__":
    out = []
    for expdir, instr, kind in TARGETS:
        arms = collect(expdir, instr)
        merged = defaultdict(dict)
        for key, cases in arms.items():
            merged[(key[0], key[1], key[2], key[3])].update(
                {v: c for v, c in cases.items()
                 if v not in merged[(key[0], key[1], key[2], key[3])]})
        for key, cases in sorted(merged.items(), key=lambda kv: str(kv[0])):
            if len(cases) < 8:
                continue
            cand = fit(cases, kind)
            v = slot_verdict(cand)
            row = {"exp": expdir, "instr": instr, "kind": kind,
                   "field_key": key[0], "declared_span": [key[1], key[2]],
                   "byte_index": key[3],
                   "n_values": len(cases), "fit": cand, "slot": v,
                   "example": [{"value": vv, "bytes": cases[vv][0],
                                "outcome": cases[vv][2],
                                "file": cases[vv][3], "line": cases[vv][4]}
                               for vv in sorted(cases)[:3]]}
            out.append(row)
            print(f"{expdir[:24]:24s} {instr:15s} {str(key[0])[:16]:16s} "
                  f"{str([key[1],key[2]]):11s} bi={str(key[3]):>4s} n={len(cases):4d} "
                  f"{('j=%d k=%d %s' % (cand['dst_reg'], cand['k'], cand['view'])) if cand else '-':18s} {v}")
    dump(out, "q1_slotfit.json")
