#!/usr/bin/env python3
"""EXP-0165 / DEF-0161-2 INDEPENDENT RE-DERIVATION.

Claim under test: `mov_zext16`'s byte0 HIGH NIBBLE is a register selector
(`r[n] = r[n] & 0xFFFF`), not part of a fixed 8-bit match `== 0x13`; and
byte+1 (db `src_reg` / `src_flag`) is inert, i.e. not a source selector.

Inputs (immutable): EXP-0161 raw/g17p_20260829_run01, run02 (arms
B_ZEXT_SYNTH, B_ZEXT_INPLACE), raw/g17p_20260830_supp02, supp03
(arm B2_ZEXT_SYNTH_R5) and raw/g17p_20260830_gen03 (generation).
EXP-0161's own verdicts are not read.
"""
from __future__ import print_function
import json
from pathlib import Path

EXP161 = Path(__file__).resolve().parents[2] / "EXP-0161-g17p-carry-fspecial"
SEED = [0x80112233, 0x8F4E7A15, 0x0A2C51E7, 0xA7D30B49,
        0x161F94AB, 0xC48A2D5D, 0x23654EBF, 0xE2B0C721,
        0x310D3883, 0x47F6A9E5, 0x5613BA47, 0xF5E0CBA9,
        0x64CD1C0B, 0x73BA8D6D, 0xEE9F7ECF, 0x00000000]

def load(run, arm):
    p = EXP161 / "raw" / run / "sweep.jsonl"
    if not p.exists(): return []
    return [json.loads(l) for l in p.open()
            if json.loads(l).get("arm") == arm]

def regs(r):
    return (r.get("observed") or {}).get("regs")

def analyse_byte0(recs, label):
    base = [r for r in recs if r["field"] == "__baseline"]
    b = regs(base[0]) if base else None
    rows = []
    for r in recs:
        if r["field"] != "__raw_b0": continue
        rg = regs(r)
        if rg is None:
            rows.append({"byte0": r["value"], "outcome": r["outcome"],
                         "regs": None}); continue
        ch = [i for i in range(15) if rg[i] != SEED[i]]
        # which register(s), if any, hold exactly seed & 0xFFFF ?
        narrowed = [i for i in range(15) if rg[i] == (SEED[i] & 0xFFFF)
                    and SEED[i] != (SEED[i] & 0xFFFF)]
        rows.append({"byte0": r["value"], "outcome": r["outcome"],
                     "changed": ch, "narrowed": narrowed,
                     "nibble": r["value"] >> 4, "low": r["value"] & 0xF})
    return {"label": label, "baseline_regs": ["%08x" % v for v in b] if b else None,
            "rows": rows}

def rule_check(a):
    """For every byte0 value with low nibble == 3, does r[hi] and ONLY r[hi]
    become seed & 0xFFFF?"""
    fits, misfits, noop = [], [], []
    for row in a["rows"]:
        if row.get("regs", 1) is None or "changed" not in row: continue
        n, lo = row["nibble"], row["low"]
        if lo != 3:
            continue
        if n <= 14:
            if row["changed"] == [n] and row["narrowed"] == [n]:
                fits.append(row["byte0"])
            elif row["changed"] == []:
                noop.append(row["byte0"])
            else:
                misfits.append(row)
        else:                       # n == 15 -> r15, outside the dumped seeds
            (noop if row["changed"] == [] else misfits).append(
                row["byte0"] if row["changed"] == [] else row)
    return {"fits": fits, "n_fits": len(fits),
            "misfits": misfits, "n_misfits": len(misfits),
            "noop": noop, "n_noop": len(noop)}

def other_low_nibbles(a):
    """What do byte0 values whose LOW nibble != 3 do?  If the low nibble is the
    real opcode discriminator, they should not perform the narrow."""
    tab = {}
    for row in a["rows"]:
        if "changed" not in row: continue
        lo = row["low"]
        tab.setdefault(lo, {"narrowing": 0, "n": 0, "other_change": 0})
        tab[lo]["n"] += 1
        if row["narrowed"]:
            tab[lo]["narrowing"] += 1
        elif row["changed"]:
            tab[lo]["other_change"] += 1
    return tab

def inertness(recs, field, label):
    base = [r for r in recs if r["field"] == "__baseline"]
    b = regs(base[0]) if base else None
    same, diff, novalue = [], [], []
    for r in recs:
        if r["field"] != field: continue
        rg = regs(r)
        if rg is None: novalue.append(r["value"]); continue
        (same if rg == b else diff).append(r["value"] if rg == b else
                                           {"value": r["value"],
                                            "regs": ["%08x" % v for v in rg]})
    return {"field": field, "carrier": label, "n_identical": len(same),
            "n_different": len(diff), "different": diff[:10],
            "n_no_readback": len(novalue)}

def main():
    out = {}
    for run, arm in (("g17p_20260829_run01", "B_ZEXT_SYNTH"),
                     ("g17p_20260829_run02", "B_ZEXT_SYNTH"),
                     ("g17p_20260830_supp02", "B2_ZEXT_SYNTH_R5"),
                     ("g17p_20260830_supp03", "B2_ZEXT_SYNTH_R5")):
        recs = load(run, arm)
        if not recs: continue
        key = "%s/%s" % (run, arm)
        a = analyse_byte0(recs, key)
        out[key] = {"n_cases": len(recs),
                    "baseline_bytes": next((r["bytes"] for r in recs
                                            if r["field"] == "__baseline"), None),
                    "byte0_rule_rN3_narrows_rN": rule_check(a),
                    "byte0_low_nibble_table": other_low_nibbles(a),
                    "src_reg_inert": inertness(recs, "src_reg", key),
                    "src_flag_inert": inertness(recs, "src_flag", key),
                    "falsifier_byte0_0x00": [
                        {"outcome": r["outcome"]} for r in recs
                        if r["field"] == "__falsifier_byte0"],
                    "subform_accepted": sorted(
                        r["value"] for r in recs
                        if r["field"] == "subform" and r["outcome"] == "ok"),
                    "extend_accepted": sorted(
                        r["value"] for r in recs
                        if r["field"] == "extend" and r["outcome"] == "ok"),
                    }
    # the INPLACE control: EXP-0146's own carrier
    for run in ("g17p_20260829_run01", "g17p_20260829_run02"):
        recs = load(run, "B_ZEXT_INPLACE")
        if not recs: continue
        out["%s/B_ZEXT_INPLACE" % run] = {
            "falsifier_byte0_0x00": [r["outcome"] for r in recs
                                     if r["field"] == "__falsifier_byte0"],
            "baseline": [r["outcome"] for r in recs if r["field"] == "__baseline"],
            "src_reg_ok": sum(1 for r in recs
                              if r["field"] == "src_reg" and r["outcome"] == "ok"),
            "src_reg_n": sum(1 for r in recs if r["field"] == "src_reg"),
        }
    # generation
    g = [json.loads(l) for l in (EXP161 / "raw" / "g17p_20260830_gen03"
                                 / "sweep.jsonl").open()]
    gz = [r for r in g if r.get("gen") == "mov_zext16"]
    det = []
    for r in gz:
        blk = bytes.fromhex(r["block"]); n = blk[0] >> 4
        got = [int(x, 16) for x in r["observed"]] if r.get("observed") else None
        pred = list(SEED); pred[n if n < 16 else 0] = SEED[n] & 0xFFFF if n < 16 else 0
        pred = list(SEED)
        if n < 15: pred[n] = SEED[n] & 0xFFFF
        pred[15] = 0
        det.append({"desc": r["desc"], "byte0": "%02x" % blk[0],
                    "n": n,
                    "rescored": ("pass" if got and got[:15] == pred[:15] else "fail"),
                    "harness_verdict": r.get("verdict"),
                    "observed_changed": ([i for i in range(15)
                                          if got[i] != SEED[i]] if got else None)})
    out["gen03_mov_zext16"] = {"n": len(det), "detail": det,
                               "rescore_agrees_with_harness":
                               all(d["rescored"] == d["harness_verdict"] for d in det)}
    print(json.dumps(out, indent=1))

if __name__ == "__main__":
    main()
