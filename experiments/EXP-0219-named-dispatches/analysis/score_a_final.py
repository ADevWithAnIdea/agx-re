#!/usr/bin/env python3
"""EXP-0219 part-A: the CORRECTED unified model, scored over every case.

    dest = m * (SEED[b5>>2] * SEED[b6>>3]) + A          m = 1 if (b7&3)==0 else 0
    sel  = (b9 >> 3) & 1
    sel == 0 :  A = ((b8 & 7) << 5) | ((b7 >> 3) & 0x1f)          8-bit IMMEDIATE
    sel == 1 :  i = ((b7 >> 3) & 0x1f) | ((b8 & 7) << 5)          8-bit INDEX
                (b9 & 1) == 0 -> A = FILE[i]                      16-bit half
                (b9 & 1) == 1 -> A = FILE[i & ~1] | FILE[(i&~1)+1] << 16   WORD

FILE is fitted per the declared rule (half-indices 0..31 only, b9=0x2e, b8=0xd0,
seed set 1, run01) and EXTENDED for indices >= 32 from the C-CONST carrier's own
MSL source layout, which is a host prediction, not a fit.  For C-DAG the file is
0 above 15 and no extension is needed.

Also prints the two rival selector assignments and the two rival 32-bit rules on
the same cases, so the margin is visible rather than asserted.
"""
import json
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
M32 = 0xFFFFFFFF
RUNS = {"dag": ["g17p_e0219_A_dag_run01", "g17p_e0219_A_dag_run02"],
        "const": ["g17p_e0219_A_const_run01", "g17p_e0219_A_const_run02"]}


def load(r):
    return [json.loads(l) for l in (EXP / "raw" / r / "sweep.jsonl").open()]


def ab(r):
    return bytes.fromhex(r["ledger"]["actual_bytes"])


def fit_file(recs, arm):
    F = {}
    for r in recs:
        b = ab(r)
        if (r["arm"] == arm and b[9] == 0x2e and b[8] == 0xd0 and r["sset"] == 1
                and r["ledger"]["gate_a_ok"]
                and r["outcome"] in ("ok", "silent_zero", "wrong_value")):
            F[(b[7] >> 3) & 0x1F] = r["recovered_A"]
    return F


def extend_const(F):
    """Host prediction from kernels/carrier_const.metal, NOT a fit: the fit
    region 14..31 shows half 14+2i -> low(i), 15+2i -> high(i); the MSL declares
    48 constants with low(i) = 0x1000+i, high(i) = 0x3F80+i.  The carrier's file
    is measured to END at half-index 75, so beyond that the prediction is 0."""
    G = dict(F)
    for i in range(48):
        for k, v in ((14 + 2 * i, 0x1000 + i), (15 + 2 * i, 0x3F80 + i)):
            if k >= 32:
                G[k] = v if k <= 75 else 0
    return G


def A_of(b7, b8, b9, F, sel_bit, idx_bits, w32):
    K = (b7 >> 3) & 0x1F
    sel = (b9 >> sel_bit) & 1
    if sel == 0:
        return (((b8 & 7) << 5) | K) & 0xFF
    i = K if idx_bits == 5 else (K | ((b8 & 7) << 5))
    if idx_bits == 5 and (b8 & 7):
        return 0
    if b9 & 1:
        j = i if w32 == "pair" else (i & ~1)
        return (F.get(j, 0) | (F.get(j + 1, 0) << 16)) & M32
    return F.get(i, 0)


def score(recs, F, sel_bit, idx_bits, w32):
    hit = tot = 0
    for r in recs:
        if not r["ledger"]["gate_a_ok"]:
            continue
        if r["outcome"] in ("hang", "fault", "measurement_failure", "undecodable"):
            continue
        b = ab(r)
        if (b[7] & 3) == 3 or (b[9] >> 5 & 1) == 0:
            continue                   # documented fault mode / block does not compute
        m = 1 if (b[7] & 3) == 0 else 0
        want = ((m * r["oracle"]["P"]) + A_of(b[7], b[8], b[9], F, sel_bit,
                                              idx_bits, w32)) & M32
        got = r["observed"]["regs"][0] if r["observed"]["regs"] else None
        tot += 1
        hit += (got == want)
    return hit, tot


out = {}
for c, rs in RUNS.items():
    r1 = load(rs[0])
    F = fit_file(r1, "cross" if c == "dag" else "cross32")
    if c == "const":
        F = extend_const(F)
    for rid in rs:
        recs = load(rid)
        e = {}
        for nm, (sb, ib, w) in {
            "U*  sel=bit3, index=8, 32bit=WORD": (3, 8, "word"),
            "    sel=bit3, index=8, 32bit=pair": (3, 8, "pair"),
            "    sel=bit3, index=5, 32bit=word": (3, 5, "word"),
            "    sel=bit1, index=8, 32bit=word": (1, 8, "word"),
            "    sel=bit1, index=5, 32bit=pair": (1, 5, "pair"),
        }.items():
            h, t = score(recs, F, sb, ib, w)
            e[nm] = "%d/%d" % (h, t)
        # per-arm breakdown under U*
        for arm in sorted({r["arm"] for r in recs}):
            h, t = score([r for r in recs if r["arm"] == arm], F, 3, 8, "word")
            e["U* :: arm " + arm] = "%d/%d" % (h, t)
        for s in (1, 2):
            h, t = score([r for r in recs if r["sset"] == s], F, 3, 8, "word")
            e["U* :: seed set %d" % s] = "%d/%d" % (h, t)
        out[rid] = e
print(json.dumps(out, indent=1))
