#!/usr/bin/env python3
"""EXP-0174 arm I/grid -- the COMPLETE byte+2 x byte+3 cross-product.

256 x 256 = 65536 generated `n3` encodings at one (dst, src) pair, so that "we
only looked at a few forms" is not an available objection to the operand model.
Written to `raw/<run>/grid.jsonl` in a DELTA-ENCODED record -- the host-known
reference dump is in `00_env.json` and each record stores only the slots that
differ -- because the full 16-word dump for 65536 cases twice would be ~20 MB of
raw for no extra information.

  python3 harness/grid.py --run <id> [--plan idx15] [--order forward|reverse]
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
import isa_helpers as H      # noqa: E402
import sweeprun as S         # noqa: E402
import cases as CM           # noqa: E402

CARRIER = EXP / "kernels" / "carrier_n3.metal"
DST, SRCB1 = 9, 0x0A         # wide destination r9, source r5 low half


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--plan", default="idx15")
    ap.add_argument("--order", default="forward", choices=("forward", "reverse"))
    args = ap.parse_args()

    outdir = EXP / "raw" / args.run
    outdir.mkdir(parents=True, exist_ok=True)
    work = EXP / "work" / ("grid_%s" % args.run)
    H.assert_geometry()
    plan = H.PLANS[args.plan]
    carrier = S.SynthCarrier(CARRIER, "k", work, timeout=8.0)
    ref = CM.dump_of(plan, CM.block_state(plan))
    (outdir / "04_grid_meta.json").write_text(json.dumps({
        "plan": plan.as_dict(), "dst": DST, "src_b1": SRCB1, "ref_dump": ref,
        "order": args.order, "device": carrier.device,
        "region_len": carrier.region_len, "t": time.time(),
        "record": "delta-encoded: d = [[slot, value], ...] vs ref_dump"}, indent=1))
    log = S.Log(outdir / "grid.jsonl")
    combos = [(b2, b3) for b2 in range(256) for b3 in range(256)]
    if args.order == "reverse":
        combos.reverse()
    t0 = time.time()
    nbad = 0
    for i, (b2, b3) in enumerate(combos):
        blk = H.n3_bytes(DST, SRCB1, 0, b2, b3)
        prog = H.synth_program(plan, blk, carrier.region_len, wide=CM.WIDE)
        resp, words = carrier.run_program(prog)
        d = S.digest(words)
        val = S.validity_of(resp["status"], resp.get("error"), d)
        if val != "valid" or resp["status"] != "OK":
            nbad += 1
        delta = ([[j, d["regs"][j]] for j in range(H.N_REGS)
                  if d["regs"][j] != ref[j]] if d else None)
        log.write({"v": [b2, b3], "d": delta, "s": resp["status"], "y": val,
                   "g": resp.get("gputime_ns"),
                   "e": (S.os_class(resp.get("error")) if resp.get("error") else None)})
        if (i + 1) % 8192 == 0:
            print("  %d/%d  %.1fs  bad=%d" % (i + 1, len(combos),
                                              time.time() - t0, nbad))
    log.close()
    carrier.close()
    print("GRID DONE", args.run, len(combos), "cases", round(time.time() - t0, 1),
          "s  bad =", nbad)


if __name__ == "__main__":
    main()
