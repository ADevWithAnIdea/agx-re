#!/usr/bin/env python3
"""EXP-0169 pilot: prove the harness can SEE things before it claims anything.

  python3 harness/smoke.py --run pilot01

Steps, in order, each recorded to raw/<run>/ (a `pilot` run id, which
EXP-0164's audit `NONGATED` filter excludes from any promotion by construction):

  S1 carrier compiles; `_agc.main` region located; region length recorded.
  S2 baseline synthesized program runs on every carrier: r0..r15 read back as
     the seeds we chose, PRE and POST sentinels intact, every other word still
     0xDEADBEEF. Without this a `silent_zero` cannot be told from "never ran".
  S3 CALIBRATION: the device_load `idx_off` unit, in words. Loads r0..r7 with
     idx_off 0..7 from a ramp image in which every word is self-identifying,
     and solves for the unit. Frozen into work/calib.json BEFORE the gated
     runs; the C2_load semantic oracle depends on it.
  S4 LIVENESS LADDER, per (arm, carrier): the pre-registered falsifier must NOT
     score `ok`, and every ladder step MUST move the observation. A carrier
     that fails a step has no demonstrated detection power in that dimension,
     and its inert readings for that dimension are reported `untested` -- never
     as "the field is inert". This is the `iter_at.loc` failure mode: all of
     that experiment's carriers were samples=1, where centroid and sample are
     the same point, so an inert reading was guaranteed regardless of the
     hardware.
  S5 device_store probe shape: the probe store lands where we predicted.

CLEAN-ROOM: OWN-SHADER + HW-PROBE.
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
import casematrix as CM      # noqa: E402
import run as R              # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="pilot01")
    a = ap.parse_args()
    rundir = EXP / "raw" / a.run
    rundir.mkdir(parents=True, exist_ok=True)
    workdir = EXP / "work" / ("smoke_%s" % a.run)
    files = R.prepare_inputs(workdir)
    rep = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
    cases, resolved, misses = CM.build_cases(rep)
    log = S.Log(rundir / "smoke.jsonl")
    cache = {}
    out = {"misses": misses, "steps": {}}

    # ---- S1/S2: carriers + baseline -------------------------------------
    s2 = {}
    for cid in ("C1_alu", "C2_load", "C3_uni", "C4_store"):
        car = R.carrier_for(cid, files, workdir, cache)
        kind = CM.CARRIERS[cid][2]
        kind = "load" if kind == "load" else "int"
        outw = CM.CARRIERS[cid][3]
        prog = H.synth_program(kind, b"", car.region_len)
        resp, words = car.run_program(prog, out_words=outw)
        d = S.digest(words) if resp["status"] == "OK" else None
        seeds = H.seed_values(kind, 1)
        rec = {"field": "_smoke_baseline", "instr": "-", "arm": "S2",
               "carrier": cid, "value": 0, "bytes": "",
               "status": resp["status"], "error": resp["error"],
               "observed": d, "outcome": "ok" if d else "fault",
               "region_len": car.region_len, "device": car.device,
               "seeds_expected": {str(k): v for k, v in seeds.items()},
               "n_poison": sum(1 for w in words if w == H.POISON),
               "note": "S1/S2 carrier + baseline + poison integrity"}
        log.write(rec)
        s2[cid] = {"status": resp["status"], "region_len": car.region_len,
                   "regs": d["regs"] if d else None,
                   "pre_ok": bool(d and d["pre"] == H.expected_pre()),
                   "post_ok": bool(d and d["post"] == H.SENT_POST),
                   "n_poison": rec["n_poison"]}
        print("S2 %-9s %s region=%d pre=%s post=%s"
              % (cid, resp["status"], car.region_len,
                 s2[cid]["pre_ok"], s2[cid]["post_ok"]))
    out["steps"]["S2"] = s2

    # ---- S3: calibrate the device_load idx_off unit ----------------------
    car = R.carrier_for("C2_load", files, workdir, cache)
    instrs = [H.mov_imm(14, 0), H.mov_imm(H.R_IDX, 0)]
    for r in range(8):
        instrs.append(H.load_reg(r, r))
    instrs += H.dump_instrs()
    instrs.append(H.stop())
    prog = H.build_program(instrs, car.region_len)
    resp, words = car.run_program(prog, out_words=H.OUT_WORDS)
    d = S.digest(words) if resp["status"] == "OK" else None
    unit, model = None, None
    if d:
        # word i of the ramp has bits 0x40000000 + (i+1)*0x00081111
        def word_index_of(bits):
            v = (bits - 0x40000000)
            return (v // 0x00081111) - 1 if v > 0 and v % 0x00081111 == 0 else None
        got = [word_index_of(d["regs"][r]) for r in range(8)]
        if got[0] is not None and got[1] is not None:
            unit = got[1] - got[0]
            model = got
    calib = {"idx_off_word_indices": model, "idx_unit_words": unit,
             "status": resp["status"],
             "note": ("device_load idx_off unit in WORDS, solved from a ramp "
                      "image in which every word is self-identifying. Frozen "
                      "here BEFORE the gated runs; the C2_load semantic oracle "
                      "depends on it.")}
    log.write({"field": "_smoke_calib", "instr": "device_load", "arm": "S3",
               "carrier": "C2_load", "value": 0, "bytes": "",
               "status": resp["status"], "observed": d, "calib": calib,
               "outcome": "ok" if unit else "wrong_value"})
    (EXP / "work" / "calib.json").write_text(json.dumps(calib, indent=1,
                                                        sort_keys=True))
    out["steps"]["S3"] = calib
    print("S3 idx_off unit =", unit, "indices", model)

    # ---- S4: falsifier + liveness ladder, per (arm, carrier) ------------
    ladder = {}
    idx_unit = unit or 1
    by_arm = {}
    for c in cases:
        if not c["field"].startswith("__"):
            continue
        by_arm.setdefault((c["carrier"], c["arm"]), []).append(c)
    for (cid, arm), cs in sorted(by_arm.items()):
        car = R.carrier_for(cid, files, workdir, cache)
        c0 = cs[0]
        base = None
        blk0 = bytes.fromhex(c0["anchor"])
        if c0["mode"] in ("lift", "nat"):
            main = bytes.fromhex(rep[c0["probe"]]["main_hex"])
            blk0 = main[c0["block_lo"]:c0["block_hi"]]
        prog, native = R.build_prog_static(c0, blk0, car, rep)
        resp, words = R.dispatch_static(c0, prog, native, car)
        base = R.observe_static(c0, resp, words)
        res = {"baseline_status": resp["status"], "steps": {}}
        for c in cs:
            blk = bytes.fromhex(c["bytes"])
            prog, native = R.build_prog_static(c, blk, car, rep)
            resp, words = R.dispatch_static(c, prog, native, car)
            obs = R.observe_static(c, resp, words)
            oc = S.classify(resp["status"], obs, base) if base else "undecodable"
            moved = bool(base and obs and obs != base)
            res["steps"][c["field"]] = {
                "outcome": oc, "moved": moved, "predict": c.get("predict"),
                "pass": ((oc != "ok") if c.get("predict") == "not_ok"
                         else (moved if c.get("predict") == "move" else None)),
                "note": c.get("note", "")}
            log.write({"field": c["field"], "instr": c["instr"], "arm": arm,
                       "carrier": cid, "value": c["value"], "bytes": c["bytes"],
                       "status": resp["status"], "error": resp["error"],
                       "observed": obs, "outcome": oc, "moved": moved,
                       "predict": c.get("predict"), "note": c.get("note", "")})
        ok = all(v["pass"] for v in res["steps"].values()
                 if v["pass"] is not None)
        res["ladder_pass"] = ok
        ladder["%s@%s" % (arm, cid)] = res
        print("S4 %-22s ladder %s  %s" % ("%s@%s" % (arm, cid),
                                          "PASS" if ok else "FAIL",
                                          {k: v["moved"] for k, v in
                                           res["steps"].items()}))
    out["steps"]["S4"] = ladder

    # ---- S5: the device_store probe shape --------------------------------
    car = R.carrier_for("C4_store", files, workdir, cache)
    st = H.device_store(**CM.DSTORE_BASE)
    prog = H.store_probe_program("int", st, car.region_len)
    resp, words = car.run_program(prog, out_words=H.OUT_WORDS_BIG)
    d = S.digest(words) if resp["status"] == "OK" else None
    out["steps"]["S5"] = {"status": resp["status"],
                          "stray": d["stray"] if d else None,
                          "expected_word": H.W_PROBE}
    log.write({"field": "_smoke_store_shape", "instr": "device_store",
               "arm": "S5", "carrier": "C4_store", "value": 0,
               "bytes": st.hex(), "status": resp["status"], "observed": d,
               "outcome": "ok" if d else "fault",
               "note": "probe store predicted to land at output word %d" % H.W_PROBE})
    print("S5 store stray:", out["steps"]["S5"]["stray"])

    log.close()
    for v in cache.values():
        v.close()
    (rundir / "smoke.json").write_text(json.dumps(out, indent=1, sort_keys=True))
    (EXP / "work" / "smoke.json").write_text(json.dumps(out, indent=1,
                                                        sort_keys=True))
    print("\nwrote", rundir / "smoke.json")


if __name__ == "__main__":
    main()
