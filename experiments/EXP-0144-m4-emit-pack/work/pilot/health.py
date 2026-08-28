import struct, sys
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP/"harness"))
import probe, casematrix as CM
c = probe.Carrier(EXP/"kernels"/"carriers.metal", "c_pack", EXP/"work"/"bin", EXP/"work"/"pilot")
b = probe.Bench(c, EXP/"work"/"bin", 1, CM.invec_bytes("c_pack", CM.FIXED["c_pack"][1]), 0, 256)
for i in range(3):
    st, ob, sent, gt, err = b.run({})
    print("health", i, st, (ob[:8].hex() if ob else None), "sent", sent[:8].hex() if sent else None, err)
b.close()
