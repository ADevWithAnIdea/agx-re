#!/usr/bin/env python3
"""EXP-0174 PRE-FREEZE CALIBRATION.  raw/prefreeze/** is NEVER evidence.

Purpose: establish that the observable works before anything is frozen, and
measure the two suspected predecessor defects rather than assuming them.

  C1  dump fidelity        -- does every one of the 16 slots read back its own
                              host-known seed, for each register plan and each
                              of the two `extmode` encodings db.json allows?
                              This is where EXP-0168's r0 = 0 and r15 = 0 are
                              either reproduced or explained.
  C2  liveness / falsifier -- the HW-VALIDATED zero-extend member
                              (`X3 00 00 01`, EXP-0013/0161) must narrow r[N]
                              in place, and byte0's low nibble != 3 must not.
  C3  coarse form scan     -- a first look at (subform x companion) for a
                              GPR-to-GPR copy, at ONE (dst, src) pair.

  python3 harness/calib.py --run <id> [--stage C1,C2,C3]
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
import isa_helpers as H      # noqa: E402
import sweeprun as S         # noqa: E402

CARRIER = EXP / "kernels" / "carrier_n3.metal"
WIDE = (9, 2.5)              # r9 := IEEE-754 bits of 2.5f = 0x40200000


def env_block(carrier):
    return {
        "host": platform.node(),
        "platform": platform.platform(),
        "device": carrier.device,
        "region_off": carrier.region_off,
        "region_len": carrier.region_len,
        "main_len": len(carrier.main_bytes),
        "isa_dir": str(H.ISA_DIR),
        "t": time.time(),
    }


def dump_case(carrier, plan, extmode_or, log, tag, block=b"", wide=WIDE,
              dst=None, src=None, n_pads=None):
    plan.extmode_or = extmode_or
    prog = H.synth_program(plan, block, carrier.region_len, wide=wide,
                           n_pads=n_pads)
    resp, words = carrier.run_program(prog)
    d = S.digest(words)
    ref = H.seed_state(plan, wide)
    val = S.validity_of(resp["status"], resp.get("error"), d)
    rec = {
        "stage": tag, "plan": plan.name, "extmode_or": extmode_or,
        "block": block.hex(), "status": resp["status"],
        "validity": val, "os_class": S.os_class(resp.get("error")),
        "error": (resp.get("error") or "")[:300],
        "regs": (d["regs"] if d else None),
        "ref": ref,
        "pre": (d["pre"] if d else None), "post": (d["post"] if d else None),
        "tail_ok": (d["tail_ok"] if d else None),
        "blind": sorted(plan.blind), "pad_masked": sorted(plan.masked),
        "moved_slots": S.moved_slots(d, ref, plan.blind),
        "rt_ok": (H.round_trips(block) if block else None),
    }
    if dst is not None and src is not None:
        oc, kind = S.classify_move(resp["status"], d, ref, dst, src, plan.blind)
        rec["dst"] = dst
        rec["src"] = src
        rec["outcome"] = oc
        rec["move_kind"] = kind
    log.write(rec)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--stage", default="C1,C2,C3")
    ap.add_argument("--timeout", type=float, default=8.0)
    args = ap.parse_args()
    stages = set(s.strip() for s in args.stage.split(","))

    outdir = EXP / "raw" / "prefreeze" / args.run
    outdir.mkdir(parents=True, exist_ok=True)
    work = EXP / "work" / ("calib_%s" % args.run)

    H.assert_geometry()
    carrier = S.SynthCarrier(CARRIER, "k", work, timeout=args.timeout)
    (outdir / "00_env.json").write_text(json.dumps(env_block(carrier), indent=1))
    print("carrier region", carrier.region_off, carrier.region_len)
    log = S.Log(outdir / "calib.jsonl")

    # ---------------------------------------------------------------- C1 ----
    if "C1" in stages:
        for pname in ("idx15", "idx7"):
            for ext in (0x00, 0xC0):
                for rep in range(3):
                    r = dump_case(carrier, H.PLANS[pname], ext, log,
                                  "C1/dumpfidelity")
                    print("C1 %-6s ext=%02x rep%d %-16s moved=%s" %
                          (pname, ext, rep, r["validity"], r["moved_slots"]))
        # the same, with NO wide seed, so r9's falu2i cannot be blamed
        for pname in ("idx15", "idx7"):
            for ext in (0x00, 0xC0):
                r = dump_case(carrier, H.PLANS[pname], ext, log,
                              "C1/dumpfidelity_nowide", wide=None)
                print("C1 nowide %-6s ext=%02x %-16s moved=%s" %
                      (pname, ext, r["validity"], r["moved_slots"]))

    # ---------------------------------------------------------------- C2 ----
    if "C2" in stages:
        # HW-VALIDATED control: `X3 00 00 01` narrows r[N] in place (EXP-0161).
        for n in (2, 5, 10):
            for pname in ("idx15", "idx7"):
                blk = H.n3_bytes(n, 0, 0, 0x00, 0x01)
                r = dump_case(carrier, H.PLANS[pname], 0xC0, log,
                              "C2/zext_r%d" % n, block=blk)
                print("C2 zext r%-2d %-6s moved=%s" % (n, pname, r["moved_slots"]))
        # FALSIFIER: byte0 low nibble 0 is not this group at all -> must be inert
        # or must fault. It is chosen AWAY from the swept fields (EXP-0168's
        # defect #2: a falsifier that clobbers the byte carrying dst is
        # confounded with dst).
        for pname in ("idx15", "idx7"):
            blk = bytes([0x20, 0x00, 0x00, 0x01])
            r = dump_case(carrier, H.PLANS[pname], 0xC0, log,
                          "C2/falsifier_lownib0", block=blk)
            print("C2 falsifier %-6s moved=%s status=%s" %
                  (pname, r["moved_slots"], r["status"]))

    # ---------------------------------------------------------------- C3 ----
    if "C3" in stages:
        DST, SRC = 2, 5          # seeds 34 and 65, both distinct and non-zero
        b3set = [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x10,
                 0x20, 0x40, 0x80, 0x9F, 0xC1, 0xFF]
        found = []
        for b3 in b3set:
            for b2 in range(256):
                blk = H.n3_bytes(DST, SRC, 0, b2, b3)
                r = dump_case(carrier, H.PLANS["idx15"], 0xC0, log,
                              "C3/scan", block=blk, dst=DST, src=SRC)
                if r.get("move_kind") in ("copy32", "narrow16"):
                    found.append((b2, b3, r["move_kind"], r["regs"]))
                    print("C3 *** b2=%02x b3=%02x %s regs=%s" %
                          (b2, b3, r["move_kind"], r["regs"]))
            print("C3 b3=%02x done, cumulative hits=%d" % (b3, len(found)))
        (outdir / "c3_hits.json").write_text(json.dumps(found, indent=1))
        print("C3 total hits", len(found))

    log.close()
    carrier.close()
    print("wrote", outdir)


if __name__ == "__main__":
    main()
