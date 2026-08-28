#!/usr/bin/env python3
"""PILOT (non-recorded): per-carrier baseline vs host oracle + anchor location."""
import hashlib, struct, sys
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import probe, oracle as O
BIN, WORK, SRC = EXP/"work"/"bin", EXP/"work"/"pilot", EXP/"kernels"/"carriers.metal"

PF = struct.pack
CARR = {
 "c_pack":   dict(inb=PF("<6f",0.25,0.75,0.125,0.375,0.625,0.875)+b"\x00"*4072, nout=256, pat="97045618"),
 "c_unpack": dict(inb=PF("<6I",0x12345678,0x00010002,0x00030004,0x00050006,0x00070008,0x0009000a)+b"\x00"*4072, nout=256, pat="17045600"),
 "c_i2f":    dict(inb=PF("<6i",3,5,7,11,13,17)+b"\x00"*4072, nout=256, pat="a7075618"),
 "c_i2f_src":dict(inb=PF("<6i",3,5,7,11,13,17)+b"\x00"*4072, nout=256, pat="a7175418"),
 "c_f2i":    dict(inb=PF("<6f",3.75,-2.5,7.25,11.5,-13.125,17.875)+b"\x00"*4072, nout=256, pat="27075618"),
 "c_f2h":    dict(inb=PF("<6f",1.5,2.25,3.125,-4.75,5.5,0.375)+b"\x00"*4072, nout=256, pat="0101148104c2"),
 "c_f2h_dst":dict(inb=PF("<6f",1.5,2.25,3.125,-4.75,5.5,0.375)+b"\x00"*4072, nout=256, pat="b101148100c2"),
 "c_f2bf":   dict(inb=PF("<6f",1.5,2.25,3.125,-4.75,5.5,0.375)+b"\x00"*4072, nout=256, pat="0101148105024080"),
 "c_ph2":    dict(inb=PF("<8e",1.5,2.5,3.0,4.0,5.0,6.0,7.0,8.0)+b"\x00"*4080, nout=256, pat="9004050000c0"),
}
for fn, cfg in CARR.items():
    c = probe.Carrier(SRC, fn, BIN, WORK)
    h = hashlib.sha256(c.main).hexdigest()[:16]
    pat = bytes.fromhex(cfg["pat"])
    occ = [i for i in range(len(c.main)-len(pat)+1) if c.main[i:i+len(pat)] == pat]
    b = probe.Bench(c, BIN, 1, cfg["inb"], 0, cfg["nout"])
    st, out, gt, err = b.run({})
    print("== %-10s main=%dB sha=%s occ=%s status=%s err=%s" % (fn, len(c.main), h, occ, st, err))
    print("   out u32: %s" % " ".join("%08x" % w for w in struct.unpack("<%dI" % (len(out)//4), out)))
    b.close()
