#!/usr/bin/env python3
"""EXP-0179 gated-run driver (A18 Pro / G17P).

  python3 harness/run.py --run g17p_YYYYMMDD_runNN [--order forward|reverse]
                         [--arms G,T,B3] [--limit N] [--hang-tolerant ARM]

Per case: build the program, dispatch it, append ONE FIELD-SWEEP-PROTOCOL
section-4 record IMMEDIATELY (flush + fsync). Never buffer to write at the end.

ORACLE CONVENTION. Every oracle here is HOST-COMPUTED from `isa_helpers.SEED_I`
and the frozen layout. **No oracle is a diff against a GPU baseline** -- DEF-0169-1
showed that a diff against a periodically refreshed baseline fabricates movement.
The baseline program IS re-run periodically, but only as a RUN-INTEGRITY check
(`baseline.jsonl`), never as the reference a case is scored against.

Safety (FIELD-SWEEP-PROTOCOL sections 7/8, binding):
  * majority-of-3 before any `fault` / `hang` is recorded;
  * the OS fault-classification string on EVERY non-ok case;
  * `InnocentVictim`-class failures flagged and re-run, never scored;
  * `validity` kept separate from `outcome`; an all-poison read-back, a failed
    PRE sentinel or a clobbered tail is `invalid_*` and is RE-RUN;
  * a per-arm HANG BUDGET of 2 -> the arm STOPS and is reported PARTIAL...
  * ...EXCEPT under `--hang-tolerant ARM`, the NAMED, NON-GATED mapping pass
    FIELD-SWEEP-PROTOCOL 3(c) requires when adjacent hangs suggest a CONTIGUOUS
    hazard. A per-value budget cannot characterise a contiguous hazard; it
    guarantees the region is never mapped. Such a run MUST use a run id
    containing `MAPPING_` and is never merged into a gated verdict.
  * the read-back buffer poisoned with 0xDEADBEEF before every dispatch.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. No Apple binary is disassembled.
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

CARRIER = EXP / "kernels" / "carrier_call.metal"
BASELINE_EVERY = 400
RETRIES = 3
REQ_TIMEOUT = 8.0
MAX_HANGS_PER_ARM = 2
HANG_COOLDOWN_S = 2.0
# Hang-prone arms run LAST so a stopped arm costs the least evidence.
ARM_ORDER = ["G", "T", "M", "B3", "B5", "B6", "TL", "R", "L", "O", "F", "N"]


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


def build_plan(name, extmode_or):
    b = H.PLANS[name]
    return H.Plan(b.name, idx=b.idx, sent=b.sent, pre=b.pre, pad=b.pad,
                  callee=b.callee, post=b.post, extmode_or=extmode_or)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--order", default="forward", choices=("forward", "reverse"))
    ap.add_argument("--arms", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--hang-tolerant", default="",
                    help="comma-separated arms to run with the hang budget "
                         "DELIBERATELY OVERRIDDEN (FIELD-SWEEP-PROTOCOL 3c). "
                         "The run id must contain MAPPING_.")
    args = ap.parse_args()

    add = CM.load_addendum()
    if "_PROVISIONAL" in add:
        raise SystemExit("REFUSING TO DISPATCH: work/addendum.json is the local "
                         "placeholder. Run harness/calib.py on the device first.")
    tolerant = set(a.strip() for a in args.hang_tolerant.split(",") if a.strip())
    if tolerant and "MAPPING_" not in args.run:
        raise SystemExit("A hang-tolerant mapping pass must have MAPPING_ in its "
                         "run id (FIELD-SWEEP-PROTOCOL 3c).")

    outdir = EXP / "raw" / args.run
    outdir.mkdir(parents=True, exist_ok=True)
    work = EXP / "work" / ("run_%s" % args.run)

    n_geo = H.assert_geometry()
    allcases = CM.build_cases(add)
    mhash = CM.matrix_sha256(allcases)
    order_key = {a: i for i, a in enumerate(ARM_ORDER)}
    allcases.sort(key=lambda c: (order_key.get(c["arm"], 99), c["carrier"]))
    if args.arms:
        want = set(a.strip() for a in args.arms.split(",") if a.strip())
        allcases = [c for c in allcases if c["arm"] in want]
    if args.order == "reverse":
        allcases = list(reversed(allcases))
    if args.limit:
        allcases = allcases[:args.limit]

    carrier = S.SynthCarrier(CARRIER, "k", work, timeout=REQ_TIMEOUT)
    if carrier.region_len != add["region_len"]:
        raise SystemExit("region_len drift: carrier %d vs frozen addendum %d"
                         % (carrier.region_len, add["region_len"]))
    plans = {n: build_plan(n, add["extmode_or"]) for n in H.PLANS}

    env = {
        "run": args.run, "order": args.order, "arms": args.arms,
        "hang_tolerant": sorted(tolerant),
        "host": platform.node(), "platform": platform.platform(),
        "device": carrier.device,
        "region_off": carrier.region_off, "region_len": carrier.region_len,
        "matrix_sha256": mhash, "n_cases": len(allcases),
        "geometry_checks": n_geo,
        "addendum": add,
        "db_sha256": sha(H.ISA_DIR / "db.json"),
        "isadb_sha256": sha(H.ISA_DIR / "isadb.py"),
        "carrier_sha256": sha(CARRIER),
        "isa_helpers_sha256": sha(HERE / "isa_helpers.py"),
        "cases_sha256": sha(HERE / "cases.py"),
        "sweeprun_sha256": sha(HERE / "sweeprun.py"),
        "run_sha256": sha(HERE / "run.py"),
        "plans": {k: v.as_dict() for k, v in plans.items()},
        "seed_i": H.SEED_I,
        "markers": {"CALLEE_CONST": H.CALLEE_CONST, "POSTCALL": H.POSTCALL,
                    "LADDER_R": list(H.LADDER_R), "LADDER_V": list(H.LADDER_V),
                    "INNER_CONST": H.INNER_CONST, "INNER_POST": H.INNER_POST},
        "words": {"W_REG0": H.W_REG0, "W_PRE": H.W_PRE, "W_POST": H.W_POST,
                  "W_CALLEE": H.W_CALLEE, "W_TAIL": H.W_TAIL,
                  "OUT_WORDS": H.OUT_WORDS},
        "t_start": time.time(),
    }
    (outdir / "00_env.json").write_text(json.dumps(env, indent=1, sort_keys=True))
    (outdir / "01_gpuwatch_start.json").write_text(json.dumps(gpu_activity(), indent=1))
    log = S.Log(outdir / "sweep.jsonl")
    blog = S.Log(outdir / "baseline.jsonl")

    # arm O only. A RAMP, so whichever word the load actually reaches is
    # self-identifying; word 0 is the one the frozen `load_reg(..., 0)` targets.
    # Sized well past anything the (overwritten) carrier body could have read.
    mem_in = carrier.write_input("mem", [0x600D0000 + i for i in range(512)])

    def run_case(c, timeout=REQ_TIMEOUT):
        plan = plans[c["plan"]]
        build = dict(c["build"])
        prog, lay = H.synth_call_program(plan, carrier.region_len, **build)
        extra = {H.SLOT_MEM: mem_in} if build.get("order_load") else None
        resp, words = carrier.run_program(prog, timeout=timeout, extra_ins=extra)
        d = S.digest(words)
        return resp, d, lay, prog

    def baseline(kind):
        for pname in ("idx15", "idx7"):
            plan = plans[pname]
            prog, lay = H.synth_call_program(
                plan, carrier.region_len, marker=add["marker"],
                reconverge=add["reconverge"])
            resp, words = carrier.run_program(prog)
            d = S.digest(words)
            outcome, facts = S.classify_call(resp["status"], d, plan)
            blog.write({"kind": kind, "plan": pname, "status": resp["status"],
                        "validity": S.validity_of(resp["status"],
                                                  resp.get("error"), d),
                        "outcome": outcome, "facts": facts,
                        "regs": (d["regs"] if d else None),
                        "expected": H.expected_dump(plan),
                        "pre": (d["pre"] if d else None),
                        "post": (d["post"] if d else None),
                        "callee_word": (d["callee_word"] if d else None),
                        "layout": lay,
                        "NOTE": "RUN-INTEGRITY ONLY. No case is scored against "
                                "this; every oracle is host-computed.",
                        "error": (resp.get("error") or "")[:300]})
    baseline("initial")

    hangs = {}
    stopped = set()
    t0 = time.time()
    for i, c in enumerate(allcases):
        arm = c["arm"]
        plan = plans[c["plan"]]
        if arm in stopped:
            log.write({"instr": c["instr"], "field": c["field"],
                       "value": c["value"], "bytes": None, "observed": None,
                       "oracle": None, "match": False, "outcome": "hang",
                       "validity": "invalid_nodata", "arm": arm,
                       "carrier": "%s/%s" % (c["carrier"], c["plan"]),
                       "plan": c["plan"], "skipped": True,
                       "note": "ARM STOPPED on hang budget -- NOT dispatched"})
            continue
        attempts = []
        d = None
        resp = None
        lay = None
        prog = None
        for k in range(RETRIES):
            resp, d, lay, prog = run_case(c)
            val = S.validity_of(resp["status"], resp.get("error"), d)
            attempts.append({"status": resp["status"], "validity": val,
                             "os_class": S.os_class(resp.get("error")),
                             "restarts": resp.get("restarts"),
                             "discarded_lines": resp.get("discarded_lines"),
                             "malformed_total": resp.get("malformed_total"),
                             "raw": resp.get("raw"),
                             "hash": S.digest_hex(d)})
            if val == "valid" and resp["status"] == "OK":
                break
            if val == "invalid_victim":
                time.sleep(0.15)
                continue
            if resp["status"] == "HANG":
                time.sleep(HANG_COOLDOWN_S)
                continue
            if val.startswith("invalid"):
                continue
            break
        val = S.validity_of(resp["status"], resp.get("error"), d)
        if resp["status"] == "HANG":
            hangs[arm] = hangs.get(arm, 0) + 1
            if hangs[arm] >= MAX_HANGS_PER_ARM and arm not in tolerant:
                stopped.add(arm)

        outcome, facts = S.classify_call(
            resp["status"], d, plan,
            expect_called=c["expect_called"],
            expect_returned=c["expect_returned"],
            expect_rung=c["expect_rung"])
        exp_dump = H.expected_dump(plan, called=c["expect_called"],
                                   returned=c["expect_returned"],
                                   rungs_from=c["expect_rung"])

        # The instruction under test, isolated, for `bytes` and `distinct_bytes`.
        if c["instr"] == "call":
            ut = lay["call_hex"]
        else:
            ut = lay["ret_hex"]

        log.write({
            "instr": c["instr"], "field": c["field"], "value": c["value"],
            "bytes": ut,
            "observed": {"regs": (d["regs"] if d else None),
                         "pre": (d["pre"] if d else None),
                         "post": (d["post"] if d else None),
                         "callee_word": (d["callee_word"] if d else None),
                         "tail_ok": (d["tail_ok"] if d else None)},
            "oracle": exp_dump,
            "match": bool(facts.get("match")), "outcome": outcome,
            "facts": facts,
            "carrier": "%s/%s" % (c["carrier"], c["plan"]),
            "arm": arm, "plan": c["plan"], "nested": c["nested"],
            "marker": c["marker"], "reconverge": c["reconverge"],
            "validity": val, "os_class": S.os_class(resp.get("error")),
            "gputime_ns": resp.get("gputime_ns"),
            "error": (resp.get("error") or "")[:300],
            "status": resp["status"],
            "restarts": resp.get("restarts"),
            "discarded_lines": resp.get("discarded_lines"),
            "malformed_total": resp.get("malformed_total"),
            "resp_raw": resp.get("raw"),
            "attempts": attempts,
            "start": c["start"], "width": c["width"],
            "encodable_range": c["encodable_range"],
            "expect_called": c["expect_called"],
            "expect_returned": c["expect_returned"],
            "expect_rung": c["expect_rung"],
            "falsifier": c["falsifier"], "hang_candidate": c["hang_candidate"],
            "blind": sorted(plan.blind), "pad_masked": sorted(plan.masked),
            "layout": lay,
            "rt_ok": H.round_trips(bytes.fromhex(ut)),
            "note": c["note"], "skipped": False,
        })
        if (i + 1) % BASELINE_EVERY == 0:
            baseline("refresh")
            print("  ...%d/%d  %.1fs  hangs=%s"
                  % (i + 1, len(allcases), time.time() - t0, hangs))

    baseline("final")
    (outdir / "02_gpuwatch_end.json").write_text(json.dumps(gpu_activity(), indent=1))
    (outdir / "03_summary.json").write_text(json.dumps({
        "n": log.n, "hangs": hangs, "stopped_arms": sorted(stopped),
        "elapsed_s": round(time.time() - t0, 3),
        "dispatches": carrier.dispatches,
        "carrier_hangs": carrier.hangs,
        "runner_restarts": getattr(carrier.runner, "restarts", None),
        "runner_malformed": getattr(carrier.runner, "malformed", None),
        "runner_discarded_lines": getattr(carrier.runner, "discarded_lines", None),
        "def_0178_1": ("leak-free runner (harness/saferunner.py) in use; a MALFORMED "
                       "response is invalid_malformed and is RE-RUN, never scored"),
        "values_dispatched_note": "per-field counts are recomputed by "
                                  "analysis/analyze.py from sweep.jsonl"}, indent=1))
    log.close()
    blog.close()
    carrier.close()
    print("DONE", args.run, log.n, "cases", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
