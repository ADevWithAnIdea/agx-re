#!/usr/bin/env python3
"""EXP-0169 CALIBRATION PROBE (pilot stage, added 2026-08-30, amendment_07).

WHY THIS EXISTS. `harness/smoke.py` step S3 could not solve the `device_load`
`idx_off` unit, and the S2 baseline on carrier C2_load read the ramp correctly
into r3..r13 but returned 0 for r0, r1, r2. Both S2 and S3 seed with
`isa_helpers.load_reg(k, k)`, which sets `extmode = 2*k` (the destination) and
`idx_off = k` (the offset) FROM THE SAME k -- so the two candidate explanations
are perfectly confounded in the pilot data:

    (A) `idx_off` 0,1,2 read zero      (an OFFSET fact)
    (B) destinations r0,r1,r2 are not written (a DESTINATION fact)

This probe breaks the confound by varying ONE at a time. It adds NO new
instruction construction of its own: every program is built from the FROZEN
`isa_helpers` helpers, through the FROZEN `run.build_prog_static` /
`dispatch_static` / `observe_static` path, so whatever it measures is a property
of the same instrument the gated sweep will use.

  D1  fixed destination, varying offset:  load r5 from idx_off 0..7
  D2  fixed offset, varying destination:  load r0..r7 from idx_off 9
  D3  the S2/S3 diagonal, replayed:      load r_k from idx_off k, k=0..7
  D4  D1 with the loads issued in REVERSE offset order, to separate an
      offset/destination property from an ISSUE-ORDER or in-flight property.

Every record goes to raw/<run>/calibprobe.jsonl, append-only, fsynced per record.
This is a PILOT-ID run: EXP-0164's NONGATED filter excludes it from promotion by
construction, and it is a MEASUREMENT of our own harness, not a field verdict.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.
"""
from __future__ import print_function

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H      # noqa: E402
import sweeprun as S         # noqa: E402
import casematrix as CM      # noqa: E402
import run as R              # noqa: E402

RAMP0 = 0x40000000
RAMPSTEP = 0x00081111


def word_index_of(bits):
    """Which ramp word a read-back value identifies, or None."""
    v = bits - RAMP0
    if v <= 0 or v % RAMPSTEP:
        return None
    return (v // RAMPSTEP) - 1


def run_seq(car, loads, tag, log, note):
    """`loads` is a list of (dst_reg, idx_off). Build seeds -> loads -> dump."""
    instrs = [H.mov_imm(14, 0), H.mov_imm(H.R_IDX, 0)]
    for (dst, off) in loads:
        instrs.append(H.load_reg(dst, off))
    instrs += H.dump_instrs()
    instrs.append(H.stop())
    prog = H.build_program(instrs, car.region_len)
    resp, words = car.run_program(prog, out_words=H.OUT_WORDS)
    d = S.digest(words) if resp["status"] == "OK" else None
    got = {}
    if d:
        for (dst, off) in loads:
            got[dst] = {"off": off, "bits": d["regs"][dst],
                        "word_index": word_index_of(d["regs"][dst])}
    rec = {"field": "_calibprobe", "instr": "device_load", "arm": tag,
           "carrier": "C2_load", "value": 0, "bytes": "",
           "status": resp["status"], "error": resp["error"],
           "observed": d, "loads": [list(x) for x in loads],
           "resolved": {str(k): v for k, v in got.items()},
           "outcome": "ok" if d else "fault", "note": note}
    log.write(rec)
    print("%-4s %s" % (tag, " ".join(
        "r%d<-off%d=%s" % (dst, got[dst]["off"],
                           ("w%d" % got[dst]["word_index"])
                           if got[dst]["word_index"] is not None
                           else ("0x%08x" % got[dst]["bits"]))
        for dst, _ in [(k, 0) for k in sorted(got)])) if d
        else "%-4s %s %s" % (tag, resp["status"], resp["error"]))
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="pilot02")
    a = ap.parse_args()
    rundir = EXP / "raw" / a.run
    rundir.mkdir(parents=True, exist_ok=True)
    workdir = EXP / "work" / ("calibprobe_%s" % a.run)
    files = R.prepare_inputs(workdir)
    cache = {}
    car = R.carrier_for("C2_load", files, workdir, cache)
    log = S.Log(rundir / "calibprobe.jsonl")
    out = {}

    out["D1_fixed_dst_r5"] = {str(off): run_seq(
        car, [(5, off)], "D1", log,
        "fixed destination r5, single load at idx_off %d" % off)
        for off in range(8)}
    out["D2_fixed_off_9"] = run_seq(
        car, [(d, 9) for d in range(8)], "D2", log,
        "fixed idx_off 9, destinations r0..r7: separates a DESTINATION fact "
        "from an OFFSET fact")
    out["D3_diagonal"] = run_seq(
        car, [(k, k) for k in range(8)], "D3", log,
        "the S2/S3 diagonal replayed: dst k, idx_off k")
    out["D4_reverse_issue"] = run_seq(
        car, [(k, k) for k in range(7, -1, -1)], "D4", log,
        "the D3 diagonal with loads ISSUED IN REVERSE ORDER: separates an "
        "offset/destination property from an issue-order or in-flight property")
    out["D5_single_r0"] = run_seq(
        car, [(0, 5)], "D5", log,
        "ONE load, destination r0, offset 5: is r0 writable by device_load at all?")
    out["D6_single_off0"] = run_seq(
        car, [(7, 0)], "D6", log,
        "ONE load, destination r7, offset 0: is idx_off 0 readable at all?")

    log.close()
    for v in cache.values():
        v.close()
    (rundir / "calibprobe.json").write_text(json.dumps(out, indent=1,
                                                       sort_keys=True))
    print("\nwrote", rundir / "calibprobe.json")


if __name__ == "__main__":
    main()
