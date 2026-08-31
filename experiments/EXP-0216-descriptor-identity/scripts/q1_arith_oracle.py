#!/usr/bin/env python3
"""EXP-0216 Q1 — host arithmetic oracle: which BYTE feeds which OPERAND SLOT.

This is the Gate-C half of test I.  For each instruction a host model is written
that maps the three candidate operand bytes to slots, the model is evaluated on
the frozen seed table, and the prediction is compared with the committed
destination register for EVERY case of the sweep.  Two rival slot assignments
are scored against the same records:

  M-current : the slot assignment db.json holds TODAY
  M-frozen  : the slot assignment the experiment's own frozen db.json held

A model is `selected` only if it reproduces the destination exactly on every
case whose outcome is `ok` or `wrong_value` (faults/hangs/poison excluded, and
counted separately).

Operand-byte decode used by both models (a hardware fact re-derived here from
the release-on-read map, not taken from any name):
      reg = byte >> 1   for the 6/8-byte float and int ALU carriers
      the low bit selects the operand WIDTH; a 16-bit read of a seed whose low
      half is zero contributes 0.
"""
from __future__ import annotations

import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0216 import dump, iter_records, outcome_of  # noqa

SEED_I = {0: 10, 1: 21, 2: 34, 3: 47, 4: 58, 5: 65, 6: 71, 7: 83,
          8: 94, 9: 101, 10: 113, 11: 119, 12: 125, 13: 127, 14: 3, 15: 0}
SEED_F = {0: 5.0, 1: 1.5, 2: 3.0, 3: 0.5, 4: 7.0, 5: 9.0, 6: 11.0, 7: 13.0,
          8: 0.25, 9: 18.0, 10: 22.0, 11: 26.0, 12: 30.0, 13: 0.75,
          14: 0.0, 15: 0.0}
POISON = 0xDEADBEEF


def f32(u):
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


def u32(x):
    return struct.unpack("<I", struct.pack("<f", x))[0]


def opnd_mul(byte):
    """MULTIPLICAND operand byte -> value.  reg = byte>>1; bit0 == 0 reads the
    LOW 16 bits of the seed, which is 0 for every exact-float seed used here."""
    if byte >= 32:
        return None                      # outside the 16-register seed table
    return SEED_F[(byte >> 1) & 0xF] if (byte & 1) else 0.0


def opnd_add(byte):
    """ADDEND operand byte -> value.  reg = byte>>1, both parities read the
    register (established from the byte-5 arm's own release map)."""
    if byte >= 32:
        return None
    return SEED_F[(byte >> 1) & 0xF]


def run_falu3(expdir, instr):
    """falu3 / falu3_ext:  dest = A*B + C.
       M-current : A=byte1, B=byte3, C=byte5     (db.json today)
       M-frozen  : A=byte3, B=byte4, C=byte5     (the experiment's own db)
    """
    rows = defaultdict(dict)
    for rel, ln, r in iter_records(expdir, instr, None):
        o = (r.get("observed") or {}).get("regs")
        v = r.get("value")
        if not o or not isinstance(v, int):
            continue
        rows[(r.get("field"), r.get("fstart"), r.get("fwidth"))].setdefault(
            v, (r["bytes"], tuple(o), outcome_of(r), rel, ln))
    res = []
    for key, cases in sorted(rows.items(), key=lambda kv: str(kv[0])):
        if len(cases) < 8:
            continue
        sc = {"M_current(A=b1,B=b3,C=b5)": 0, "M_frozen(A=b3,B=b4,C=b5)": 0,
              "in_domain_current": 0, "in_domain_frozen": 0,
              "n_scored": 0, "n_excluded": 0}
        misses = []
        for v, (bh, regs, oc, f, l) in sorted(cases.items()):
            raw = bytes.fromhex(bh)
            dst = raw[0] >> 4
            got = regs[dst]
            if got == POISON or oc in ("fault", "hang", "timeout", None):
                sc["n_excluded"] += 1
                continue
            sc["n_scored"] += 1
            for name, (ia, ib, ic) in (
                    ("M_current(A=b1,B=b3,C=b5)", (1, 3, 5)),
                    ("M_frozen(A=b3,B=b4,C=b5)", (3, 4, 5))):
                a, b, c = (opnd_mul(raw[ia]), opnd_mul(raw[ib]),
                           opnd_add(raw[ic]))
                if None in (a, b, c):
                    continue
                sc["in_domain_current" if ia == 1 else "in_domain_frozen"] += 1
                pred = a * b + c
                try:
                    if u32(pred) == got:
                        sc[name] += 1
                    elif name == "M_current(A=b1,B=b3,C=b5)" and len(misses) < 6:
                        misses.append({"value": v, "bytes": bh,
                                       "pred": pred, "got_f32": f32(got),
                                       "outcome": oc, "file": f, "line": l})
                except (OverflowError, ValueError):
                    pass
        res.append({"exp": expdir, "instr": instr, "field_key": key[0],
                    "declared_span": [key[1], key[2]], "scores": sc,
                    "first_misses_of_M_current": misses})
    return res


def run_iminmax(expdir):
    """iminmax: dest = min(A, B) over 32-bit ints.
       M-current : A=byte1, B=byte3    M-frozen : A=byte3, B=byte5
       Integer seeds have identical low halves, so the width bit is invisible
       and reg = byte>>1 is used for both widths."""
    rows = defaultdict(dict)
    for rel, ln, r in iter_records(expdir, "iminmax", None):
        o = (r.get("observed") or {}).get("regs")
        v = r.get("value")
        if not o or not isinstance(v, int):
            continue
        rows[(r.get("field"), r.get("fstart"), r.get("fwidth"))].setdefault(
            v, (r["bytes"], tuple(o), outcome_of(r), rel, ln))
    res = []
    for key, cases in sorted(rows.items(), key=lambda kv: str(kv[0])):
        if len(cases) < 8:
            continue
        sc = {"M_current(A=b1,B=b3)": 0, "M_frozen(A=b3,B=b5)": 0,
              "in_domain_current": 0, "in_domain_frozen": 0,
              "n_scored": 0, "n_excluded": 0}
        for v, (bh, regs, oc, f, l) in sorted(cases.items()):
            raw = bytes.fromhex(bh)
            dst = raw[0] >> 4
            got = regs[dst]
            if got == POISON or oc in ("fault", "hang", "timeout", None):
                sc["n_excluded"] += 1
                continue
            sc["n_scored"] += 1
            for name, (ia, ib) in (("M_current(A=b1,B=b3)", (1, 3)),
                                   ("M_frozen(A=b3,B=b5)", (3, 5))):
                if raw[ia] >= 32 or raw[ib] >= 32:
                    continue
                sc["in_domain_current" if ia == 1 else "in_domain_frozen"] += 1
                a, b = SEED_I[(raw[ia] >> 1) & 0xF], SEED_I[(raw[ib] >> 1) & 0xF]
                if min(a, b) == got:
                    sc[name] += 1
        res.append({"exp": expdir, "instr": "iminmax", "field_key": key[0],
                    "declared_span": [key[1], key[2]], "scores": sc})
    return res


def run_imad(expdir):
    """imad: dest = A*B + K.   Both rival descriptor versions agree that byte5
    and byte6 are operands; they disagree only about WHICH of them is the
    addend `srcC_lo`.  Scored models:
       M-mulmul : dest = SEED[b5>>2] * SEED[b6>>3] + K      (both multiplicands)
       M-b5addend: dest = SEED[b6>>3] * K2 + SEED[b5>>2]
       M-b6addend: dest = SEED[b5>>2] * K2 + SEED[b6>>3]
    K and K2 are taken from the arm's own baseline, not fitted per case."""
    rows = defaultdict(dict)
    for rel, ln, r in iter_records(expdir, "imad", None):
        o = (r.get("observed") or {}).get("regs")
        v = r.get("value")
        if not o or not isinstance(v, int):
            continue
        rows[(r.get("field"), r.get("fstart"), r.get("fwidth"))].setdefault(
            v, (r["bytes"], tuple(o), outcome_of(r), rel, ln))
    res = []
    K, K2 = 1, None
    for key, cases in sorted(rows.items(), key=lambda kv: str(kv[0])):
        if key[0] not in ("srcB", "srcC_lo"):
            continue
        sc = {"M_mulmul": 0, "M_b5addend": 0, "M_b6addend": 0,
              "n_scored": 0, "n_excluded": 0}
        ex = []
        for v, (bh, regs, oc, f, l) in sorted(cases.items()):
            raw = bytes.fromhex(bh)
            dst = raw[3] >> 1 if raw[3] else 0
            got = regs[0]
            if got == POISON or oc in ("fault", "hang", "timeout", None):
                sc["n_excluded"] += 1
                continue
            if raw[5] >> 2 > 15 or raw[6] >> 3 > 15:
                sc["n_excluded"] += 1
                continue
            s5 = SEED_I[(raw[5] >> 2) & 0xF]
            s6 = SEED_I[(raw[6] >> 3) & 0xF]
            sc["n_scored"] += 1
            if s5 * s6 + K == got:
                sc["M_mulmul"] += 1
            if s6 * SEED_I[0] + s5 == got:
                sc["M_b5addend"] += 1
            if s5 * SEED_I[0] + s6 == got:
                sc["M_b6addend"] += 1
            if len(ex) < 5:
                ex.append({"value": v, "bytes": bh, "got": got,
                           "s5": s5, "s6": s6, "mulmul": s5 * s6 + K,
                           "file": f, "line": l})
        res.append({"exp": expdir, "instr": "imad", "field_key": key[0],
                    "declared_span": [key[1], key[2]], "scores": sc,
                    "examples": ex})
    return res


if __name__ == "__main__":
    out = []
    out += run_falu3("EXP-0154-g17p-emit-alu", "falu3")
    out += run_falu3("EXP-0154-g17p-emit-alu", "falu3_ext")
    out += run_iminmax("EXP-0154-g17p-emit-alu")
    out += run_iminmax("EXP-0160-g17p-last-field")
    out += run_imad("EXP-0154-g17p-emit-alu")
    dump(out, "q1_arith_oracle.json")
    for r in out:
        s = r["scores"]
        print(f"{r['exp'][:22]:22s} {r['instr']:10s} {str(r['field_key'])[:10]:10s} "
              f"{str(r['declared_span']):11s} " +
              "  ".join(f"{k}={v}" for k, v in s.items()))
