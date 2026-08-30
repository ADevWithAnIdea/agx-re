#!/usr/bin/env python3
"""EXP-0165: independent scoring of EXP-0161's gen03 generation arm.

EXP-0161's own harness wrote a `verdict` into each record.  This script ignores
that verdict entirely and re-scores every generated case from (a) the encoded
BLOCK BYTES committed in the record and (b) the corrected operand model, and
also re-scores them against the ORIGINAL db.json model, so the two can be
compared.  Inputs: raw/g17p_20260830_gen03/sweep.jsonl (immutable).
"""
from __future__ import print_function
import json, struct
from pathlib import Path

EXP161 = Path(__file__).resolve().parents[2] / "EXP-0161-g17p-carry-fspecial"
SEED_F32 = [4.0, 9.0, 0.25, 16.0, 2.0, 64.0, 0.5, 100.0,
            1.5, 36.0, 0.125, 81.0, 6.25, 121.0, 3.0, 0.0]
SEED_U32 = None
def fb(x): return struct.unpack("<I", struct.pack("<f", float(x)))[0]
def f32(u): return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]
FSEED = [fb(v) for v in SEED_F32]

def approx(a, b, tol=1e-5):
    return abs(a - b) <= tol * max(1.0, abs(b))

def score_fspecial(rec, model):
    blk = bytes.fromhex(rec["block"])
    b1hi, b3, b5 = blk[1] >> 4, blk[3], blk[5]
    if model == "corrected":
        dst, src = b3 >> 1, b5 >> 2
    else:                              # db.json as committed: dst=b1 hi nibble,
        dst, src = b1hi, b3            # src = byte+3 (low bits of the reg)
    if not (0 <= dst < 15 and 0 <= src < 15):
        return "unpredictable"
    got = [int(x, 16) for x in rec["observed"]]
    pred = list(FSEED)
    if src != dst:
        pred[src] = 0                  # release-on-read
    pred[dst] = fb(1.0 / (f32(FSEED[src]) ** 0.5))
    pred[15] = 0
    ok = all(got[i] == pred[i] or approx(f32(got[i]), f32(pred[i]))
             for i in range(15))
    return "pass" if ok else "fail"

def main():
    recs = [json.loads(l) for l in (EXP161 / "raw" / "g17p_20260830_gen03"
                                    / "sweep.jsonl").open()]
    fs = [r for r in recs if r.get("gen") == "fspecial" and r.get("observed")]
    res = {"n": len(fs), "corrected": {}, "db_json_as_committed": {}, "detail": []}
    for r in fs:
        c = score_fspecial(r, "corrected")
        o = score_fspecial(r, "dbjson")
        res["corrected"][c] = res["corrected"].get(c, 0) + 1
        res["db_json_as_committed"][o] = res["db_json_as_committed"].get(o, 0) + 1
        res["detail"].append({"desc": r["desc"], "block": r["block"],
                              "corrected": c, "db_model": o,
                              "harness_verdict": r.get("verdict")})
    # agreement with the harness' own verdict
    res["agrees_with_harness_verdict"] = all(
        d["corrected"] == d["harness_verdict"] for d in res["detail"])
    print(json.dumps(res, indent=1))

if __name__ == "__main__":
    main()
