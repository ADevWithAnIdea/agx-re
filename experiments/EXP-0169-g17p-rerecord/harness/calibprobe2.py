#!/usr/bin/env python3
"""EXP-0169 CALIBRATION PROBE 2 -- the LOAD-LATENCY test (pilot stage, amendment_07).

pilot02 broke the dst/offset confound and refuted BOTH candidate explanations:
r5 from idx_off 5, alone, read 0 -- yet the SAME construction read the ramp
correctly into r3..r13 in smoke S2. So the variable is neither the destination
nor the offset. The remaining hypothesis:

    H_LAT: `device_load` is ASYNCHRONOUS and this harness issues NO wait /
           scoreboard barrier anywhere (there is no such helper in the frozen
           isa_helpers at all). A register is read back correctly only if
           enough instructions executed between its load being ISSUED and the
           dump's store of that register. In smoke S2 the 14 loads plus the
           PRE-sentinel block gave the later registers that slack and the first
           three none -- which is exactly the observed "r0,r1,r2 read 0,
           r3..r13 correct" pattern.

PREDICTION, and its REFUTER. Under H_LAT the number of landed registers must
grow monotonically with the number of filler instructions inserted between the
loads and the dump, and with enough filler ALL loads must land. If the landed
set is instead FIXED regardless of filler, H_LAT is refuted and the zeros are a
property of the load itself.

  E1  8 loads, then F filler instructions, then the dump, for F in
      0,2,4,8,16,32,64,128 -- count landed registers as a function of F.
  E2  the smoke S2 sequence EXACTLY (14 loads + PRE sentinel), repeated 5x, to
      establish whether the r0,r1,r2 = 0 pattern is DETERMINISTIC or flaky.

Filler is `mov_imm(R_PRE, SEED_I[R_PRE])` -- 2 bytes, writes only the scratch
register the PRE-sentinel path already writes, touches no seeded register and no
memory. It is built from the FROZEN helpers.

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
import run as R              # noqa: E402

RAMP0 = 0x40000000
RAMPSTEP = 0x00081111


def word_index_of(bits):
    v = bits - RAMP0
    if v <= 0 or v % RAMPSTEP:
        return None
    return (v // RAMPSTEP) - 1


def landed(d, loads):
    """Which (dst,off) pairs read back the ramp word their offset names."""
    ok, bad = [], []
    for (dst, off) in loads:
        wi = word_index_of(d["regs"][dst])
        (ok if wi == off else bad).append([dst, off, wi, d["regs"][dst]])
    return ok, bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="pilot03")
    a = ap.parse_args()
    rundir = EXP / "raw" / a.run
    rundir.mkdir(parents=True, exist_ok=True)
    workdir = EXP / "work" / ("calibprobe2_%s" % a.run)
    files = R.prepare_inputs(workdir)
    cache = {}
    car = R.carrier_for("C2_load", files, workdir, cache)
    log = S.Log(rundir / "calibprobe2.jsonl")
    out = {"E1_filler_ladder": {}, "E2_s2_repeat": []}
    filler1 = H.mov_imm(H.R_PRE, H.SEED_I[H.R_PRE])

    # ---- E1: landed count as a function of filler --------------------------
    loads = [(k, k) for k in range(8)]
    for F in (0, 2, 4, 8, 16, 32, 64, 128):
        instrs = [H.mov_imm(14, 0), H.mov_imm(H.R_IDX, 0)]
        for (dst, off) in loads:
            instrs.append(H.load_reg(dst, off))
        instrs += [filler1] * F
        instrs += H.dump_instrs()
        instrs.append(H.stop())
        try:
            prog = H.build_program(instrs, car.region_len)
        except ValueError as e:
            out["E1_filler_ladder"][str(F)] = {"error": str(e)}
            print("E1 F=%-4d SKIPPED (%s)" % (F, e))
            continue
        resp, words = car.run_program(prog, out_words=H.OUT_WORDS)
        d = S.digest(words) if resp["status"] == "OK" else None
        ok, bad = landed(d, loads) if d else ([], [])
        out["E1_filler_ladder"][str(F)] = {
            "status": resp["status"], "n_landed": len(ok),
            "landed": ok, "not_landed": bad,
            "post_ok": bool(d and d["post"] == H.SENT_POST)}
        log.write({"field": "_latency_E1", "instr": "device_load", "arm": "E1",
                   "carrier": "C2_load", "value": F, "bytes": "",
                   "status": resp["status"], "error": resp["error"],
                   "observed": d, "n_landed": len(ok), "landed": ok,
                   "not_landed": bad, "outcome": "ok" if d else "fault",
                   "note": ("%d filler instructions between the 8 loads and "
                            "the dump" % F)})
        print("E1 F=%-4d landed %d/8  %s" % (
            F, len(ok), [x[0] for x in ok]))

    # ---- E2: is the smoke S2 pattern deterministic? -----------------------
    for rep in range(5):
        prog = H.synth_program("load", b"", car.region_len)
        resp, words = car.run_program(prog, out_words=H.OUT_WORDS)
        d = S.digest(words) if resp["status"] == "OK" else None
        l2 = [(k, k) for k in range(H.N_LOAD_SEEDED)]
        ok, bad = landed(d, l2) if d else ([], [])
        out["E2_s2_repeat"].append({"status": resp["status"],
                                    "n_landed": len(ok),
                                    "landed_regs": [x[0] for x in ok],
                                    "not_landed": bad})
        log.write({"field": "_latency_E2", "instr": "device_load", "arm": "E2",
                   "carrier": "C2_load", "value": rep, "bytes": "",
                   "status": resp["status"], "error": resp["error"],
                   "observed": d, "n_landed": len(ok),
                   "landed_regs": [x[0] for x in ok], "not_landed": bad,
                   "outcome": "ok" if d else "fault",
                   "note": "smoke S2 sequence verbatim, repeat %d of 5" % rep})
        print("E2 rep%d landed %d/14 regs=%s" % (rep, len(ok),
                                                 [x[0] for x in ok]))

    log.close()
    for v in cache.values():
        v.close()
    (rundir / "calibprobe2.json").write_text(json.dumps(out, indent=1,
                                                        sort_keys=True))
    print("\nwrote", rundir / "calibprobe2.json")


if __name__ == "__main__":
    main()
