#!/usr/bin/env python3
"""Pilot smoke test (NON-GATED, work/ only): does a hand-built MODE A program
spliced into kernels/carrier.metal actually run and read back the seeds?"""
import sys
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H
import bench as B

bench = B.Bench(EXP / "kernels" / "carrier.metal", "k",
                EXP / "work" / "bin", EXP / "work" / "pilot" / "bw")
print("READY on", bench.device, "region_len", bench.region_len)
mem = bench.write_in(1, [float(i) for i in range(16)])

def prog(instrs):
    p = H.build_program(instrs, bench.region_len)
    H.assert_round_trip(p)
    return p

# 1. seed r0..r12, store r0, r2, and (r0+r2) via falu2 into words 0,4,8
instrs = [H.mov_imm(H.R_IDX, 0)]
for r, v in sorted(H.SEED.items()):
    instrs.append(H.seed(r, v))
instrs += [H.falu2_raw(6, 0, 2, opsel=4),          # r6 = r0 + r2 = 8.0  (overwrites seed 11.0)
           H.store_word(0, 0),                      # 5.0
           H.store_word(4, 2),                      # 3.0
           H.store_word(8, 6),                      # 8.0
           H.falu2_raw(7, 0, 2, opsel=5),           # r7 = r0 * r2 = 15.0
           H.store_word(12, 7),
           H.stop()]
resp = bench.run([(0, prog(instrs))], ins={1: mem}, outs={0: 64})
print("STATUS", resp["status"], resp.get("error"))
print("OUT", B.words_f32(resp["outs"].get(0, b""), 16))
bench.close()
