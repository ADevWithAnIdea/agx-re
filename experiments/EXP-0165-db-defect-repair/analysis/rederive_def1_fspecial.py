#!/usr/bin/env python3
"""EXP-0165 / DEF-0161-1 INDEPENDENT RE-DERIVATION.

Reads EXP-0161's immutable raw sweeps and re-derives, from the register dumps
alone, which byte of `fspecial` selects the DESTINATION register and which
selects the SOURCE register.  Nothing is taken from EXP-0161's RESULTS.md or
its verdicts file; the only inputs are:

  * the authored float seed vector (r0..r14), recomputed here from EXP-0161's
    committed harness constant, and
  * `observed.regs` -- the 16-register architectural dump -- in
    raw/g17p_20260829_run01 and run02 (D3_FSPEC_SYNTH), and
    raw/g17p_20260830_gen03 (the generation arm).

CLEAN-ROOM: analysis of our own experiment's committed raw JSON only.
"""
from __future__ import print_function
import json, struct, sys, collections
from pathlib import Path

EXP161 = Path(__file__).resolve().parents[2] / "EXP-0161-g17p-carry-fspecial"

SEED_F32 = [4.0, 9.0, 0.25, 16.0, 2.0, 64.0, 0.5, 100.0,
            1.5, 36.0, 0.125, 81.0, 6.25, 121.0, 3.0, 0.0]
def fb(x): return struct.unpack("<I", struct.pack("<f", float(x)))[0]
def f32(u): return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]
SEED = [fb(v) for v in SEED_F32]

def load(run, arms=None, instr=None):
    out = []
    p = EXP161 / "raw" / run / "sweep.jsonl"
    for line in p.open():
        r = json.loads(line)
        if arms and r.get("arm") not in arms: continue
        if instr and r.get("instr") != instr: continue
        out.append(r)
    return out

def regs(r):
    o = r.get("observed") or {}
    return o.get("regs")

def classify(rg):
    """Return (changed_to_result, released_to_zero) relative to the seed."""
    if not rg: return None
    ch = [i for i in range(15) if rg[i] != SEED[i]]
    zero = [i for i in ch if rg[i] == 0]
    nz = [i for i in ch if rg[i] != 0]
    return ch, zero, nz

def rsqrt_of(u):
    return 1.0 / (f32(u) ** 0.5)

def main():
    report = {}
    for run in ("g17p_20260829_run01", "g17p_20260829_run02"):
        recs = load(run, arms={"D3_FSPEC_SYNTH"})
        base = [r for r in recs if r["field"] == "__baseline"]
        rep = {"n_cases": len(recs), "baseline_bytes": base[0]["bytes"] if base else None,
               "baseline_regs": ["%08x" % v for v in regs(base[0])] if base else None}

        # ---- byte+1 high nibble (db `dst`) --------------------------------
        d = [r for r in recs if r["field"] == "dst" and r["outcome"] != "victim"]
        b0 = regs(base[0])
        same = [r["value"] for r in d if regs(r) == b0]
        diff = [(r["value"], ["%08x" % v for v in regs(r)]) for r in d if regs(r) != b0]
        rep["db_dst_byte1hi"] = {"n": len(d), "identical_to_baseline": sorted(same),
                                 "different": diff}

        # ---- byte+3 (db `src`) -------------------------------------------
        s = [r for r in recs if r["field"] == "src" and r["outcome"] != "victim"]
        dst_map, src_map, other = {}, {}, []
        for r in s:
            rg = regs(r)
            if rg is None: continue
            ch, zero, nz = classify(rg)
            # which register received an rsqrt result, and of what?
            rec = {"value": r["value"], "changed": ch, "zeroed": zero}
            hits = []
            for i in nz:
                for j in range(15):
                    if abs(f32(rg[i]) - rsqrt_of(SEED[j])) <= 1e-5 * max(1.0, abs(rsqrt_of(SEED[j]))):
                        hits.append((i, j))
            rec["rsqrt_writes"] = hits
            other.append(rec)
        rep["byte3_cases"] = other

        # ---- byte+5 (db `src_ext`) ---------------------------------------
        e = [r for r in recs if r["field"] == "src_ext" and r["outcome"] != "victim"]
        erec = []
        for r in e:
            rg = regs(r)
            if rg is None: continue
            ch, zero, nz = classify(rg)
            hits = []
            for i in nz:
                for j in range(15):
                    if abs(f32(rg[i]) - rsqrt_of(SEED[j])) <= 1e-5 * max(1.0, abs(rsqrt_of(SEED[j]))):
                        hits.append((i, j))
            erec.append({"value": r["value"], "changed": ch, "zeroed": zero,
                         "rsqrt_writes": hits})
        rep["byte5_cases"] = erec
        report[run] = rep
    print(json.dumps(report, indent=1))

if __name__ == "__main__":
    main()
