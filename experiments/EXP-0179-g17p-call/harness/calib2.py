#!/usr/bin/env python3
"""EXP-0179 AMENDMENT-01 probe: find a working second carrier.

WHY THIS EXISTS. `PRE_REGISTRATION.md` froze `C2 nested` as "one `if_push` deep".
Run01 measured that carrier to be **DEAD**: in all 256+ of its cases the PRE
sentinel wrote and then NOTHING else did -- all 16 registers, the POST sentinel
and the callee breadcrumb still `0xDEADBEEF`, status OK, tail intact. An
unconditional `if_push` with `scope_kind = 0x01` masks off the only lane of a
one-thread dispatch and nothing after it executes. That is EXP-0129's failure
(a carrier that cannot express what is being asked of it), and the honest
response is to report it, retain run01's C2 data, and register a replacement --
not to quietly reinterpret 1395 dead cases.

This probe tests candidate replacements. Everything it writes is PRE-FREEZE and
is NEVER evidence for a verdict.

CLEAN-ROOM: OWN-SHADER + HW-PROBE. No Apple binary is disassembled.
"""
from __future__ import print_function

import argparse
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


def probe(carrier, plan, log, label, grid=1, tg=1, **kw):
    prog, lay = H.synth_call_program(plan, carrier.region_len, **kw)
    resp, words = carrier.run_program(prog, grid=grid, tg=tg)
    d = S.digest(words)
    outcome, facts = S.classify_call(resp["status"], d, plan)
    rec = {"label": label, "grid": grid, "tg": tg, "status": resp["status"],
           "validity": S.validity_of(resp["status"], resp.get("error"), d),
           "outcome": outcome, "facts": facts,
           "regs": (d["regs"] if d else None),
           "pre": (d["pre"] if d else None), "post": (d["post"] if d else None),
           "callee_word": (d["callee_word"] if d else None),
           "layout": lay, "os_class": S.os_class(resp.get("error")),
           "error": (resp.get("error") or "")[:300]}
    log.write(rec)
    print("  %-34s grid=%d -> %-12s callee_ran=%s returned=%s"
          % (label, grid, outcome, facts.get("callee_ran"), facts.get("returned")))
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    outdir = EXP / "raw" / "prefreeze" / args.run
    outdir.mkdir(parents=True, exist_ok=True)
    carrier = S.SynthCarrier(CARRIER, "k",
                             EXP / "work" / ("calib2_%s" % args.run), timeout=8.0)
    log = S.Log(outdir / "calib2.jsonl")
    (outdir / "00_env.json").write_text(json.dumps(
        {"run": args.run, "host": platform.node(), "device": carrier.device,
         "region_len": carrier.region_len, "t": time.time(),
         "NOTE": "PRE-FREEZE amendment probe. Never evidence."}, indent=1))

    b = H.PLANS["idx7"]
    plan = H.Plan(b.name, idx=b.idx, sent=b.sent, pre=b.pre, pad=b.pad,
                  extmode_or=0x00)
    base = dict(marker=False, reconverge=True)
    out = {}

    # 0. the FROZEN C2, re-measured here so the amendment cites a probe of its own
    out["frozen_C2_if_push_01"] = probe(carrier, plan, log,
                                        "frozen_C2_if_push_scope54_kind01",
                                        nested=True, **base)
    # 1. the SAME flat program at 8 lanes -- the mask is per-lane, so a multi-lane
    #    dispatch exercises the mask machinery the call's push acts on.
    out["flat_grid8"] = probe(carrier, plan, log, "flat_grid8", grid=8, tg=8, **base)
    # 2. alternate reconvergence BANK / SCOPE KIND for the pop that closes the call
    for (sc, sk, name) in ((0x24, 0x02, "pop_bankB_kind02"),
                           (0x04, 0x01, "pop_bankA_kind01"),
                           (0x24, 0x01, "pop_bankB_kind01"),
                           (0x54, 0x02, "pop_scope54_kind02")):
        out[name] = probe(carrier, plan, log, name, marker=False, reconverge=False,
                          post_call_extra=H.pop_reconverge_bytes(sc, sk))
    # 3. an if_push with the LOOP-ITERATION scope kind (0x1a) -- the same value
    #    `call` itself carries at byte+3
    for (sc, sk, name) in ((0x54, 0x1a, "ifpush_scope54_kind1a"),
                           (0x56, 0x1a, "ifpush_scope56_kind1a"),
                           (0x56, 0x01, "ifpush_scope56_kind01")):
        out[name] = probe(carrier, plan, log, name, marker=False, reconverge=True,
                          pre_call_extra=H.if_push_bytes(sc, sk))
    # 4. TWO pops after the call
    out["double_pop"] = probe(carrier, plan, log, "double_pop", marker=False,
                              reconverge=True,
                              post_call_extra=H.pop_reconverge_bytes())
    # 5. a marker-bracketed call at 8 lanes (the full compiler-shaped bracket)
    out["marker_grid8"] = probe(carrier, plan, log, "marker_grid8", grid=8, tg=8,
                                marker=True, reconverge=True)

    summary = {k: {"outcome": v["outcome"], "grid": v["grid"],
                   "callee_ran": v["facts"].get("callee_ran"),
                   "returned": v["facts"].get("returned"),
                   "collateral": v["facts"].get("collateral")}
               for k, v in out.items()}
    (outdir / "01_amendment_probe.json").write_text(
        json.dumps(summary, indent=1, sort_keys=True))
    log.close()
    carrier.close()
    print(json.dumps(summary, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
