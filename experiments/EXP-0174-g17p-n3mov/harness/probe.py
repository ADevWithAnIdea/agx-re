#!/usr/bin/env python3
"""EXP-0174 generic block prober (PRE-FREEZE; raw/prefreeze/** is NEVER evidence).

Runs an arbitrary list of authored byte-blocks in the synthesized carrier and
dumps all 16 GPRs for each, in one or both register plans.

  python3 harness/probe.py --run <id> --tag <tag> --blocks <file.json>
      [--plans idx15,idx7] [--src N] [--dst N] [--nopads]

`blocks.json` is a list of {"hex": "...", "note": "...", "dst": n, "src": n}.
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

CARRIER = EXP / "kernels" / "carrier_n3.metal"
WIDE = (9, 2.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--tag", default="probe")
    ap.add_argument("--blocks", required=True)
    ap.add_argument("--plans", default="idx15,idx7")
    ap.add_argument("--npads", type=int, default=4)
    ap.add_argument("--nowide", action="store_true")
    ap.add_argument("--timeout", type=float, default=8.0)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    blocks = json.loads(Path(args.blocks).read_text())
    plans = [H.PLANS[p.strip()] for p in args.plans.split(",")]
    wide = None if args.nowide else WIDE

    outdir = EXP / "raw" / "prefreeze" / args.run
    outdir.mkdir(parents=True, exist_ok=True)
    work = EXP / "work" / ("probe_%s" % args.run)
    H.assert_geometry()
    carrier = S.SynthCarrier(CARRIER, "k", work, timeout=args.timeout)
    (outdir / ("00_env_%s.json" % args.tag)).write_text(json.dumps({
        "device": carrier.device, "region_off": carrier.region_off,
        "region_len": carrier.region_len, "isa_dir": str(H.ISA_DIR),
        "t": time.time(), "tag": args.tag, "npads": args.npads,
        "wide": wide}, indent=1))
    log = S.Log(outdir / ("%s.jsonl" % args.tag))

    for b in blocks:
        blk = bytes.fromhex(b["hex"])
        for plan in plans:
            plan.extmode_or = 0xC0
            prog = H.synth_program(plan, blk, carrier.region_len, wide=wide,
                                   n_pads=args.npads)
            resp, words = carrier.run_program(prog)
            d = S.digest(words)
            ref = H.seed_state(plan, wide)
            rec = {"tag": args.tag, "plan": plan.name, "block": blk.hex(),
                   "note": b.get("note", ""), "npads": args.npads,
                   "status": resp["status"],
                   "validity": S.validity_of(resp["status"], resp.get("error"), d),
                   "os_class": S.os_class(resp.get("error")),
                   "error": (resp.get("error") or "")[:300],
                   "regs": (d["regs"] if d else None), "ref": ref,
                   "pre": (d["pre"] if d else None),
                   "post": (d["post"] if d else None),
                   "tail_ok": (d["tail_ok"] if d else None),
                   "blind": sorted(plan.blind),
                   "pad_masked": sorted(plan.masked),
                   "moved_slots": S.moved_slots(d, ref, plan.blind),
                   "rt_ok": H.round_trips(blk)}
            if "dst" in b and "src" in b:
                oc, kind = S.classify_move(resp["status"], d, ref,
                                           b["dst"], b["src"], plan.blind)
                rec.update({"dst": b["dst"], "src": b["src"],
                            "outcome": oc, "move_kind": kind})
            log.write(rec)
            if not args.quiet:
                ms = rec["moved_slots"]
                vals = ["%d=%x" % (i, rec["regs"][i]) for i in ms] if ms else []
                print("%-10s %-6s %-10s %-5s moved=%s  %s" % (
                    blk.hex(), plan.name, rec["status"], rec["validity"],
                    ",".join(vals) if vals else "-", rec["note"]))
    log.close()
    carrier.close()


if __name__ == "__main__":
    main()
