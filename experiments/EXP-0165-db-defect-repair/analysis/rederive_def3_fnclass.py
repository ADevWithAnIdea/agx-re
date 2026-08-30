#!/usr/bin/env python3
"""EXP-0165 / DEF-0161-3 INDEPENDENT RE-DERIVATION.

DEF-0161-3 claims: "on the standard-SFU datapath (byte+6/+7 = 0xb0/0x40) only
the LOW TWO BITS of the `fnclass` nibble are live: values 1,3,5,7,9,11,13,15 all
compute the same function."

This script re-derives the fnclass -> function map BY COMPUTED VALUE from the
raw output vectors of all three fspecial carriers, and tests bit 2 and bit 3
for don't-care independently.
"""
from __future__ import print_function
import json, math, struct
from pathlib import Path

EXP161 = Path(__file__).resolve().parents[2] / "EXP-0161-g17p-carry-fspecial"
F_IN = [4.0, 9.0, 0.25, 16.0, 2.0, 64.0, 0.5, 100.0, 1.5, 36.0, 0.125, 81.0]
SEED_F32 = [4.0, 9.0, 0.25, 16.0, 2.0, 64.0, 0.5, 100.0,
            1.5, 36.0, 0.125, 81.0, 6.25, 121.0, 3.0, 0.0]

def f32(u): return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]

FUNCS = {
    "identity": lambda x: x,
    "rint": lambda x: float(round(x)),
    "rcp": lambda x: 1.0 / x,
    "rsqrt": lambda x: 1.0 / math.sqrt(x),
    "sqrt": math.sqrt,
    "exp2": lambda x: 2.0 ** x,
    "log2": math.log2,
    "floor": math.floor,
    "ceil": math.ceil,
    "trunc": math.trunc,
}

def name_vector(vals, inputs):
    """Which known function reproduces this output vector, to 1e-5 relative?"""
    if vals is None:
        return "no_readback"
    fv = []
    for v in vals:
        try: fv.append(float(v))
        except Exception: return "unparsable"
    if all(math.isnan(x) for x in fv): return "ALL_NaN"
    if all(math.isinf(x) for x in fv): return "ALL_inf"
    for nm, fn in FUNCS.items():
        try:
            want = [fn(x) for x in inputs[:len(fv)]]
        except Exception:
            continue
        if all(abs(a - b) <= 1e-5 * max(1.0, abs(b)) for a, b in zip(fv, want)):
            return nm
    nan = sum(1 for x in fv if math.isnan(x))
    return "unknown(%d NaN)" % nan if nan else "unknown"

def collect(run, arm, field, inputs):
    rows = {}
    for l in (EXP161 / "raw" / run / "sweep.jsonl").open():
        r = json.loads(l)
        if r.get("arm") != arm or r.get("field") != field: continue
        ob = r.get("observed") or {}
        out = ob.get("out")
        if out is None and ob.get("regs"):        # synth carrier: r0 holds it
            out = None
        rows[r["value"]] = {"outcome": r["outcome"],
                            "poison": ob.get("poison_words"),
                            "fn": name_vector(out, inputs) if out is not None else None,
                            "regs": ob.get("regs")}
    return rows

def synth_fn(rows):
    """For the SYNTH carrier the answer is in the register dump: the block is
    `af 01 56 00 02 00 b0 40 00 00`, dst = byte+3>>1 = r0, src = byte+5>>2 = r0,
    so the function of seed r0 = 4.0 lands in r0."""
    for v, row in rows.items():
        rg = row.get("regs")
        if not rg: row["fn"] = None; continue
        got = f32(rg[0])
        nm = "unknown"
        if math.isnan(got): nm = "NaN"
        elif math.isinf(got): nm = "inf"
        else:
            for k, fn in FUNCS.items():
                try:
                    if abs(got - fn(4.0)) <= 1e-5 * max(1.0, abs(fn(4.0))): nm = k; break
                except Exception: pass
        row["fn"] = nm
        row["r0"] = "%08x" % rg[0]
    return rows

def main():
    out = {}
    for run in ("g17p_20260829_run01", "g17p_20260829_run02"):
        a = collect(run, "D_FSPEC_INPLACE", "fnclass", F_IN)   # 0xaf rsqrt
        b = collect(run, "D2_FSPEC_LOG2", "fnclass", F_IN)     # 0x2f log2
        c = synth_fn(collect(run, "D3_FSPEC_SYNTH", "fnclass", F_IN))
        rep = {}
        for lbl, tab in (("byte0=0xaf INPLACE(rsqrt)", a),
                         ("byte0=0x2f INPLACE(log2)", b),
                         ("byte0=0xaf SYNTH(rsqrt)", c)):
            rep[lbl] = {str(v): "%s / %s%s" % (tab[v]["fn"], tab[v]["outcome"],
                        (" poison=%s" % tab[v]["poison"]) if tab[v].get("poison") else "")
                        for v in sorted(tab)}
            # bit-2 and bit-3 don't-care tests
            b3 = {v: (tab[v]["fn"], tab[v]["outcome"]) for v in tab}
            rep[lbl + " :: bit3_dontcare"] = all(
                b3.get(v) == b3.get(v + 8) for v in range(8) if v in b3 and v + 8 in b3)
            rep[lbl + " :: bit2_dontcare"] = {
                "per_low2": {lo: all(b3.get(lo + hi * 8) == b3.get(lo + 4 + hi * 8)
                                     for hi in (0, 1)
                                     if lo + hi * 8 in b3 and lo + 4 + hi * 8 in b3)
                             for lo in range(4)},
                "global": all(b3.get(v) == b3.get(v + 4) for v in (0, 1, 2, 3, 8, 9, 10, 11)
                              if v in b3 and v + 4 in b3)}
            rep[lbl + " :: all_odd_same"] = len({b3[v] for v in b3 if v % 2 == 1}) == 1
        # fn_hi at fnclass==2, by computed value
        for run_arm, lbl in (("D2_FSPEC_LOG2", "fn_hi on the 0x?f/class-2 datapath"),):
            t = collect(run, run_arm, "fn_hi", F_IN)
            rep[lbl] = {str(v): t[v]["fn"] for v in sorted(t)}
        out[run] = rep
    print(json.dumps(out, indent=1))

if __name__ == "__main__":
    main()
