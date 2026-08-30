#!/usr/bin/env python3
"""EXP-0161 SMOKE / PILOT (not evidence -- writes to work/, never raw/).

Answers, on hardware, the questions the gated matrix depends on:

  S1  does the SYNTH carrier's `_agc.main` region fit the seeded program?
  S2  does the device_load seeding actually put SEED_U32 into r0..r14?
      (elem_code 3 vs 1 -- the only free parameter in the seeding path)
  S3  what does the lifted k_u64add block do to the 16 registers?
  S4  DOES THE FALSIFIER FIRE?  carry_gen byte0 := 0x00 must NOT reproduce the
      baseline.  This is the single question EXP-0154 answered "no" and the
      whole reason this experiment exists.
  S5  do the INPLACE carriers reproduce their host-computed oracle unmutated?
  S6  is mov_zext16 live in the synthesized carrier (and does ITS falsifier fire)?
  S7  is fspecial live in the synthesized carrier with float seeds?

CLEAN-ROOM: OWN-SHADER + HW-PROBE.
"""
from __future__ import print_function

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H   # noqa: E402
import sweeprun as S      # noqa: E402
import cases as CM        # noqa: E402
import run as R           # noqa: E402

OUT = {}
REP = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())


def synth_carrier(tag, elem_code=3):
    return S.Carrier(EXP / "kernels" / "carrier_seed.metal", "k",
                     EXP / "work" / ("smoke_%s" % tag), timeout=8.0,
                     fast_math=False,
                     inputs={0: ("poison_synth.bin", CM.poison(H.OUT_WORDS)),
                             1: ("seedbuf.bin", H.seed_buffer_bytes())},
                     outs={0: H.OUT_WORDS * 4})


def dump(car, kind, blk, elem_code=3):
    prog = H.synth_program(kind, blk, car.region_len, elem_code=elem_code)
    resp, outs = car.run_program(prog, grid=1, tg=1)
    words = S.words_u32(outs.get(0, b""))
    d = S.digest(words)
    return resp, d


def main():
    car = synth_carrier("synth")
    OUT["S1"] = {"region_len": car.region_len, "device": car.device,
                 "program_len_empty": len(H.synth_program("int", b"", car.region_len))}
    print("S1 region_len=%d device=%s" % (car.region_len, car.device))

    # ---- S2: seeding -----------------------------------------------------
    for ec in (3,):
        resp, d = dump(car, "int", b"", elem_code=ec)
        ok = d is not None and d["regs"][:15] == [v & 0xFFFFFFFF
                                                  for v in H.SEED_U32[:15]]
        OUT["S2_elem%d" % ec] = {
            "status": resp["status"], "error": resp["error"],
            "regs": ["0x%08x" % v for v in d["regs"]] if d else None,
            "pre": d["pre"] if d else None, "post": d["post"] if d else None,
            "seed_match": bool(ok)}
        print("S2 elem_code=%d status=%s seed_match=%s" % (ec, resp["status"], ok))
        if d:
            print("   regs:", " ".join("%08x" % v for v in d["regs"]))
        if ok:
            OUT["S2_chosen_elem_code"] = ec
            break

    ec = OUT.get("S2_chosen_elem_code", 3)
    # S2b: stability of the seeding fix over 8 consecutive dispatches
    reps = []
    for _ in range(8):
        resp, d = dump(car, "int", b"", elem_code=ec)
        reps.append(bool(d and d["regs"][:15] == [v & 0xFFFFFFFF
                                                  for v in H.SEED_U32[:15]]))
    OUT["S2b_repeat_ok"] = reps
    print("S2b seeding stable over 8 repeats:", reps)

    # ---- S3/S4: carry_gen ------------------------------------------------
    main_u64 = bytes.fromhex(REP["k_u64add"]["main_hex"])
    blk = main_u64[32:72]
    resp, base = dump(car, "int", blk, elem_code=ec)
    OUT["S3_carry_baseline"] = {
        "status": resp["status"],
        "regs": ["0x%08x" % v for v in base["regs"]] if base else None,
        "block": blk.hex()}
    print("S3 carry baseline status=%s" % resp["status"])
    if base:
        seeds = H.seeds_for("int")
        chg = [(i, "0x%08x" % seeds[i], "0x%08x" % base["regs"][i])
               for i in range(16) if base["regs"][i] != seeds[i]]
        OUT["S3_changed"] = chg
        print("   changed regs (seed -> after):", chg)

    for name, bi in (("byte0", 0), ("b2", 2)):
        mb = CM.set_byte(blk, 10, bi, 0x00)
        resp, d = dump(car, "int", mb, elem_code=ec)
        fired = (d is None) or (base is None) or (d["regs"] != base["regs"])
        OUT["S4_falsifier_%s" % name] = {
            "status": resp["status"], "error": resp["error"],
            "regs": ["0x%08x" % v for v in d["regs"]] if d else None,
            "FIRED": bool(fired)}
        print("S4 falsifier carry_gen %s:=0x00 -> status=%s FIRED=%s"
              % (name, resp["status"], fired))

    # ---- S6: mov_zext16 --------------------------------------------------
    mz = bytes.fromhex(REP["k_zext16"]["main_hex"])[18:22]
    resp, zb = dump(car, "int", mz, elem_code=ec)
    OUT["S6_zext_baseline"] = {
        "status": resp["status"], "block": mz.hex(),
        "regs": ["0x%08x" % v for v in zb["regs"]] if zb else None}
    if zb:
        seeds = H.seeds_for("int")
        OUT["S6_changed"] = [(i, "0x%08x" % seeds[i], "0x%08x" % zb["regs"][i])
                             for i in range(16) if zb["regs"][i] != seeds[i]]
        print("S6 zext16 changed:", OUT["S6_changed"])
    mzf = CM.set_byte(mz, 0, 0, 0x00)
    resp, d = dump(car, "int", mzf, elem_code=ec)
    fired = (d is None) or (zb is None) or (d["regs"] != zb["regs"])
    OUT["S6_falsifier"] = {"status": resp["status"], "FIRED": bool(fired),
                           "regs": ["0x%08x" % v for v in d["regs"]] if d else None}
    print("S6 falsifier mov_zext16 byte0:=0x00 -> FIRED=%s" % fired)

    # ---- S7: fspecial (float seeds) --------------------------------------
    fs = bytes.fromhex(REP["k_rsqrt"]["main_hex"])[18:28]
    resp, fb = dump(car, "float", fs, elem_code=ec)
    OUT["S7_fspecial_baseline"] = {
        "status": resp["status"], "block": fs.hex(),
        "regs": ["0x%08x" % v for v in fb["regs"]] if fb else None}
    if fb:
        seeds = H.seeds_for("float")
        import struct as _s
        chg = [(i, "0x%08x" % seeds[i], "0x%08x" % fb["regs"][i],
                _s.unpack("<f", _s.pack("<I", fb["regs"][i]))[0])
               for i in range(16) if fb["regs"][i] != seeds[i]]
        OUT["S7_changed"] = chg
        print("S7 fspecial changed:", chg)
    fsf = CM.set_byte(fs, 0, 0, 0x00)
    resp, d = dump(car, "float", fsf, elem_code=ec)
    fired = (d is None) or (fb is None) or (d["regs"] != fb["regs"])
    OUT["S7_falsifier"] = {"status": resp["status"], "FIRED": bool(fired)}
    print("S7 falsifier fspecial byte0:=0x00 -> FIRED=%s" % fired)

    # ---- S5: INPLACE baselines -------------------------------------------
    car.close()
    for cname, cfg in sorted(CM.CARRIERS.items()):
        try:
            c2 = S.Carrier(EXP / "kernels" / "probes.metal", cfg["func"],
                           EXP / "work" / ("smoke_ip_%s" % cname), timeout=8.0,
                           fast_math=cfg["fast_math"], inputs=cfg["inputs"],
                           outs=cfg["outs"])
            resp, outs = c2.run_inplace(0, c2.main_bytes,
                                        grid=cfg["grid"], tg=cfg["tg"])
            got = R.decode_out(cfg, outs)
            ok = R.close_enough(got, cfg["oracle"], cfg["tol"])
            OUT["S5_%s" % cname] = {
                "status": resp["status"], "error": resp["error"],
                "region_len": c2.region_len, "main_len": len(c2.main_bytes),
                "got": ["%.9g" % g if isinstance(g, float) else "0x%x" % g
                        for g in (got or [])],
                "oracle": ["%.9g" % g if isinstance(g, float) else "0x%x" % g
                           for g in cfg["oracle"]],
                "ORACLE_MATCH": bool(ok)}
            print("S5 %-14s status=%s oracle_match=%s" % (cname, resp["status"], ok))
            if not ok:
                print("     got   ", OUT["S5_%s" % cname]["got"])
                print("     oracle", OUT["S5_%s" % cname]["oracle"])
            c2.close()
        except Exception as e:
            OUT["S5_%s" % cname] = {"error": str(e)[:500]}
            print("S5 %-14s EXC %s" % (cname, str(e)[:160]))

    p = EXP / "work" / "smoke.json"
    p.write_text(json.dumps(OUT, indent=1, sort_keys=True))
    print("\nwrote", p)


if __name__ == "__main__":
    main()
