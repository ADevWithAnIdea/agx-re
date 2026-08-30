#!/usr/bin/env python3
"""EXP-0161 fault adjudication (FIELD-SWEEP-PROTOCOL section 7A).

`fault` and `hang` are the one verdict class where the cheap mitigations are
insufficient: EXP-0153 found five cases that passed majority-of-3 AND agreed
across two independent unlocked runs and still were not faults. This script
re-runs EVERY case whose two gated runs agreed on `fault`/`hang`, five times
each, in a dedicated process, and records:

  * the OS fault-classification string for every attempt;
  * the majority outcome over the five;
  * the POISON census of the read-back buffer, which settles many cases
    offline: a buffer that is poison EVERYWHERE proves the program never
    stored, while a buffer that is poison only after the pre-test sentinel
    proves the program ran and the following store did not.

  python3 harness/adjudicate.py --run g17p_YYYYMMDD_adjNN

Writes `raw/<run>/sweep.jsonl` and `analysis/adjudication.json`.
"""
from __future__ import print_function

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H   # noqa: E402
import sweeprun as S      # noqa: E402
import cases as CM        # noqa: E402
import run as R           # noqa: E402

REPEATS = 5


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--runs", default="g17p_20260829_run01,g17p_20260829_run02")
    ap.add_argument("--extra", default="")
    ap.add_argument("--sample", type=int, default=0,
                    help="adjudicate a STRATIFIED SAMPLE of this many cases "
                         "instead of all of them. Re-running every fault costs "
                         "5 dispatches each, and a large fraction of this "
                         "experiment's faults are contained `...ErrorHang`s "
                         "that RESET THE DEVICE for every other agent. No field "
                         "verdict in analysis/field_verdicts.json rests on a "
                         "`fault` classification (accepted sets are `ok` sets), "
                         "so a stratified sample is the proportionate way to "
                         "measure how trustworthy the unlocked-run `fault` "
                         "counts are.")
    a = ap.parse_args()
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())

    idx = {}
    names = a.runs.split(",") + ([a.extra] if a.extra else [])
    per = []
    for nm in names:
        p = EXP / "raw" / nm / "sweep.jsonl"
        if not p.exists():
            continue
        per.append(dict((json.loads(l)["idx"], json.loads(l)) for l in open(str(p))))
    if len(per) < 2:
        raise SystemExit("need at least two gated runs")
    want = []
    for i, r in per[0].items():
        others = [p.get(i) for p in per[1:] if p.get(i)]
        if not others:
            continue
        if all(o["outcome"] == r["outcome"] for o in others) and \
           r["outcome"] in ("fault", "hang"):
            want.append(r)
    print("fault/hang cases agreeing across the gated pair:", len(want))
    if a.sample and len(want) > a.sample:
        strata = {}
        for r in want:
            strata.setdefault((r["arm"], r["field"]), []).append(r)
        keys = sorted(strata)
        picked, i = [], 0
        while len(picked) < a.sample:
            progressed = False
            for k in keys:
                if i < len(strata[k]):
                    picked.append(strata[k][i])
                    progressed = True
                    if len(picked) >= a.sample:
                        break
            if not progressed:
                break
            i += 1
        want = picked
        print("STRATIFIED SAMPLE: %d cases over %d (arm, field) strata"
              % (len(want), len(keys)))

    allcases = {}
    for arms, supp, danger in ((CM.ARMS, False, False), (CM.SUPP_ARMS, True, False),
                               ([], False, True)):
        for c in CM.build_cases(rep, arms=arms, include_danger=danger):
            allcases.setdefault((c["arm"], c["field"], c["value"]), c)

    rundir = EXP / "raw" / a.run
    rundir.mkdir(parents=True, exist_ok=True)
    log = S.Log(rundir / "sweep.jsonl")

    ARMDEF = dict((x["arm"], x) for x in list(CM.ARMS) + list(CM.SUPP_ARMS)
                  + [CM.DANGER_ARM])
    out = {}
    byarm = {}
    for r in want:
        byarm.setdefault(r["arm"], []).append(r)

    changed = 0
    for armname, rs in sorted(byarm.items()):
        arm = ARMDEF[armname]
        car, disp = R.make_carrier(arm, EXP / "work" / ("adj_%s" % armname), 8.0)
        ccfg = CM.CARRIERS.get(arm.get("carrier", ""), None)
        bl = allcases[(armname, "__baseline", 0)]
        base_bytes = bytes.fromhex(bl["bytes"])

        def dispatch(blk):
            if arm["style"] == "synth":
                return car.run_program(H.synth_program(arm["kind"], blk,
                                                       car.region_len), **disp)
            return car.run_inplace(0, blk, **disp)

        base = None
        for att in range(8):
            resp, outs = dispatch(base_bytes)
            if resp["status"] == "OK":
                base = (S.digest(S.words_u32(outs.get(0, b"")))
                        if arm["style"] == "synth" else R.decode_out(ccfg, outs))
                break
            time.sleep(3.0 * (att + 1))
        print("[%s] %-18s baseline %s (%d cases)"
              % (time.strftime("%H:%M:%S"), armname,
                 "OK" if base else "FAILED", len(rs)))
        for r in rs:
            c = allcases[(armname, r["field"], r["value"])]
            blk = bytes.fromhex(c["bytes"])
            atts = []
            for k in range(REPEATS):
                resp, outs = dispatch(blk)
                oc, o = R.classify(arm, resp["status"], outs, base, ccfg)
                atts.append({"status": resp["status"], "outcome": oc,
                             "error": resp["error"],
                             "victim": S.is_victim(resp["error"]),
                             "observed": o})
                time.sleep(0.05)
            nonvic = [x["outcome"] for x in atts if not x["victim"]]
            pool = nonvic if nonvic else [x["outcome"] for x in atts]
            final = max(set(pool), key=pool.count)
            n_hangstr = sum(1 for x in atts
                            if x["error"] and "ErrorHang" in x["error"])
            rec = {"idx": r["idx"], "arm": armname, "field": r["field"],
                   "value": r["value"], "bytes": c["bytes"],
                   "gated_outcome": r["outcome"], "final": final,
                   "n_repeats": REPEATS, "n_nonvictim": len(nonvic),
                   "n_os_ErrorHang": n_hangstr,
                   "attempts": atts, "outcome": final,
                   "carrier": "ADJUDICATION:%s" % armname,
                   "instr": c["instr"], "note": "section 7A re-run"}
            log.write(rec)
            out[str(r["idx"])] = {"arm": armname, "field": r["field"],
                                  "value": r["value"],
                                  "gated": r["outcome"], "final": final,
                                  "n_nonvictim": len(nonvic),
                                  "n_os_ErrorHang": n_hangstr}
            if final != r["outcome"]:
                changed += 1
        car.close()

    (EXP / "analysis" / "adjudication.json").write_text(json.dumps(
        {"_meta": {"repeats": REPEATS, "source_runs": names,
                   "n_adjudicated": len(want), "n_changed": changed,
                   "rule": "FIELD-SWEEP-PROTOCOL 7A: no fault/hang verdict is "
                           "promoted from an unlocked gated run alone"},
         "cases": out,
         "sampled": bool(a.sample),
         "sample_size": a.sample or None}, indent=1, sort_keys=True))
    log.close()
    print("adjudicated %d, verdict CHANGED for %d" % (len(want), changed))


if __name__ == "__main__":
    main()
