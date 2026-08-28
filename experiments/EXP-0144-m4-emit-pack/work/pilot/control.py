#!/usr/bin/env python3
"""PILOT (non-recorded): splice-effect controls -- prove a byte change reaches
the hardware and that distinct field values give distinct observable results."""
import struct, sys, time
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import probe
BIN, WORK, SRC = EXP/"work"/"bin", EXP/"work"/"pilot", EXP/"kernels"/"anchors.metal"

inb = struct.pack("<8f", 0.25, 0.75, 0.5, 1.0, 0.0, -1.0, 2.0, 0.125)
c = probe.Carrier(SRC, "k_pack_unorm", BIN, WORK)
b = probe.Bench(c, BIN, 1, inb, 0, 16)
off, ab = c.find("pack_convert")
print("anchor @0x%x = %s" % (off, ab.hex()))
base = b.run({})[1]
print("baseline out = %s" % base.hex())
for name, ov in [("b+1 src_desc 0x04->0x00", {off+1: 0x00}),
                 ("b+1 src_desc 0x04->0x14", {off+1: 0x14}),
                 ("b+2 fmt_class 0x56->0x54", {off+2: 0x54}),
                 ("b+3 src 0x00->0x02",       {off+3: 0x02}),
                 ("b+3 src 0x00->0x04",       {off+3: 0x04}),
                 ("b+4 mode 0x02->0x03",      {off+4: 0x03}),
                 ("b+9 0x82->0x42 (snorm?)",  {off+9: 0x42}),
                 ("b+8 0x45->0x00",           {off+8: 0x00}),
                 ("b+0 0x97->0xff (illegal)", {off+0: 0xff})]:
    st, out, gt, err = b.run(ov)
    print("%-28s %-12s %s %s" % (name, st, out.hex(), "SAME" if out == base else "DIFF"))
b.close()
