#!/usr/bin/env python3
"""EXP-0157 REACHABILITY probe (post-freeze control, recorded as a deviation).

Arm R found `rtq_pred` inert at 8 of 8 anchors and `rtq_dualsrc` inert at 11 of
11 -- ERASING all 4 (resp. 12) bytes of the instruction leaves the ray-query
result exactly correct. Two explanations survive that observation:

  (a) the instruction genuinely does not affect the traversal result, or
  (b) the code at that offset is never executed with our geometry.

They are distinguished by ERASING A WIDER WINDOW around the same offset. If a
256-byte hole through the region still leaves the oracle intact, the region is
UNREACHED and nothing there can be concluded about any field. If a 16-byte hole
already breaks the program, the region IS executed and the instruction really is
inert.

This is the control that keeps `inert_or_unreached` from being silently read as
`inert`.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EXP / "analysis"))
import carriers as C   # noqa: E402
import run as R        # noqa: E402

WINDOWS = [4, 16, 64, 256]

# Filler used to REPLACE an instruction rather than zero it. `00` bytes are not
# known to be a no-op on this hardware (db.json's own `pad_operand` entry says
# "NEGATIVE RESULT -- 0x00 is not an opcode"), so an output change after a
# zero-erase is not by itself evidence that the ERASED INSTRUCTION mattered.
# `mov_imm(r13, 0)` is a known 2-byte instruction whose only effect is on a
# register nothing else here reads, and arm L's CTRL_INERT verified on hardware
# that eight bytes of it leave every witness intact. This is the filler a fence
# litmus needs.
INERT2 = None   # resolved in main() from isa_helpers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--bin-dir", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--carrier", required=True)
    ap.add_argument("--filler", default="zero", choices=("zero", "inert"),
                    help="what to replace the window with: 0x00 bytes, or "
                         "repeated mov_imm(r13,0) (a HW-verified 2-byte no-op)")
    ap.add_argument("--windows", default="4,16,64,256")
    ap.add_argument("--anchors", required=True,
                    help="json: [[instr, offset], ...] from a prior run's _ANCHOR_VERDICT")
    a = ap.parse_args()
    work = Path(a.work); work.mkdir(parents=True, exist_ok=True)
    raw = Path(a.raw); raw.mkdir(parents=True, exist_ok=True)
    (raw / "00_env.json").write_text(json.dumps(R.env_report(), indent=1, sort_keys=True) + "\n")

    mains, build = R.prepare(a.bin_dir, work, [a.carrier])
    (raw / "00_build.json").write_text(json.dumps(build, indent=1, sort_keys=True) + "\n")
    mainlen = len(mains[a.carrier][2])
    sess = R.CarrierSession(a.carrier, a.bin_dir, work, mains)
    sess.start()
    fres = open(raw / "sweep.jsonl", "a")
    try:
        base = {"field": "_baseline", "splice": [], "value": 0}
        oc, obs, m, st, sts, cls, inn = sess.measure(base, sess.blob_of(base))
        R.emit(fres, {"arm": "P", "carrier": a.carrier, "instr": "-",
                      "anchor_idx": -1, "anchor": 0, "field": "_baseline",
                      "value": 0, "observed": obs, "match": bool(m),
                      "outcome": oc, "status": st, "expect_match": True,
                      "note": "unmutated baseline before the reachability probe"})
        import isa_helpers as H
        inert = H.mov_imm(13, 0)
        wins = [int(x) for x in a.windows.split(",")]
        for instr, off in json.load(open(a.anchors)):
            for w in wins:
                start = max(0, off)
                n = min(w, mainlen - start)
                if a.filler == "inert":
                    fill = (inert * ((n // 2) + 1))[:n]
                else:
                    fill = b"\x00" * n
                case = {"field": "_%s%d" % (a.filler.upper(), w), "value": w,
                        "splice": [(start, fill.hex())]}
                oc, obs, m, st, sts, cls, inn = sess.measure(case, sess.blob_of(case))
                R.emit(fres, {"arm": "P", "carrier": a.carrier, "instr": instr,
                              "anchor_idx": 0, "anchor": off,
                              "field": case["field"], "value": w,
                              "bytes": "", "observed": obs, "match": bool(m),
                              "outcome": oc, "status": st,
                              "statuses": sts if len(sts) > 1 else None,
                              "fault_classes": cls or None,
                              "expect_match": False,
                              "note": "%s-fill %d bytes from offset %d: if the oracle "
                                      "SURVIVES, the region is unreached / the "
                                      "instruction is inert" % (a.filler, n, start)})
                print("  %-16s off=%-6d erase %3d -> %s" % (instr, off, n, oc), flush=True)
    finally:
        sess.stop(); fres.close()
    print("done", flush=True)


if __name__ == "__main__":
    main()
