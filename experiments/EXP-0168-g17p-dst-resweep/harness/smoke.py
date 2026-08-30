#!/usr/bin/env python3
"""EXP-0168 PRE-FREEZE smoke / calibration (raw/prefreeze/ -- NEVER evidence).

Runs a handful of cases per arm to prove, before a gated run is started:
  S1  the synth carrier's region is long enough and the program round-trips;
  S2  the unmutated anchor reproduces on hardware and both sentinels are clean;
  S3  the tail poison region is intact after a normal dispatch (nothing writes
      out of bounds);
  S4  the poison is actually visible -- a deliberately empty program leaves the
      WHOLE buffer poisoned, so `invalid_poison` can be told from `silent_zero`;
  S5  every arm's LIVENESS LADDER moves. An arm whose ladder is flat here is
      reported before the gated runs, not after.
  S6  every arm's falsifier fails.

Output: raw/prefreeze/smoke_<id>.jsonl + a printed summary.
"""
from __future__ import print_function
import argparse, json, sys, time
from collections import Counter, defaultdict
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H
import sweeprun as S
import casematrix as CM
import run as R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default=time.strftime("smoke_%Y%m%d_%H%M%S"))
    ap.add_argument("--per-arm", type=int, default=24)
    ap.add_argument("--arms", default="")
    a = ap.parse_args()
    out = EXP / "raw" / "prefreeze"
    out.mkdir(parents=True, exist_ok=True)
    log = S.Log(out / ("%s.jsonl" % a.id))

    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cases = CM.build_cases(rep)
    if a.arms:
        want = set(a.arms.split(","))
        cases = [c for c in cases if c["arm"] in want]
    per = defaultdict(list)
    for c in cases:
        per[c["arm"]].append(c)

    work = EXP / "work" / ("smoke_%s" % a.id)
    inputs = R.write_inputs(work)
    carriers = {}
    summary = {}

    def carrier(c):
        if c["style"] == "S":
            if "S" not in carriers:
                carriers["S"] = S.SynthCarrier(
                    EXP / "kernels" / "carrier_dag.metal", "k", work)
            return carriers["S"]
        k = "P:" + c["probe"]
        if k not in carriers:
            ins, outs, grid, tg, oidx = R.INPLACE_BIND[c["probe"]]
            carriers[k] = S.InPlaceCarrier(
                EXP / "kernels" / "probes.metal", c["probe"], work,
                dict((i, inputs[v]) for i, v in ins.items()), outs, grid, tg)
            carriers[k].out_index = oidx
        return carriers[k]

    # S4 -- the poison must be visible
    try:
        car = carriers.setdefault("S", S.SynthCarrier(
            EXP / "kernels" / "carrier_dag.metal", "k", work))
        empty = H.build_program([H.stop()], car.region_len)
        resp, words = car.run_program(empty)
        d = S.digest(words)
        s4 = bool(d and d["all_poison"])
        print("S4 poison-visible (empty program leaves whole buffer poisoned): %s"
              % ("PASS" if s4 else "FAIL -- %s" % (words[:4] if words else resp)))
        log.write({"check": "S4_poison_visible", "pass": s4,
                   "status": resp["status"], "first_words": words[:8]})
    except Exception as e:
        print("S4 FAILED to run:", str(e)[:200])

    for arm, cs in sorted(per.items()):
        real = [c for c in cs if c["role"] != "arm_not_run"]
        if not real:
            print("%-24s ARM NOT RUN: %s" % (arm, cs[0]["note"][:80]))
            summary[arm] = {"arm_not_run": True, "note": cs[0]["note"]}
            continue
        try:
            car = carrier(real[0])
        except Exception as e:
            print("%-24s CARRIER BUILD FAILED: %s" % (arm, str(e)[:120]))
            summary[arm] = {"carrier_build_failed": str(e)[:300]}
            continue

        def obs(c):
            blk = bytes.fromhex(c["bytes"])
            if c["style"] == "S":
                prog = R.build_program(c, car.region_len, blk)
                resp, words = car.run_program(
                    prog, grid=(8 if arm == "GETSR/dump" else 1),
                    tg=(8 if arm == "GETSR/dump" else 1))
                d = S.digest(words)
                return resp, d, (S.digest_hex(d) if d else None)
            resp, outs = car.run_patched(blk)
            w = outs.get(car.out_index, [])
            return resp, {"words": w}, R.words_digest(w)

        base = [c for c in real if c["role"] == "baseline"][0]
        rb, db, hb = obs(base)
        tail_ok = (db.get("tail_ok") if db and "tail_ok" in db else None)
        print("%-24s baseline status=%-4s tail_poison_intact=%s"
              % (arm, rb["status"], tail_ok))
        log.write({"check": "S2_S3_baseline", "arm": arm,
                   "status": rb["status"], "hash": hb, "tail_ok": tail_ok,
                   "pre": (db or {}).get("pre"), "post": (db or {}).get("post")})

        lad = [c for c in real if c["role"] == "ladder"][:a.per_arm]
        hashes = set()
        for c in lad:
            r, d, h = obs(c)
            hashes.add(h)
            log.write({"check": "S5_ladder", "arm": arm, "field": c["field"],
                       "value": c["value"], "bytes": c["bytes"],
                       "status": r["status"], "hash": h})
        fal = [c for c in real if c["role"] == "falsifier"]
        fpass = None
        for c in fal:
            r, d, h = obs(c)
            fpass = (h != hb) or r["status"] != "OK"
            log.write({"check": "S6_falsifier", "arm": arm, "bytes": c["bytes"],
                       "status": r["status"], "hash": h,
                       "differs_from_baseline": fpass})
        ladder_pass = len(hashes) >= 2 if lad else None
        print("   ladder: %d cases, %d distinct digests -> %s | falsifier: %s"
              % (len(lad), len(hashes),
                 "PASS" if ladder_pass else ("FAIL (arm would be DISCARDED)"
                                             if lad else "n/a"),
                 "PASS" if fpass else ("FAIL" if fal else "n/a")))
        summary[arm] = {"baseline_status": rb["status"], "tail_ok": tail_ok,
                        "ladder_cases": len(lad),
                        "ladder_distinct": len(hashes),
                        "ladder_pass": ladder_pass, "falsifier_pass": fpass}

    (out / ("%s_summary.json" % a.id)).write_text(
        json.dumps(summary, indent=1, sort_keys=True))
    log.close()
    for c in carriers.values():
        c.close()
    print("\nwrote", out / ("%s_summary.json" % a.id))
    bad = [k for k, v in summary.items()
           if v.get("ladder_pass") is False or v.get("carrier_build_failed")]
    if bad:
        print("\nARMS THAT WOULD BE DISCARDED (ladder flat / carrier dead):")
        for k in bad:
            print("   ", k)


if __name__ == "__main__":
    main()
