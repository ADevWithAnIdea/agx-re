#!/usr/bin/env python3
"""EXP-0139 PILOT (disclosed, non-gated): smoke-test the carrier + the two
priority-1 constructions before freezing the pre-registration."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
sys.path.insert(0, str(EXP / "harness"))
import isa_helpers as H
import sweeprun as S

CARRIER_LEN = 1536
SLOT_OUT = 0
R_IDX = 15

def prog(instrs):
    p = H.build_program(instrs + [H.stop()], CARRIER_LEN)
    H.assert_round_trip(p)
    return p.hex()

def ibitcount(dst_reg, src_reg, fn_hi=0, form=5, cache=1, op_enable=2,
              srcdesc=0x5c, tail=4):
    return H.isadb.assemble("ibitcount", {
        "fn_hi": fn_hi & 1, "form": form & 0xFF, "cache": cache & 1,
        "dst": (dst_reg << 1) & 0xFF, "op_enable": op_enable & 0xFF,
        "src": (src_reg << 2) & 0xFF, "srcdesc": srcdesc & 0xFF, "tail": tail & 0xFF})

sw = S.Sweeper(EXP/"kernels"/"carrier_dag.metal", "k", HERE/"run", HERE/"work", timeout=8.0)
print("DEVICE", sw.device, "main_len", sw.region_len)
mem = sw.write_input("mem.bin", [float(i) for i in range(16)])
ins = {1: mem, 2: sw.write_input("imem.bin", [0]*16, "i")}

# A. iadd2 register-mode reproduction (EXP-0128 rule)
for (N, dstr, a, b) in [(2, 5, 10, 20), (7, 40, 33, 44), (0, 6, 21, 21)]:
    instrs = [H.mov_imm(R_IDX, 0), H.mov_imm(0, a)]
    if N: instrs.append(H.mov_imm(N, b))
    instrs.append(H.iadd2_reg_r0_plus_rN(dstr, N))
    instrs.append(H.device_store(R_IDX, 0, SLOT_OUT, data_reg=dstr))
    r, iw, fw = sw.run_case(prog(instrs), ins=ins, out_words=4)
    print("IADD2 N=%d dst=%d %d+%d -> status=%s int=%s" % (N, dstr, a, b, r["status"], iw[:2]))

# B. ibitcount popcount with a mov_imm-seeded source
for (src, dstr, val) in [(3, 5, 85), (3, 5, 127), (9, 2, 0), (3, 5, 1)]:
    instrs = [H.mov_imm(R_IDX, 0), H.mov_imm(src, val),
              ibitcount(dstr, src),
              H.device_store(R_IDX, 0, SLOT_OUT, data_reg=dstr)]
    r, iw, fw = sw.run_case(prog(instrs), ins=ins, out_words=4)
    print("POPCNT src=r%d val=%d dst=r%d -> status=%s int=%s expect=%d"
          % (src, val, dstr, r["status"], iw[:2], bin(val).count("1")))
sw.close()
