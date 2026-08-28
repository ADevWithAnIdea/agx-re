#!/usr/bin/env python3
"""PILOT (non-recorded): baseline correctness + throughput measurement."""
import struct, sys, time
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import probe

BIN = EXP / "work" / "bin"
WORK = EXP / "work" / "pilot"
SRC = EXP / "kernels" / "anchors.metal"

# unorm2x16 pack: in = float2 (0.25, 0.75) -> expect round(0.25*65535)|round(0.75*65535)<<16
inb = struct.pack("<8f", 0.25, 0.75, 0.5, 1.0, 0.0, -1.0, 2.0, 0.125)
c = probe.Carrier(SRC, "k_pack_unorm", BIN, WORK)
print("main len", len(c.main))
for (o, m, b, f) in c.tokens():
    print("  +0x%02x %-16s %s" % (o, m, b.hex()))
b = probe.Bench(c, BIN, in_buf=1, in_bytes=inb, out_buf=0, out_nbytes=16)
t0 = time.time()
st, out, gt, err = b.run({})
print("baseline", st, out.hex(), "err", err, "%.1fms" % ((time.time()-t0)*1000))
u = struct.unpack("<I", out[:4])[0]
print("packed = 0x%08x  lanes %d %d  (expect %d %d)" % (u, u & 0xFFFF, u >> 16,
      round(0.25*65535), round(0.75*65535)))
# throughput
off, ab = c.find("pack_convert")
N = 64
t0 = time.time()
nok = 0
for v in range(N):
    st, out, gt, err = b.run({off + 4: v})
    if st == "OK":
        nok += 1
dt = time.time() - t0
print("throughput: %d runs in %.2fs = %.1f/s (ok=%d)" % (N, dt, N/dt, nok))
b.close()
