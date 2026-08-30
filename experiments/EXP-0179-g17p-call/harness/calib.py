#!/usr/bin/env python3
"""EXP-0179 PRE-FREEZE calibration. Everything this writes lands under
`raw/prefreeze/` and is **NEVER EVIDENCE** for any verdict.

Its only job is to measure the FOUR parameters PRE_REGISTRATION section 8
permits calibration to decide, and to prove the carrier can see a difference
before the gate runs:

  1. `extmode_or` for `device_store` (db.json declares `2*R` and `2*R|0xC0`);
  2. whether the `43 00 00 01` frame marker and/or the `0f 06` reconverge are
     REQUIRED for a generated call to work at all;
  3. the carrier's `_agc.main` region length (measured, not guessed);
  4. whether a generated forward `jump` over a callee works, which is what a
     BACKWARD call displacement would need.

It also runs falsifiers F1 (the landing ladder must resolve a 2-byte target
shift) and F2 (replacing the call with no-ops must remove the callee's effect).
A carrier that cannot see a difference is caught HERE, not after the gate.

Usage (on the neo):
  python3 harness/calib.py --run calib_<id>

CLEAN-ROOM: OWN-SHADER + HW-PROBE. No Apple binary is disassembled.
"""
from __future__ import print_function

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H   # noqa: E402
import sweeprun as S      # noqa: E402

CARRIER = EXP / "kernels" / "carrier_call.metal"
REQ_TIMEOUT = 8.0


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def one(carrier, plan, log, label, timeout=REQ_TIMEOUT, **kw):
    exp_called = kw.pop("_exp_called", True)
    exp_returned = kw.pop("_exp_returned", True)
    exp_rung = kw.pop("_exp_rung", None)
    prog, lay = H.synth_call_program(plan, carrier.region_len, **kw)
    resp, words = carrier.run_program(prog, timeout=timeout)
    d = S.digest(words)
    val = S.validity_of(resp["status"], resp.get("error"), d)
    outcome, facts = S.classify_call(
        resp["status"], d, plan, expect_called=exp_called,
        expect_returned=exp_returned, expect_rung=exp_rung)
    rec = {"label": label, "plan": plan.name, "status": resp["status"],
           "validity": val, "outcome": outcome, "facts": facts,
           "layout": lay, "regs": (d["regs"] if d else None),
           "pre": (d["pre"] if d else None), "post": (d["post"] if d else None),
           "callee_word": (d["callee_word"] if d else None),
           "tail_ok": (d["tail_ok"] if d else None),
           "os_class": S.os_class(resp.get("error")),
           "error": (resp.get("error") or "")[:300],
           "gputime_ns": resp.get("gputime_ns"),
           "expected_dump": H.expected_dump(plan)}
    log.write(rec)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--plan", default="idx15")
    args = ap.parse_args()

    outdir = EXP / "raw" / "prefreeze" / args.run
    outdir.mkdir(parents=True, exist_ok=True)
    work = EXP / "work" / ("calib_%s" % args.run)

    n_geo = H.assert_geometry()
    carrier = S.SynthCarrier(CARRIER, "k", work, timeout=REQ_TIMEOUT)
    log = S.Log(outdir / "calib.jsonl")

    env = {"run": args.run, "host": platform.node(),
           "platform": platform.platform(), "device": carrier.device,
           "region_off": carrier.region_off, "region_len": carrier.region_len,
           "geometry_checks": n_geo,
           "db_sha256": sha(H.ISA_DIR / "db.json"),
           "isadb_sha256": sha(H.ISA_DIR / "isadb.py"),
           "carrier_sha256": sha(CARRIER),
           "isa_helpers_sha256": sha(HERE / "isa_helpers.py"),
           "t_start": time.time(),
           "NOTE": "PRE-FREEZE. Never evidence for any verdict."}
    (outdir / "00_env.json").write_text(json.dumps(env, indent=1, sort_keys=True))
    print("region_len =", carrier.region_len, " device =", carrier.device)

    results = {"region_len": carrier.region_len}
    # The bracket probe runs FIRST, with extmode_or = 0x00. If that choice were
    # wrong the probe's `ok` verdict -- which requires the WHOLE 16-register dump
    # to match the host prediction -- could not be reached at all, so an `ok`
    # here validates both the bracket and this extmode simultaneously.
    _b = H.PLANS[args.plan]
    plan0 = H.Plan(_b.name, idx=_b.idx, sent=_b.sent, pre=_b.pre, pad=_b.pad,
                   extmode_or=0x00)

    # --- 1. marker x reconverge (FIRST: calib_20260830a probed extmode with
    # reconverge=False, which FAULTS, so both extmode arms came back `fault` and
    # the choice fell through to a default. That run is retained, not reused.)
    bracket = {}
    for mk in (False, True):
        for rc in (False, True):
            r = one(carrier, plan0, log, "bracket_m%d_r%d" % (mk, rc),
                    marker=mk, reconverge=rc)
            bracket["m%d_r%d" % (mk, rc)] = {
                "outcome": r["outcome"], "status": r["status"],
                "callee_ran": r["facts"]["callee_ran"],
                "returned": r["facts"]["returned"],
                "collateral": r["facts"]["collateral"]}
            print("  marker=%d reconverge=%d -> %s callee_ran=%s returned=%s"
                  % (mk, rc, r["outcome"], r["facts"]["callee_ran"],
                     r["facts"]["returned"]))
    results["bracket_probe"] = bracket
    # the MINIMAL working combination, preferring no scaffolding at all
    chosen = None
    for key in ("m0_r0", "m0_r1", "m1_r0", "m1_r1"):
        if bracket.get(key, {}).get("outcome") == "ok":
            chosen = key
            break
    results["marker"] = bool(chosen and chosen[1] == "1")
    results["reconverge"] = bool(chosen and chosen[4] == "1")
    results["bracket_chosen"] = chosen

    # --- 2. extmode_or, probed with the WORKING bracket ---------------------
    ext_ok = {}
    for ext in (0x00, 0xC0):
        plan = H.Plan("cal_%02x" % ext, idx=15, sent=12, pre=11, pad=13,
                      extmode_or=ext)
        r = one(carrier, plan, log, "extmode_%02x" % ext,
                marker=results["marker"], reconverge=results["reconverge"])
        exp = H.expected_dump(plan)
        obs = r["regs"]
        ok = (obs is not None
              and all(obs[i] == exp[i] for i in range(H.N_REGS)
                      if i not in plan.blind))
        ext_ok[ext] = {"dump_matches_host_prediction": bool(ok),
                       "outcome": r["outcome"], "regs": obs, "expected": exp}
        print("  extmode_or=0x%02x -> %s (%s)" % (ext, ok, r["outcome"]))
    results["extmode_or_probe"] = ext_ok
    chosen_ext = 0xC0 if (ext_ok[0xC0]["dump_matches_host_prediction"]
                          and not ext_ok[0x00]["dump_matches_host_prediction"]) \
        else 0x00
    results["extmode_or"] = chosen_ext

    plan = H.Plan(_b.name, idx=_b.idx, sent=_b.sent, pre=_b.pre, pad=_b.pad,
                  extmode_or=chosen_ext)

    # --- 3. falsifiers F1 / F2 --------------------------------------------
    r = one(carrier, plan, log, "F1_delta_minus2",
            marker=results["marker"], reconverge=results["reconverge"],
            offset_delta=-2, _exp_rung=3)
    results["F1"] = {"outcome": r["outcome"], "landing": r["facts"]["landing"],
                     "fired": r["facts"]["landing"] == 3}
    print("  F1 (delta -2): landing rung =", r["facts"]["landing"])

    r = one(carrier, plan, log, "F2_call_replaced_by_pads",
            marker=results["marker"], reconverge=results["reconverge"],
            replace_call=H.nop_pad(plan) * 7, _exp_called=False)
    results["F2"] = {"outcome": r["outcome"],
                     "callee_ran": r["facts"]["callee_ran"],
                     "breadcrumb": r["facts"]["breadcrumb"],
                     "fired": (r["facts"]["callee_ran"] is False)}
    print("  F2 (call -> no-ops): callee_ran =", r["facts"]["callee_ran"])

    # --- 4. jumpover (would give a BACKWARD displacement) -------------------
    try:
        jb = H.jump_bytes(0)
        results["jumpover_probe"] = {"jump_len": len(jb),
                                     "note": "structural only; the backward-call "
                                             "carrier is out of scope unless a "
                                             "successor builds it"}
    except Exception as e:
        results["jumpover_probe"] = {"error": repr(e)}
    results["jumpover_ok"] = False

    results["frozen_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results["prefreeze_run"] = args.run
    (outdir / "01_calibration.json").write_text(
        json.dumps(results, indent=1, sort_keys=True))
    (EXP / "work" / "addendum.json").write_text(
        json.dumps({k: results[k] for k in
                    ("extmode_or", "marker", "reconverge", "region_len",
                     "jumpover_ok", "frozen_utc", "prefreeze_run")},
                   indent=1, sort_keys=True))
    log.close()
    carrier.close()
    print("CALIB DONE ->", outdir)
    print(json.dumps({k: results[k] for k in
                      ("extmode_or", "marker", "reconverge", "region_len")},
                     sort_keys=True))


if __name__ == "__main__":
    main()
