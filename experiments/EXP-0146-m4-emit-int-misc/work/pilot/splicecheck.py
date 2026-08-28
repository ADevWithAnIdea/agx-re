#!/usr/bin/env python3
"""EXP-0146 pilot: prove the splice actually executes (the in-process AIR-memoization
gotcha the persistent runner is designed to defeat). Uses the HW-VALIDATED
iadd2 byte0 0x9f->0x1f add/sub polarity flip (RT-1a-FIX)."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]
sys.path.insert(0, str(EXP / "harness"))
import sweeplib as S, oracles as O
K = EXP / "kernels"
WD = HERE / "smokework"; RD = HERE / "smokeraw"

c = S.Carrier("u32add", K / "k_u32add.metal",
              {0: O.pack32(O.LOGIC_A), 1: O.pack32(O.LOGIC_B)}, {2: 32}, 8, 8, RD, WD)
base = c.run_main(c.main_bytes)
print("baseline    ", base["status"], [hex(v) for v in S.words32(base["outs"][2])])
print("host a+b    ", [hex((a + b) & 0xFFFFFFFF) for a, b in zip(O.LOGIC_A, O.LOGIC_B)])
mb = bytearray(c.main_bytes); mb[0x20] = 0x1f
r = c.run_main(bytes(mb))
print("0x9f->0x1f  ", r["status"], [hex(v) for v in S.words32(r["outs"][2])])
print("host a-b    ", [hex((a - b) & 0xFFFFFFFF) for a, b in zip(O.LOGIC_A, O.LOGIC_B)])
print("host b-a    ", [hex((b - a) & 0xFFFFFFFF) for a, b in zip(O.LOGIC_A, O.LOGIC_B)])
c.close()

# ilogic: flip op_base and lut bytes on the AND carrier and read the realized LUT
c = S.Carrier("logic_and", K / "k_logic_and.metal",
              {0: O.pack32(O.LOGIC_A), 1: O.pack32(O.LOGIC_B)}, {2: 32}, 8, 8, RD, WD)
rec, raw = c.instr_at(0x20)
print("\nilogic base", raw.hex(), rec["fields"])
for name, off, val in [("byte2=0x1e(op_base=0)", 0x22, 0x1e), ("lut_a=0x02", 0x24, 0x02),
                       ("lut_b=0x08", 0x25, 0x08), ("byte0=0x0a", 0x20, 0x0a)]:
    mb = bytearray(c.main_bytes); mb[off] = val
    r = c.run_main(bytes(mb))
    obs = S.words32(r["outs"].get(2, b""))
    lut = O.derive_lut2(O.LOGIC_A, O.LOGIC_B, obs) if r["status"] == "OK" else None
    print("  %-22s %-12s lut=%s (%s)" % (name, r["status"], lut,
                                          O.LUT_NAMES.get(lut, "not-a-bitwise-LUT")))
c.close()
