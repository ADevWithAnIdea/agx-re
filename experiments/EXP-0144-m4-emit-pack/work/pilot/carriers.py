#!/usr/bin/env python3
"""PILOT (non-recorded): tokenize each carrier, show where the target sits."""
import sys
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import probe
BIN, WORK, SRC = EXP/"work"/"bin", EXP/"work"/"pilot", EXP/"kernels"/"carriers.metal"
for fn in ["c_pack","c_unpack","c_i2f","c_i2f_src","c_f2i","c_f2h","c_f2h_dst","c_f2bf","c_ph2"]:
    c = probe.Carrier(SRC, fn, BIN, WORK)
    print("== %-10s main=%dB" % (fn, len(c.main)))
    for (o,m,b,f) in c.tokens():
        print("   +0x%02x %-16s %-30s %s" % (o,m,b.hex(),f))
