#!/usr/bin/env python3
"""EXP-0160 EXTENSION gated-run driver (G17P) -- identical to harness/run.py
except that it builds its cases from harness/casematrix_ext.py. run.py itself is
left byte-identical to the copy hashed in CAPTURE_CONTRACT.json.

  python3 harness/run.py --run g17p_YYYYMMDD_runNN [--arms A,B] [--order reverse]

Per case: build the synthesized program for the case's SEED SET
(seeds -> PRE sentinel -> lifted block with ONE field mutated -> 16-register
dump -> POST sentinel -> stop), dispatch it once, and append one
FIELD-SWEEP-PROTOCOL section-4 record immediately (flush + fsync).

Safety / anti-contamination (FIELD-SWEEP-PROTOCOL sections 7 and 7A, binding):
  * majority-of-3 before any `fault`/`hang` is recorded -- and 7A: a `fault`
    verdict is NEVER promoted from this unlocked run; it must be re-confirmed
    under `~/agxre/gpulease.sh` by harness/confirm_faults.py;
  * the OS fault-classification string is recorded verbatim on every non-OK
    case and `...ErrorInnocentVictim`-class failures are flagged `victim`;
  * a per-arm-and-seed-set baseline is re-validated every BASELINE_EVERY cases;
    a baseline failure restarts the child rather than logging a cascade as data;
  * the read-back buffer is poisoned with 0xDEADBEEF before every dispatch, so
    "wrote nothing" is distinguishable from "wrote zero" offline.
"""
from __future__ import print_function

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H      # noqa: E402
import sweeprun as S         # noqa: E402
import casematrix_ext as CM  # noqa: E402  (EXTENSION matrix)

BASELINE_EVERY = 250
RETRIES = 3
REQ_TIMEOUT = 8.0


def env_block(car):
    def sh(cmd):
        try:
            return subprocess.check_output(cmd, shell=True,
                                           stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return "?"
    return {
        "target": "G17P",
        "device": car.device,
        "host": platform.node(),
        "os": sh("sw_vers -productVersion") + " (" + sh("sw_vers -buildVersion") + ")",
        "machine": sh("sysctl -n hw.model"),
        "python": sys.version.split()[0],
        "region_len": car.region_len,
        "db_sha256": sh("shasum -a 256 %s | cut -d' ' -f1" % (H.ISA_DIR / "db.json")),
        "isadb_sha256": sh("shasum -a 256 %s | cut -d' ' -f1" % (H.ISA_DIR / "isadb.py")),
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--arms", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--order", default="forward", choices=("forward", "reverse"))
    a = ap.parse_args()

    rundir = EXP / "raw" / a.run
    rundir.mkdir(parents=True, exist_ok=True)
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cases = CM.build_cases(rep)
    msha = CM.matrix_sha256(cases)
    if a.arms:
        want = set(a.arms.split(","))
        cases = [c for c in cases if c["arm"] in want]
    if a.limit:
        cases = cases[:a.limit]
    if a.order == "reverse":
        # The two gated runs execute the SAME frozen matrix in opposite arm
        # order so that, running concurrently against sibling experiments, they
        # are not hitting the same illegal encodings at the same moment. A
        # contamination mitigation, not a change of matrix.
        arms = []
        for c in cases:
            if not arms or arms[-1] != c["arm"]:
                arms.append(c["arm"])
        rank = dict((n, -i) for i, n in enumerate(arms))
        cases = sorted(cases, key=lambda c: (rank[c["arm"]], c["idx"]))

    done = set()
    jl = rundir / "sweep.jsonl"
    if jl.exists():
        for ln in jl.open():
            try:
                done.add(json.loads(ln)["idx"])
            except Exception:
                pass
        print("resume: %d cases already recorded" % len(done))

    car = S.Carrier(EXP / "kernels" / "carrier_dag.metal", "k",
                    EXP / "work" / ("run_%s" % a.run), timeout=REQ_TIMEOUT)
    env = env_block(car)
    env["matrix_sha256"] = msha
    (rundir / "00_env.json").write_text(json.dumps(env, indent=1, sort_keys=True))
    log = S.Log(jl)
    blog = S.Log(rundir / "baseline.jsonl")

    baselines = {}
    counters = dict(ok=0, silent_zero=0, wrong_value=0, fault=0, hang=0,
                    undecodable=0, victim=0, sentinel_bad=0, baseline_fail=0)

    def baseline_for(key, blk, kind, sset, force=False):
        if key in baselines and not force:
            return baselines[key]
        prog = H.synth_program(kind, blk, car.region_len, sset)
        for att in range(8):
            resp, words = car.run_program(prog)
            if resp["status"] == "OK":
                break
            if S.is_victim(resp["error"]):
                time.sleep(5.0 * (att + 1))
                if att == 3:
                    car.restart()
        d = S.digest(words) if resp["status"] == "OK" else None
        blog.write({"key": "%s/s%d" % key if isinstance(key, tuple) else str(key),
                    "arm": key[0], "sset": key[1], "status": resp["status"],
                    "error": resp["error"],
                    "digest": S.digest_hex(d) if d else None,
                    "regs": d["regs"] if d else None,
                    "poison": S.poison_count(d),
                    "kind": "refresh" if force else "initial"})
        if d is None:
            counters["baseline_fail"] += 1
        else:
            baselines[key] = d
        return d

    n = 0
    t0 = time.time()
    cur = None
    for c in cases:
        if c["idx"] in done:
            continue
        main_b = bytes.fromhex(rep[c["probe"]]["main_hex"])
        blk0 = main_b[c["block_lo"]:c["block_hi"]]
        key = (c["arm"], c["sset"])
        if key != cur:
            cur = key
            b = baseline_for(key, blk0, c["kind"], c["sset"])
            print("[%s] arm %s seedset %d baseline %s"
                  % (time.strftime("%H:%M:%S"), c["arm"], c["sset"],
                     "OK" if b else "FAILED"))
        base = baselines.get(key)
        blk = bytes.fromhex(c["bytes"])
        prog = H.synth_program(c["kind"], blk, car.region_len, c["sset"])
        rt_ok = H.round_trips(blk)

        attempts = []
        outcome = None
        obs = None
        for k in range(RETRIES):
            resp, words = car.run_program(prog)
            d = S.digest(words) if resp["status"] == "OK" and words else None
            oc = S.classify(resp["status"], d, base) if base else "undecodable"
            attempts.append({"status": resp["status"], "outcome": oc,
                             "error": resp["error"],
                             "victim": S.is_victim(resp["error"])})
            if oc in ("ok", "silent_zero", "wrong_value"):
                outcome, obs = oc, d
                break
            if k == RETRIES - 1:
                bad = [x["outcome"] for x in attempts]
                outcome = max(set(bad), key=bad.count)
                obs = d
        victim = any(x["victim"] for x in attempts)
        sent_bad = bool(obs and (obs["pre"] != H.expected_pre()
                                 or obs["post"] != H.SENT_POST))
        counters[outcome] = counters.get(outcome, 0) + 1
        if victim:
            counters["victim"] += 1
        if sent_bad:
            counters["sentinel_bad"] += 1

        rec = {
            "idx": c["idx"], "arm": c["arm"], "instr": c["instr"],
            "field": c["field"], "value": c["value"], "sset": c["sset"],
            "bytes": c["bytes"],
            "observed": {"digest": S.digest_hex(obs) if obs else None,
                         "regs": obs["regs"] if obs else None,
                         "pre": obs["pre"] if obs else None,
                         "post": obs["post"] if obs else None},
            "oracle": {"digest": S.digest_hex(base) if base else None},
            "match": bool(obs and base and obs["regs"] == base["regs"]),
            "outcome": outcome,
            "frame": ("break" if (obs and S.poison_count(obs)) else "intact"),
            "poison_words": S.poison_count(obs),
            "carrier": "SYNTH+LIFTED:%s@%s[%d:%d]" % (c["probe"], c["instr"],
                                                      c["block_lo"], c["block_hi"]),
            "kind": c["kind"], "rt_ok": rt_ok, "victim": victim,
            "sentinel_bad": sent_bad, "attempts": attempts,
            "predict": c.get("predict", ""),
            "anchor_value": c.get("anchor_value"),
            "fstart": c.get("fstart"), "fwidth": c.get("fwidth"),
            "note": "",
        }
        log.write(rec)
        n += 1

        if n % BASELINE_EVERY == 0:
            d = baseline_for(key, blk0, c["kind"], c["sset"], force=True)
            if d is None or base is None or d["regs"] != base["regs"]:
                print("  !! baseline drift/failure at n=%d arm=%s -> restarting child"
                      % (n, c["arm"]))
                counters["baseline_fail"] += 1
                car.restart()
                baselines.pop(key, None)
                baseline_for(key, blk0, c["kind"], c["sset"])
        if n % 500 == 0:
            el = time.time() - t0
            print("  %6d/%d  %.1f case/s  %s"
                  % (n, len(cases) - len(done), n / max(el, 1e-9),
                     json.dumps(counters, sort_keys=True)))
            (rundir / "01_progress.json").write_text(
                json.dumps({"done": n, "counters": counters,
                            "elapsed_s": round(el, 1)}, indent=1, sort_keys=True))

    (rundir / "02_summary.json").write_text(json.dumps(
        {"cases": n, "counters": counters, "hangs_seen": car.hangs,
         "elapsed_s": round(time.time() - t0, 1),
         "matrix_len": len(cases), "matrix_sha256": msha}, indent=1, sort_keys=True))
    log.close(); blog.close(); car.close()
    print("DONE", n, json.dumps(counters, sort_keys=True))


if __name__ == "__main__":
    main()
