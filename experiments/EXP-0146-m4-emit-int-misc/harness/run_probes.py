#!/usr/bin/env python3
"""EXP-0146 targeted follow-up probes (run05) -- the adversarial / second-method pass.

P1  native 64-bit ADD confirmation: the `k_u64sub` carrier with `addsub` flipped 0->1, run
    against a SECOND, independent boundary-input set, 5 repetitions, with the unmutated
    baseline re-validated before and after.
P2  `carry_gen.dst` <-> `psel` consumer coupling: cross carry_gen's dst nibble with the psel
    bytes to test whether dst is a predicate-REGISTER index that the consumer can follow.
P3  `mov_zext16.src_reg` on a second carrier where the source is NOT the immediately
    preceding load (tests the ALU-forward explanation for its inertness).
P4  carrier search for `sr_read_wide` and `int_alu_ehi`.

  python3 harness/run_probes.py --run-id run05
"""
import argparse
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(HERE))
import sweeplib as S   # noqa: E402
import oracles as O    # noqa: E402
import arms as A       # noqa: E402
import isadb           # noqa: E402
from run_sweep import fault_class, hexlist  # noqa: E402

K = EXP / "kernels"
M64 = O.M64

# --- P1: a SECOND, independent 64-bit input set (not the frozen U64_A/U64_B) -------------
U64_A2 = [0x8000000000000000, 0x00000000FFFFFFFF, 0xFFFFFFFF00000000, 0x0000000100000000,
          0x7FFFFFFFFFFFFFFF, 0xAAAAAAAAAAAAAAAA, 0x00000000DEADBEEF, 0xFFFFFFFFFFFFFFFE]
U64_B2 = [0x8000000000000000, 0x0000000000000001, 0x00000000FFFFFFFF, 0xFFFFFFFFFFFFFFFF,
          0x0000000000000001, 0x5555555555555556, 0xFFFFFFFF00000000, 0x0000000000000003]


def run(run_id, timeout=8.0):
    run_dir = EXP / "raw" / run_id
    if (run_dir / "sweep.jsonl").exists():
        sys.exit("REFUSING to reuse run id %s" % run_id)
    workdir = EXP / "work" / run_id
    rec = S.Recorder(run_dir / "sweep.jsonl")
    rec.record({"instr": "_meta", "field": "run", "value": 0, "bytes": "",
                "observed": {"run_id": run_id}, "oracle": {}, "match": True, "outcome": "ok",
                "carrier": "-", "note": "EXP-0146 targeted follow-up probes P1-P4"})
    t0 = time.time()

    def emit(instr, field, value, b, obs, orc, match, outcome, carrier, note):
        rec.record({"instr": instr, "field": field, "value": value, "bytes": b,
                    "observed": obs, "oracle": orc, "match": match, "outcome": outcome,
                    "carrier": carrier, "note": note})

    # ---------------------------------------------------------------- P1
    ins = {0: O.pack64(U64_A2), 1: O.pack64(U64_B2)}
    c = S.Carrier("P1_u64sub2", K / "k_u64sub.metal", ins, {2: 64}, 8, 8, run_dir, workdir,
                  timeout=timeout)
    irec, iraw = c.instr_at(0x20)
    orc_sub = [(a - b) & M64 for a, b in zip(U64_A2, U64_B2)]
    orc_add = [(a + b) & M64 for a, b in zip(U64_A2, U64_B2)]
    for tag, fieldval, oracle in (("baseline_sub", 0, orc_sub), ("addsub=1", 1, orc_add),
                                   ("baseline_sub_after", 0, orc_sub)):
        f2 = dict(irec["fields"]); f2["addsub"] = fieldval
        mut = isadb.assemble("iadd2", f2)
        reps = []
        for _ in range(5):
            r = c.run_with_instr(0x20, mut)
            obs = S.words64(r["outs"].get(2, b""))
            oc, mt = S.classify(r["status"], obs, oracle)
            reps.append({"outcome": oc, "match": mt, "words": hexlist(obs),
                          "fault_class": fault_class(r.get("error"))})
        allmatch = all(x["match"] for x in reps)
        emit("iadd2", "P1_" + tag, fieldval, mut.hex(),
             {"reps": [x["outcome"] for x in reps], "words": reps[0]["words"],
              "all_match": allmatch, "fault_classes": [x["fault_class"] for x in reps]},
             {"words": hexlist(oracle)}, allmatch, "ok" if allmatch else reps[0]["outcome"],
             "u64sub_inputset2",
             "P1: SECOND independent boundary input set; oracle = 64-bit %s"
             % ("subtract" if fieldval == 0 else "ADD"))
        print("P1 %-20s all_match=%s %s" % (tag, allmatch, [x["outcome"] for x in reps]))
    c.close()

    # ---------------------------------------------------------------- P2
    ins = {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}
    c = S.Carrier("P2_u64add", K / "k_u64add.metal", ins, {2: 64}, 8, 8, run_dir, workdir,
                  timeout=timeout)
    cg, cg_raw = c.instr_at(0x2a)
    ps, ps_raw = c.instr_at(0x30)
    oracle = O.oracle_u64add()
    emit("psel", "_baseline", 0, ps_raw.hex(), {"fields": ps["fields"]}, {}, True, "ok",
         "u64add", "P2: the psel that consumes carry_gen's predicate, at +0x30")
    for cg_dst in range(16):
        for pb in range(3):                       # psel bytes +1,+2,+3
            for pv in range(0, 256, 8):           # 32-point sample of each psel byte
                f2 = dict(cg["fields"]); f2["dst"] = cg_dst
                mcg = isadb.assemble("carry_gen", f2)
                mps = bytearray(ps_raw); mps[pb + 1] = pv
                mb = bytearray(c.main_bytes)
                mb[0x2a:0x2a + len(mcg)] = mcg
                mb[0x30:0x30 + len(mps)] = bytes(mps)
                r = c.run_main(bytes(mb))
                obs = S.words64(r["outs"].get(2, b""))
                oc, mt = S.classify(r["status"], obs, oracle)
                if mt or (cg_dst != 3 and oc == "ok"):
                    emit("carry_gen", "P2_dst_x_psel_b%d" % (pb + 1), [cg_dst, pv],
                         mcg.hex() + "/" + bytes(mps).hex(),
                         {"words": hexlist(obs), "status": r["status"]},
                         {"words": hexlist(oracle)}, mt, oc, "u64add",
                         "P2: carry_gen.dst x psel byte+%d -- MATCH" % (pb + 1))
    emit("carry_gen", "P2_done", 0, "", {}, {}, True, "ok", "u64add",
         "P2 complete: only MATCHING (cg_dst, psel byte) combinations were recorded above; "
         "the exhaustive negative space is 16 x 3 x 32 = 1536 combinations")
    print("P2 done")
    c.close()

    # ---------------------------------------------------------------- P3
    A3 = [0x00010001, 0x8000FFFF, 0xFFFFFFFF, 0x12345678, 0xDEADBEEF, 0x0000FFFF,
          0xFFFF0000, 0xA5A5A5A5]
    B3 = [1, 2, 3, 4, 5, 6, 7, 8]

    def orc_p3():
        out = []
        for a, b in zip(A3, B3):
            t = (a * 3 + b) & 0xFFFFFFFF
            u = t ^ 0x5A5A5A5A
            out.append(((u & 0xFFFF) + (u & 0xFFFF0000)) & 0xFFFFFFFF)
        return out

    try:
        c = S.Carrier("P3_zext_far", K / "k_zext16_far.metal",
                      {0: O.pack32(A3), 1: O.pack32(B3)}, {2: 32}, 8, 8, run_dir, workdir,
                      timeout=timeout)
        recs, _ = isadb.disassemble(c.main_bytes)
        seq = [r["mnemonic"] for r in recs]
        off = None
        o = 0
        for r in recs:
            if r["mnemonic"] == "mov_zext16":
                off = o
                break
            o += r["length"] or 0
        oracle = orc_p3()
        base = c.run_main(c.main_bytes)
        bobs = S.words64(b"") if False else S.words32(base["outs"].get(2, b""))
        boc, bmt = S.classify(base["status"], bobs, oracle)
        emit("mov_zext16", "P3_baseline", 0, "", {"seq": seq, "words": hexlist(bobs),
             "zext_off": off}, {"words": hexlist(oracle)}, bmt, boc, "zext16_far",
             "P3: second carrier; mov_zext16 present=%s" % (off is not None))
        print("P3 carrier seq:", " ".join(seq), "| mov_zext16 @", off, "| baseline", boc)
        if off is not None and bmt:
            irec, iraw = c.instr_at(off)
            for v in range(128):
                f2 = dict(irec["fields"]); f2["src_reg"] = v
                mut = isadb.assemble("mov_zext16", f2)
                r = c.run_with_instr(off, mut)
                obs = S.words32(r["outs"].get(2, b""))
                oc, mt = S.classify(r["status"], obs, oracle)
                emit("mov_zext16", "P3_src_reg", v, mut.hex(),
                     {"words": hexlist(obs), "status": r["status"],
                      "fault_class": fault_class(r.get("error"))},
                     {"words": hexlist(oracle)}, mt, oc, "zext16_far",
                     "P3: src_reg dense sweep on a carrier where the source is NOT the "
                     "immediately preceding load")
        c.close()
    except Exception as e:
        emit("mov_zext16", "P3_error", 0, "", {"err": str(e)[:300]}, {}, False, "undecodable",
             "zext16_far", "P3 carrier failed")
        print("P3 failed:", e)

    # ---------------------------------------------------------------- P4
    for name, msl in (("sr_read_wide", "k_rayquery.metal"),
                      ("int_alu_ehi", "k_std140_matcopy.metal")):
        outbin = workdir / (msl.replace(".metal", ".bin"))
        workdir.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([str(EXP / "work" / "bin" / "shdump"), "-o", str(outbin),
                            "-f", "k", "--no-fast-math", str(K / msl)],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            emit(name, "P4_carrier_search", 0, "", {"shdump_rc": r.returncode,
                 "stderr": r.stderr[-400:]}, {}, False, "undecodable", msl,
                 "P4: carrier search -- our own MSL did not compile")
            print("P4 %s: compile failed" % name)
            continue
        buf = outbin.read_bytes()
        _, pieces = S.agxparse.extract_agx(buf)
        mb = pieces["_agc.main"]
        recs, leftover = isadb.disassemble(mb)
        seq = [x["mnemonic"] for x in recs]
        found = name in seq
        emit(name, "P4_carrier_search", 0, mb.hex(),
             {"seq": seq, "found": found, "main_len": len(mb), "leftover": len(leftover)},
             {}, found, "ok" if found else "undecodable", msl,
             "P4: own-MSL carrier search for %s -- %s" % (name, "FOUND" if found else "ABSENT"))
        print("P4 %-14s found=%-5s  %s" % (name, found, " ".join(seq[:14])))

    rec.record({"instr": "_meta", "field": "done", "value": rec.n, "bytes": "",
                "observed": {"cases": rec.n, "elapsed_s": round(time.time() - t0, 1)},
                "oracle": {}, "match": True, "outcome": "ok", "carrier": "-", "note": "complete"})
    print("TOTAL %d records in %.1fs" % (rec.n, time.time() - t0))
    rec.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    a = ap.parse_args()
    run(a.run_id)
