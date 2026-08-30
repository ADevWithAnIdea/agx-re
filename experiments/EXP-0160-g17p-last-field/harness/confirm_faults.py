#!/usr/bin/env python3
"""EXP-0160 fault adjudication (FIELD-SWEEP-PROTOCOL section 7A, MANDATORY).

  ~/agxre/gpulease.sh EXP-0160 900 -- python3 harness/confirm_faults.py \
        --run g17p_YYYYMMDD_confirmNN --from raw/<runA> raw/<runB> [--reps 5]

EXP-0153 established that majority-of-3 AND cross-run agreement are BOTH
insufficient for a `fault` verdict: five cases passed both and, re-run in
isolation, four were not faults at all. So every case whose UNLOCKED outcome was
`fault`, `hang` or `undecodable` in either gated run is re-run here `--reps`
times under the device lease, and the ISOLATED verdict is what the analysis
uses. Cases are identified by (arm, field, value, sset); their bytes are rebuilt
from the same frozen matrix, never copied from the log.

Records go to `raw/<run>/confirm.jsonl`, same schema plus `rep`.
"""
from __future__ import print_function

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H      # noqa: E402
import sweeprun as S         # noqa: E402
import casematrix as CM      # noqa: E402

SUSPECT = ("fault", "hang", "undecodable")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--from", dest="src", nargs="+", required=True)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--timeout", type=float, default=8.0)
    a = ap.parse_args()

    want = set()
    for d in a.src:
        p = Path(d)
        if not p.is_absolute():
            p = EXP / d
        for ln in (p / "sweep.jsonl").open():
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r["outcome"] in SUSPECT:
                want.add(r["idx"])
    print("suspect cases to adjudicate:", len(want))

    rundir = EXP / "raw" / a.run
    rundir.mkdir(parents=True, exist_ok=True)
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cases = {c["idx"]: c for c in CM.build_cases(rep)}

    done = Counter()
    jl = rundir / "confirm.jsonl"
    if jl.exists():
        for ln in jl.open():
            try:
                done[json.loads(ln)["idx"]] += 1
            except Exception:
                pass

    car = S.Carrier(EXP / "kernels" / "carrier_dag.metal", "k",
                    EXP / "work" / ("run_%s" % a.run), timeout=a.timeout)
    (rundir / "00_env.json").write_text(json.dumps(
        {"target": "G17P", "device": car.device, "isolated": "gpulease.sh",
         "reps": a.reps, "sources": a.src,
         "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        indent=1, sort_keys=True))
    log = S.Log(jl)

    baselines = {}
    for idx in sorted(want):
        c = cases[idx]
        main_b = bytes.fromhex(rep[c["probe"]]["main_hex"])
        blk0 = main_b[c["block_lo"]:c["block_hi"]]
        key = (c["arm"], c["sset"])
        if key not in baselines or baselines[key] is None:
            # AMENDMENT 01 (2026-08-30): retry the arm baseline. In
            # raw/g17p_20260830_confirm01 a single victim-class failure on the
            # F3_OP/seed-set-2 baseline made every one of that arm's 32 cases
            # `undecodable`, because there was nothing to compare against. A
            # baseline is not evidence about an encoding, so retrying it is not
            # a change of method -- but it IS a change of a frozen file, so the
            # re-adjudication runs under a NEW run id (confirm02) and
            # confirm01 is retained untouched.
            prog = H.synth_program(c["kind"], blk0, car.region_len, c["sset"])
            d = None
            for att in range(8):
                resp, words = car.run_program(prog)
                if resp["status"] == "OK":
                    d = S.digest(words)
                    break
                if S.is_victim(resp["error"]):
                    time.sleep(3.0 * (att + 1))
                    if att == 3:
                        car.restart()
            baselines[key] = d
        base = baselines[key]
        blk = bytes.fromhex(c["bytes"])
        prog = H.synth_program(c["kind"], blk, car.region_len, c["sset"])
        for rep_i in range(done[idx], a.reps):
            resp, words = car.run_program(prog)
            d = S.digest(words) if resp["status"] == "OK" and words else None
            oc = S.classify(resp["status"], d, base) if base else "undecodable"
            log.write({"idx": idx, "rep": rep_i, "arm": c["arm"],
                       "instr": c["instr"], "field": c["field"],
                       "value": c["value"], "sset": c["sset"],
                       "bytes": c["bytes"], "outcome": oc,
                       "observed": {"digest": S.digest_hex(d) if d else None,
                                    "regs": d["regs"] if d else None,
                                    "pre": d["pre"] if d else None,
                                    "post": d["post"] if d else None},
                       "oracle": {"digest": S.digest_hex(base) if base else None},
                       "match": bool(d and base and d["regs"] == base["regs"]),
                       "poison_words": S.poison_count(d),
                       "frame": ("break" if (d and S.poison_count(d)) else "intact"),
                       "status": resp["status"], "error": resp["error"],
                       "victim": S.is_victim(resp["error"]),
                       "carrier": "SYNTH+LIFTED:%s@%s[%d:%d]"
                                  % (c["probe"], c["instr"], c["block_lo"],
                                     c["block_hi"]),
                       "note": "isolated re-run under gpulease.sh"})
    log.close(); car.close()
    print("DONE")


if __name__ == "__main__":
    main()
