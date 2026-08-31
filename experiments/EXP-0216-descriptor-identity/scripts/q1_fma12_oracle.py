#!/usr/bin/env python3
"""EXP-0216 Q1 — independent confirmation of half_alu_fma12's operand layout.

EXP-0203 committed a HOST ORACLE beside every case: `oracle.a`, `.b`, `.c` (the
half-precision operand values it predicted the instruction would consume) and
`oracle.dst`.  Those numbers were produced by the harness, not by db.json's
field names, and they are checked here against the committed `pre` register dump:

    PREDICTION IF db.json's CURRENT layout is right
        oracle.a == low16( pre[ byte1 >> 1 ] )
        oracle.b == low16( pre[ byte3 >> 1 ] )
        oracle.c == low16( pre[ byte5 >> 1 ] )
        oracle.dst == byte0 >> 4

    PREDICTION IF EXP-0180's FROZEN layout is right (srcA at byte3)
        oracle.a == low16( pre[ byte3 >> 1 ] )   ... and so on, shifted

Only one of the two can hold.  The oracle's own hit rate against the observed
registers is reported too, so a wrong oracle cannot silently confirm a layout.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib0216 import dump, iter_records, outcome_of  # noqa


def lo(x):
    return x & 0xFFFF


def hi(x):
    return (x >> 16) & 0xFFFF


def run(expdir, instr):
    sc = Counter()
    ex = []
    for rel, ln, r in iter_records(expdir, instr, None):
        o = r.get("oracle") or {}
        pre = (r.get("observed") or {}).get("pre")
        if not isinstance(pre, list) or len(pre) < 16:
            continue
        if not all(k in o for k in ("a", "b", "c")):
            continue
        raw = bytes.fromhex(r["bytes"])
        if len(raw) < 6:
            continue
        sc["n"] += 1
        # operand byte -> (register, half):  reg = byte>>1, half = byte&1
        # (0 = low 16 bits, 1 = high 16 bits).  Re-derived here from the
        # oracle/pre agreement itself, not taken from any descriptor text.
        def opnd(byte):
            v = pre[(byte >> 1) & 0xF]
            return hi(v) if (byte & 1) else lo(v)

        cur = (opnd(raw[1]) == o["a"] and opnd(raw[3]) == o["b"]
               and opnd(raw[5]) == o["c"])
        frz = (opnd(raw[3]) == o["a"] and opnd(raw[4]) == o["b"]
               and opnd(raw[5]) == o["c"])
        sc["M_current(a=b1,b=b3,c=b5)"] += 1 if cur else 0
        sc["M_frozen(a=b3,b=b4,c=b5)"] += 1 if frz else 0
        if "dst" in o:
            sc["oracle.dst == byte0>>4"] += 1 if o["dst"] == raw[0] >> 4 else 0
        sc["outcome:" + str(outcome_of(r))] += 1
        if len(ex) < 4:
            ex.append({"file": rel, "line": ln, "bytes": r["bytes"],
                       "oracle": {k: o.get(k) for k in
                                  ("a", "b", "c", "dst", "dst_half", "model")},
                       "opnd(byte1)": opnd(raw[1]),
                       "opnd(byte3)": opnd(raw[3]),
                       "opnd(byte5)": opnd(raw[5])})
    return {"exp": expdir, "instr": instr, "scores": dict(sc), "examples": ex}


if __name__ == "__main__":
    out = [run("EXP-0203-g17p-half-oracle", "half_alu_fma12"),
           run("EXP-0203-g17p-half-oracle", "half_alu_ext8"),
           run("EXP-0180-g17p-halfalu-rerecord", "half_alu_fma12")]
    dump(out, "q1_fma12_oracle.json")
    for o in out:
        print(o["exp"], o["instr"])
        for k, v in sorted(o["scores"].items()):
            print("   ", k, v)
