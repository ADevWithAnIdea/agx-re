#!/usr/bin/env python3
"""EXP-0165 / DEF-0161-4 INDEPENDENT RE-DERIVATION.

Claim: on the rsqrt (0xaf) and log2 (0x2f) SFU datapaths only BIT 0 of byte+8
(`roundmode`) is live, and setting it returns NaN for EVERY input -- 128 of 256
values, all-NaN in 12/12 lanes, in three independent carriers; all 128 even
values reproduce the correct result.

Re-derived here directly from the raw output vectors.  The NaN test is done with
`math.isnan`, NOT with a tolerance compare (the IEEE trap EXP-0161 disclosed).
"""
from __future__ import print_function
import json, math
from pathlib import Path

EXP161 = Path(__file__).resolve().parents[2] / "EXP-0161-g17p-carry-fspecial"

def rows(run, arm, field):
    for l in (EXP161 / "raw" / run / "sweep.jsonl").open():
        r = json.loads(l)
        if r.get("arm") == arm and r.get("field") == field:
            yield r

def vec(r):
    ob = r.get("observed") or {}
    out = ob.get("out")
    if out is None: return None
    try: return [float(x) for x in out]
    except Exception: return None

def main():
    rep = {}
    for run in ("g17p_20260829_run01", "g17p_20260829_run02"):
        for arm, lbl in (("D_FSPEC_INPLACE", "rsqrt 0xaf"),
                         ("D2_FSPEC_LOG2", "log2 0x2f")):
            base = None
            for r in rows(run, arm, "__baseline"):
                base = vec(r)
            odd_allnan, odd_other, even_match, even_other, noread = [], [], [], [], []
            for r in rows(run, arm, "roundmode"):
                v = r["value"]; got = vec(r)
                if got is None:
                    noread.append((v, r["outcome"])); continue
                allnan = all(math.isnan(x) for x in got)
                anynan = any(math.isnan(x) for x in got)
                if v & 1:
                    (odd_allnan if allnan else odd_other).append(
                        v if allnan else {"value": v, "outcome": r["outcome"],
                                          "any_nan": anynan, "head": got[:4]})
                else:
                    same = (base is not None and len(got) == len(base) and
                            all((math.isnan(a) and math.isnan(b)) or
                                abs(a - b) <= 1e-6 * max(1.0, abs(b))
                                for a, b in zip(got, base)))
                    (even_match if same else even_other).append(
                        v if same else {"value": v, "outcome": r["outcome"],
                                        "any_nan": anynan, "head": got[:4]})
            rep["%s/%s" % (run, lbl)] = {
                "odd_values_all_NaN": len(odd_allnan),
                "odd_values_NOT_all_NaN": odd_other,
                "even_values_matching_baseline": len(even_match),
                "even_values_NOT_matching": even_other,
                "no_readback": noread}
    print(json.dumps(rep, indent=1))

if __name__ == "__main__":
    main()
