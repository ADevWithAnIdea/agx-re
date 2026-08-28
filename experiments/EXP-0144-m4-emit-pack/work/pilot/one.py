import struct, sys
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
import probe
BIN, WORK, SRC = EXP/"work"/"bin", EXP/"work"/"pilot", EXP/"kernels"/"carriers.metal"
fn = sys.argv[1]
INB = {"c_unpack": struct.pack("<6I",0x12345678,0x00010002,0x00030004,0x00050006,0x00070008,0x0009000a),
       "c_i2f_src": struct.pack("<6i",3,5,7,11,13,17),
       "c_f2h": struct.pack("<6f",1.5,2.25,3.125,-4.75,5.5,0.375),
       "c_f2bf": struct.pack("<6f",1.5,2.25,3.125,-4.75,5.5,0.375)}[fn] + b"\x00"*4072
c = probe.Carrier(SRC, fn, BIN, WORK)
b = probe.Bench(c, BIN, 1, INB, 0, 256)
for trial in range(3):
    st, out, gt, err = b.run({})
    print(fn, trial, st, err, " ".join("%08x" % w for w in struct.unpack("<%dI" % (len(out)//4), out))[:200])
b.close()
