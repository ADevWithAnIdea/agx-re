#!/usr/bin/env python3
"""EXP-0139 PILOT step 3 (disclosed, non-gated): baseline + liveness check for
every NATURAL carrier, and a throughput measurement."""
import sys, time, struct
from pathlib import Path
HERE=Path(__file__).resolve().parent; EXP=HERE.parents[1]
sys.path.insert(0,str(EXP/"harness"))
import sweeprun as S
sys.path.insert(0,str(EXP.parents[1]/"tools"/"agx-isa")); import isadb

SRC = EXP/"kernels"/"ialu_probes.metal"
A = [0x12345678, 0xFFFFFFFF, 0x0000FF00, 0xDEADBEEF, 1, 0, 0x80000000, 0x7FFFFFFF]
B = [3, 5, 8, 1, 31, 32, 2, 0]
N = len(A)

CASES = [
    ("k_bfe_const", 0x012, "ibfe"),
    ("k_shl",       0x02a, "ibfins"),
    ("k_imad",      0x020, "imad"),
    ("k_umax",      0x020, "iminmax"),
    ("k_abs",       0x01c, "isel8"),
    ("k_clz",       0x024, "isel10"),
    ("k_bfe_const_s", 0x01e, "isel_reg"),
    ("k_shr",       0x02a, "ibfe"),
]
for fn, off, mn in CASES:
    c = S.Carrier(SRC, fn, HERE/"work", timeout=8.0)
    ain = c.write_input("a.bin", A); bin_ = c.write_input("b.bin", B)
    t0=time.time()
    resp, iw, fw = c.run([], {0:ain,1:bin_}, out_slot=2, out_words=N, grid=N, tg=N)
    base = iw[:N]
    # liveness: flip one byte of the target instruction (byte+3 = dst-ish)
    recs,_ = isadb.disassemble(c.main_bytes)
    o=0; found=None
    for r in recs:
        if o==off: found=r; break
        o+=r["length"]
    orig = c.main_bytes[off:off+ (found["length"] if found else 0)]
    r2, iw2, _ = c.run([(off+2, bytes([c.main_bytes[off+2]^0x02]))], {0:ain,1:bin_}, 2, N, N, N)
    t=time.time()-t0
    print("%-14s +0x%03x %-10s len=%s base=%s" % (fn, off, mn, found["length"] if found else "?",
          [hex(x) for x in base[:4]]))
    print("               bytes=%s  flip_b2 -> %s %s" % (orig.hex(), r2["status"], [hex(x) for x in iw2[:4]]))
    print("               2 cases in %.2fs" % t)
    c.close()
