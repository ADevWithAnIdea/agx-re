#!/usr/bin/env python3
"""EXP-0161 GENERATION PROOF (the strongest evidence level in CODEX section 3:
"independently generated encoding executed successfully on hardware").

The sweeps establish what each field means. This script turns that around: it
GENERATES `fspecial`, `carry_gen` and `mov_zext16` encodings the compiler never
emitted -- arbitrary source/destination registers, arbitrary compare operands --
from the recovered model alone, predicts the FULL 16-register architectural
state HOST-SIDE before dispatching, and checks it.

A pass here is what separates "we decoded the field" from "an emitter can
choose the value". Every prediction is computed from the authored seed vector
and the recovered rule; none is read back from the GPU first.

  python3 harness/gen.py --run g17p_YYYYMMDD_gen01

CLEAN-ROOM: OWN-SHADER + HW-PROBE.
"""
from __future__ import print_function

import argparse
import json
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import isa_helpers as H   # noqa: E402
import sweeprun as S      # noqa: E402
import cases as CM        # noqa: E402

REP = json.loads((EXP / "work" / "anchors" / "anchor_report.json").read_text())
M32 = 0xFFFFFFFF


def fbits(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def f32(u):
    return struct.unpack("<f", struct.pack("<I", u & M32))[0]


def set_f(blk, tgt, instr, name, v):
    f = [x for x in CM.INS[instr]["fields"] if x["name"] == name][0]
    return CM.set_field(blk, tgt, f["start"], f["width"], v)


# ---------------------------------------------------------------------------
def gen_fspecial():
    """d[r_i] = rsqrt(r_j), for register pairs the compiler never emitted.

    Recovered model (EXP-0161 run01/run02, both carriers):
      byte+3 (db `src`)     = DESTINATION register, (reg<<1)|size, reg = v>>1
      byte+5 (db `src_ext`) = SOURCE register,       reg<<2,       reg = v>>2
      byte+1 high nibble (db `dst`) = INERT
    """
    blk = bytes.fromhex(REP["k_rsqrt"]["main_hex"])[18:28]
    seeds = H.seeds_for("float")
    out = []
    pairs = [(i, j) for i in range(1, 15) for j in range(1, 15) if i != j]
    pairs = pairs[::13][:16] + [(5, 9), (9, 5), (14, 2), (2, 14), (7, 7), (12, 3)]
    for (i, j) in pairs:
        b = set_f(blk, 0, "fspecial", "src", 2 * i)
        b = set_f(b, 0, "fspecial", "src_ext", 4 * j)
        pred = list(seeds)
        if j != i:
            pred[j] = 0                       # release-on-read
        pred[i] = fbits(1.0 / (f32(seeds[j]) ** 0.5))
        pred[15] = 0
        out.append({"gen": "fspecial", "kind": "float", "block": b.hex(),
                    "desc": "r%d = rsqrt(r%d)" % (i, j),
                    "params": {"dst_reg": i, "src_reg": j,
                               "src_field": 2 * i, "src_ext_field": 4 * j},
                    "pred_regs": pred, "tol_ulp_rel": 1e-5})
    return out


def gen_carry():
    """p = (r[a] CMP r[b]) for compare operands the compiler never emitted.

    Recovered model: byte+1 (db `srcA`) and byte+3 (db `srcB`) are both
    `(reg<<1)|is32` selectors with an INERT bit 7 (EXP-0146 on M4; reproduced
    here on G17P by the dense INPLACE sweep, which accepts exactly the two
    values {0x01,0x81} / {0x03,0x83}).

    gen02 GENERATED these with `is32 = 0` and 9 of 16 predictions failed. All
    16 outcomes are explained EXACTLY by the size bit being real: with
    `is32 = 0` the hardware compares only the LOW 16 BITS. gen03 therefore
    generates BOTH widths and predicts each from its own rule -- the failure
    diagnosed a semantic, and the corrected model is what is tested here.

    Only a, b in r5..r14 are used, so the rest of the lifted u64-add chain
    (which reads r1..r4) is untouched and the ONLY observable difference is the
    carry bit the psel materializes into the high word.
    """
    main = bytes.fromhex(REP["k_u64add"]["main_hex"])
    blk = main[32:72]
    seeds = H.seeds_for("int")
    out = []
    pairs = [(5, 9), (9, 5), (7, 11), (11, 7), (6, 14), (14, 6), (8, 8),
             (10, 12), (12, 10), (13, 5), (5, 13), (11, 14), (14, 11),
             (6, 8), (8, 6), (9, 13)]
    for (a, b) in pairs:
        for is32 in (1, 0):
            for top in (0, 0x80):       # bit 7 is claimed INERT -- generate both
                if top and is32 == 0:
                    continue            # keep the matrix small: bit7 x 32-bit only
                va = top | (a << 1) | is32
                vb = top | (b << 1) | is32
                if is32:
                    pred = int(seeds[a] < seeds[b])
                else:
                    pred = int((seeds[a] & 0xFFFF) < (seeds[b] & 0xFFFF))
                nb = set_f(blk, 10, "carry_gen", "srcA", va)
                nb = set_f(nb, 10, "carry_gen", "srcB", vb)
                out.append({"gen": "carry_gen", "kind": "int", "block": nb.hex(),
                            "desc": "p = (r%d <u%d r%d)%s"
                                    % (a, 32 if is32 else 16, b,
                                       " [bit7 set]" if top else ""),
                            "params": {"a": a, "b": b, "is32": is32,
                                       "bit7": bool(top),
                                       "srcA_field": va, "srcB_field": vb,
                                       "pred_predicate": pred},
                            "pred_regs": None})
    return out


def gen_zext():
    """r[n] = r[n] & 0xFFFF for every n, driven by byte0's HIGH NIBBLE --
    a field db.json does not model at all (it pins byte0 == 0x13)."""
    blk = bytes.fromhex(REP["k_zext16"]["main_hex"])[18:22]
    seeds = H.seeds_for("int")
    out = []
    for n in range(16):   # gen02: nibbles 0..A drive r0..r10; 0xB..0xF are a no-op
        b = bytearray(blk)
        b[0] = (n << 4) | 0x03
        pred = list(seeds)
        pred[n] = seeds[n] & 0xFFFF
        pred[15] = 0
        out.append({"gen": "mov_zext16", "kind": "int", "block": bytes(b).hex(),
                    "desc": "r%d = r%d & 0xFFFF" % (n, n),
                    "params": {"n": n, "byte0": (n << 4) | 0x03},
                    "pred_regs": pred})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    rundir = EXP / "raw" / a.run
    rundir.mkdir(parents=True, exist_ok=True)
    log = S.Log(rundir / "sweep.jsonl")

    cases = gen_fspecial() + gen_carry() + gen_zext()
    counts = {"pass": 0, "fail": 0, "fault": 0}
    car = S.Carrier(EXP / "kernels" / "carrier_seed.metal", "k",
                    EXP / "work" / ("gen_%s" % a.run), timeout=8.0,
                    fast_math=False,
                    inputs={0: ("poison_synth.bin", CM.poison(H.OUT_WORDS)),
                            1: ("seedbuf.bin", H.seed_buffer_bytes())},
                    outs={0: H.OUT_WORDS * 4})
    (rundir / "00_env.json").write_text(json.dumps(
        {"target": "G17P", "device": car.device, "kind": "generation-proof",
         "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}, indent=1))

    # carry_gen needs its own unmutated baseline to know the high word
    cbase = None
    main_u64 = bytes.fromhex(REP["k_u64add"]["main_hex"])
    # A sibling's device reset can land in our very first command buffer as an
    # `...ErrorInnocentVictim`; retry with backoff rather than losing the
    # baseline the whole carry_gen generation arm is scored against.
    for att in range(8):
        resp, outs = car.run_program(
            H.synth_program("int", main_u64[32:72], car.region_len), grid=1, tg=1)
        if resp["status"] == "OK":
            cbase = S.digest(S.words_u32(outs.get(0, b"")))
            break
        time.sleep(3.0 * (att + 1))
        if att == 3:
            car.restart()
    log.write({"gen": "carry_gen", "desc": "__baseline", "status": resp["status"],
               "regs": cbase["regs"] if cbase else None,
               "note": "unmutated lifted u64-add chain; its r1 is the carry-1 "
                       "high word every generated carry_gen case is scored against"})

    for c in cases:
        blk = bytes.fromhex(c["block"])
        for att in range(3):
            resp, outs = car.run_program(
                H.synth_program(c["kind"], blk, car.region_len), grid=1, tg=1)
            if resp["status"] == "OK" or not S.is_victim(resp["error"]):
                break
            time.sleep(2.0)
        d = S.digest(S.words_u32(outs.get(0, b""))) if resp["status"] == "OK" else None
        rec = dict(c)
        rec.update(status=resp["status"], error=resp["error"],
                   observed=(["%08x" % v for v in d["regs"]] if d else None),
                   pre=(d["pre"] if d else None), post=(d["post"] if d else None))
        if d is None:
            rec["verdict"] = "fault"
            counts["fault"] += 1
        elif c["gen"] == "carry_gen":
            if cbase is None:
                rec["verdict"] = "no_baseline"
            else:
                got_hi = d["regs"][1]
                p_obs = (1 if got_hi == cbase["regs"][1] else
                         (0 if got_hi == (cbase["regs"][1] - 1) & M32 else None))
                rec["observed_predicate"] = p_obs
                rec["verdict"] = ("pass" if p_obs == c["params"]["pred_predicate"]
                                  else "fail")
                counts["pass" if rec["verdict"] == "pass" else "fail"] += 1
        else:
            pred = c["pred_regs"]
            if c["gen"] == "fspecial":
                okk = all(
                    (abs(f32(d["regs"][i]) - f32(pred[i]))
                     <= 1e-5 * max(1.0, abs(f32(pred[i]))))
                    if d["regs"][i] != pred[i] else True
                    for i in range(15))
            else:
                okk = d["regs"][:15] == pred[:15]
            rec["pred_regs_hex"] = ["%08x" % v for v in pred]
            rec["verdict"] = "pass" if okk else "fail"
            rec["diff"] = [{"reg": i, "pred": "%08x" % pred[i],
                            "got": "%08x" % d["regs"][i]}
                           for i in range(15) if d["regs"][i] != pred[i]]
            counts["pass" if okk else "fail"] += 1
        rec.pop("pred_regs", None)
        log.write(rec)
        print("  %-10s %-24s %s" % (c["gen"], c["desc"], rec["verdict"]))
    car.close()
    log.close()
    (rundir / "02_summary.json").write_text(json.dumps(counts, indent=1))
    print("GEN", json.dumps(counts))


if __name__ == "__main__":
    main()
