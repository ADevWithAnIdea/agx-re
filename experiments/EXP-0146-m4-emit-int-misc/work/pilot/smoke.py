#!/usr/bin/env python3
"""EXP-0146 smoke: baseline-only run of each carrier + throughput measurement."""
import sys, time
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
sys.path.insert(0, str(EXP / "harness"))
import sweeplib as S, oracles as O

K = EXP / "kernels"
WD = HERE / "smokework"
RD = HERE / "smokeraw"

cases = [
    ("u64add", "k_u64add.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 64},
     O.oracle_u64add(), S.words64),
    ("u64sub", "k_u64sub.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 64},
     O.oracle_u64sub(), S.words64),
    ("logic_and", "k_logic_and.metal", {0: O.pack32(O.LOGIC_A), 1: O.pack32(O.LOGIC_B)}, {2: 32},
     O.oracle_logic_and(), S.words32),
    ("zext16", "k_zext16.metal", {0: O.pack32(O.U32_A)}, {1: 32}, O.oracle_zext16(), S.words32),
    ("rot_imm", "k_rot_imm.metal", {0: O.pack32(O.U32_A)}, {1: 32}, O.oracle_rot_imm(), S.words32),
    ("rot_var", "k_rot_var.metal", {0: O.pack32(O.U32_A), 1: O.pack32(O.U32_B)}, {2: 32},
     O.oracle_rot_var(), S.words32),
    ("u64eq", "k_u64eq.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 32},
     O.oracle_u64eq(), S.words32),
    ("roundmodes", "k_roundmodes.metal", {0: O.packf32(O.F32_ROUND)}, {1: 32},
     O.oracle_roundmodes(), S.words32),
    ("sfu_sin", "k_sfu_sin.metal", {0: O.packf32(O.F32_SIN)}, {1: 32}, O.oracle_sin(), S.floats32),
    ("u64mul", "k_u64mul.metal", {0: O.pack64(O.U64_A), 1: O.pack64(O.U64_B)}, {2: 64},
     O.oracle_u64mul(), S.words64),
    ("u32x32to64", "k_u32x32to64.metal", {0: O.pack32(O.U32_A), 1: O.pack32(O.U32_B)}, {2: 64},
     O.oracle_u32x32to64(), S.words64),
    ("s32x32to64", "k_s32x32to64.metal", {0: O.pack32(O.U32_A), 1: O.pack32(O.U32_B)}, {2: 64},
     O.oracle_s32x32to64(), S.words64),
]
for name, src, ins, outs, oracle, dec in cases:
    c = S.Carrier(name, K / src, ins, outs, 8, 8, RD, WD)
    oidx = list(outs)[0]
    resp = c.run_main(c.main_bytes)
    obs = dec(resp["outs"].get(oidx, b""))
    ok = (obs == oracle) if dec is not S.floats32 else all(
        abs(a - b) < 1e-3 for a, b in zip(obs, oracle))
    print("%-12s dev=%s status=%-12s match=%s" % (name, c.device, resp["status"], ok))
    if not ok:
        print("   obs   ", [hex(v) if isinstance(v, int) else round(v, 6) for v in obs])
        print("   oracle", [hex(v) if isinstance(v, int) else round(v, 6) for v in oracle])
    # throughput
    t0 = time.time(); N = 20
    for _ in range(N):
        c.run_main(c.main_bytes)
    print("   %.1f ms/case" % ((time.time() - t0) / N * 1000))
    c.close()
