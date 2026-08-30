#!/usr/bin/env python3
"""EXP-0174 gated-run driver (A18 Pro / G17P).

  python3 harness/run.py --run g17p_YYYYMMDD_runNN [--order forward|reverse]
                         [--arms A,B] [--limit N]

Per case: build the program, dispatch it, append ONE FIELD-SWEEP-PROTOCOL
section-4 record IMMEDIATELY (flush + fsync). Never buffer to write at the end.

ORACLE CONVENTION. `outcome == "ok"` means "the full 16-register dump matched the
HOST-COMPUTED prediction". For this experiment the prediction is MOVEMENT: the
model in `cases.model_move()` says exactly which slot changes and to what. Cases
the model does not cover carry `predicts = "no_model"` and are scored
structurally against the unmutated block-state; they can falsify the model but
never confirm it. Every record ALSO carries `moved` and `moved_slots` against the
host-known state, so the audit's own metric is recomputable from the raw without
knowing the convention.

Safety (FIELD-SWEEP-PROTOCOL section 7/8, binding):
  * majority-of-3 before any `fault` / `hang` is recorded;
  * the OS fault-classification string on EVERY non-ok case;
  * `InnocentVictim`-class failures flagged and re-run, never scored;
  * `validity` separate from `outcome`; an all-poison read-back, a failed
    sentinel or a clobbered tail is `invalid_*` and is RE-RUN;
  * a per-arm HANG BUDGET: after 2 genuine hangs an arm STOPS and is PARTIAL;
  * the read-back buffer poisoned with 0xDEADBEEF before every dispatch;
  * the unmutated baseline re-validated every BASELINE_EVERY cases.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import os
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
import cases as CM           # noqa: E402

CARRIER = EXP / "kernels" / "carrier_n3.metal"
BASELINE_EVERY = 400
RETRIES = 3
REQ_TIMEOUT = 8.0
MAX_HANGS_PER_ARM = 2
HANG_COOLDOWN_S = 2.0


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def gpu_activity():
    """Record concurrent GPU activity so 'the machine was quiet' is a
    measurement rather than a claim (FIELD-SWEEP-PROTOCOL section 7)."""
    try:
        out = subprocess.run(["/bin/ps", "-Ao", "pid,pcpu,comm"],
                             stdout=subprocess.PIPE, timeout=15).stdout.decode()
        keep = [ln for ln in out.splitlines()
                if any(k in ln for k in ("agxrun", "gfrun", "MTLCompiler",
                                         "python3", "shdump", "WindowServer"))]
        return keep[:80]
    except Exception as e:
        return ["ps failed: %s" % e]


def run_once(carrier, plan, blk, timeout=REQ_TIMEOUT):
    prog = H.synth_program(plan, blk, carrier.region_len, wide=CM.WIDE)
    resp, words = carrier.run_program(prog, timeout=timeout)
    d = S.digest(words)
    return resp, d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--order", default="forward", choices=("forward", "reverse"))
    ap.add_argument("--arms", default="")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    outdir = EXP / "raw" / args.run
    outdir.mkdir(parents=True, exist_ok=True)
    work = EXP / "work" / ("run_%s" % args.run)

    H.assert_geometry()
    allcases = CM.build_cases()
    mhash = CM.matrix_sha256(allcases)
    if args.arms:
        want = set(a.strip() for a in args.arms.split(","))
        allcases = [c for c in allcases if c["arm"] in want]
    if args.order == "reverse":
        allcases = list(reversed(allcases))
    if args.limit:
        allcases = allcases[:args.limit]

    carrier = S.SynthCarrier(CARRIER, "k", work, timeout=REQ_TIMEOUT)
    env = {
        "run": args.run, "order": args.order,
        "host": platform.node(), "platform": platform.platform(),
        "device": carrier.device,
        "region_off": carrier.region_off, "region_len": carrier.region_len,
        "matrix_sha256": mhash, "n_cases": len(allcases),
        "db_sha256": sha(H.ISA_DIR / "db.json"),
        "isadb_sha256": sha(H.ISA_DIR / "isadb.py"),
        "carrier_sha256": sha(CARRIER),
        "isa_helpers_sha256": sha(HERE / "isa_helpers.py"),
        "cases_sha256": sha(HERE / "cases.py"),
        "sweeprun_sha256": sha(HERE / "sweeprun.py"),
        "run_sha256": sha(HERE / "run.py"),
        "plans": {k: v.as_dict() for k, v in H.PLANS.items()},
        "seed_i": H.SEED_I, "wide": list(CM.WIDE),
        "t_start": time.time(),
    }
    (outdir / "00_env.json").write_text(json.dumps(env, indent=1, sort_keys=True))
    (outdir / "01_gpuwatch_start.json").write_text(json.dumps(gpu_activity(), indent=1))
    log = S.Log(outdir / "sweep.jsonl")
    blog = S.Log(outdir / "baseline.jsonl")

    # ---- baseline: the unmutated program, per plan --------------------
    def baseline(kind):
        for pname in CM.PLANS:
            plan = H.PLANS[pname]
            resp, d = run_once(carrier, plan, b"")
            ref = CM.dump_of(plan, CM.block_state(plan))
            blog.write({"kind": kind, "plan": pname, "status": resp["status"],
                        "validity": S.validity_of(resp["status"],
                                                  resp.get("error"), d),
                        "regs": (d["regs"] if d else None), "ref": ref,
                        "match": (d is not None and d["regs"] == ref),
                        "pre": (d["pre"] if d else None),
                        "post": (d["post"] if d else None),
                        "error": (resp.get("error") or "")[:300]})
    baseline("initial")

    hangs = {}
    stopped = set()
    t0 = time.time()
    for i, c in enumerate(allcases):
        if c["arm"] in stopped:
            log.write({"instr": "n3_mov", "field": c["field"], "value": c["value"],
                       "bytes": c["bytes"], "observed": None, "oracle": c["expect"],
                       "match": False, "outcome": "hang", "validity": "invalid_nodata",
                       "carrier": "%s/%s" % (c["arm"], c["plan"]),
                       "arm": c["arm"], "plan": c["plan"],
                       "note": "ARM STOPPED on hang budget -- NOT dispatched",
                       "skipped": True})
            continue
        plan = H.PLANS[c["plan"]]
        blk = bytes.fromhex(c["bytes"])
        attempts = []
        d = None
        resp = None
        for k in range(RETRIES):
            resp, d = run_once(carrier, plan, blk)
            val = S.validity_of(resp["status"], resp.get("error"), d)
            attempts.append({"status": resp["status"], "validity": val,
                             "os_class": S.os_class(resp.get("error")),
                             "hash": S.digest_hex(d)})
            if val == "valid" and resp["status"] == "OK":
                break
            if val == "invalid_victim":
                time.sleep(0.15)
                continue
            if resp["status"] in ("HANG",):
                time.sleep(HANG_COOLDOWN_S)
                continue
            if val.startswith("invalid"):
                continue
            break
        val = S.validity_of(resp["status"], resp.get("error"), d)
        if resp["status"] == "HANG":
            hangs[c["arm"]] = hangs.get(c["arm"], 0) + 1
            if hangs[c["arm"]] >= MAX_HANGS_PER_ARM:
                stopped.add(c["arm"])

        ref = CM.block_state(plan)
        refdump = CM.dump_of(plan, ref)
        observed = (d["regs"] if d else None)
        exp = c["expect"]
        if resp["status"] != "OK":
            outcome = "hang" if resp["status"] == "HANG" else "fault"
            match = False
        elif d is None:
            outcome, match = "undecodable", False
        elif c["undecidable"]:
            outcome, match = "undecidable", (observed == exp)
        elif c["predicts"] in ("move", "narrow", "no_move") and exp is not None:
            match = (observed == exp)
            if match:
                outcome = "ok"
            else:
                bad = [j for j in range(H.N_REGS) if observed[j] != exp[j]]
                outcome = ("silent_zero" if all(observed[j] == 0 for j in bad)
                           else "wrong_value")
        else:
            match = (observed == refdump)
            outcome = "ok" if match else "wrong_value"

        log.write({
            "instr": "n3_mov", "field": c["field"], "value": c["value"],
            "bytes": c["bytes"],
            "observed": {"regs": observed, "pre": (d["pre"] if d else None),
                         "post": (d["post"] if d else None),
                         "tail_ok": (d["tail_ok"] if d else None)},
            "oracle": exp, "match": bool(match), "outcome": outcome,
            "carrier": "%s/%s" % (c["arm"], c["plan"]),
            "arm": c["arm"], "plan": c["plan"], "predicts": c["predicts"],
            "validity": val, "os_class": S.os_class(resp.get("error")),
            "gputime_ns": resp.get("gputime_ns"),
            "error": (resp.get("error") or "")[:300],
            "attempts": attempts,
            "dst": c["dst"], "b1": c["b1"], "b2": c["b2"], "b3": c["b3"],
            "start": c["start"], "width": c["width"],
            "encodable_range": c["encodable_range"],
            "blind": sorted(plan.blind), "pad_masked": sorted(plan.masked),
            "ref_dump": refdump,
            "moved": (observed != refdump) if observed else None,
            "moved_slots": S.moved_slots(d, refdump, ()) if d else None,
            "falsifier": c["falsifier"], "undecidable": c["undecidable"],
            "rt_ok": H.round_trips(blk),
            "note": c["note"], "skipped": False,
        })
        if (i + 1) % BASELINE_EVERY == 0:
            baseline("refresh")
            print("  ...%d/%d  %.1fs" % (i + 1, len(allcases), time.time() - t0))

    baseline("final")
    (outdir / "02_gpuwatch_end.json").write_text(json.dumps(gpu_activity(), indent=1))
    (outdir / "03_summary.json").write_text(json.dumps({
        "n": log.n, "hangs": hangs, "stopped_arms": sorted(stopped),
        "elapsed_s": round(time.time() - t0, 3),
        "dispatches": carrier.dispatches,
        "carrier_hangs": carrier.hangs}, indent=1))
    log.close()
    blog.close()
    carrier.close()
    print("DONE", args.run, log.n, "cases", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
