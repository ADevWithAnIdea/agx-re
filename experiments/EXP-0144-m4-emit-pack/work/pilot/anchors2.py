#!/usr/bin/env python3
"""PILOT (non-recorded): re-derive the anchor offset/bytes for every carrier
after adding the integrity-sentinel path."""
import hashlib, sys
from pathlib import Path
EXP = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(EXP / "harness"))
sys.path.insert(0, str(EXP.parents[1] / "tools" / "agx-isa"))
import probe, isadb
BIN, WORK, SRC = EXP/"work"/"bin", EXP/"work"/"pilot", EXP/"kernels"/"carriers.metal"
WANT = {"c_pack":"pack_convert","c_unpack":"unpack_convert","c_i2f":"cvt_i2f",
        "c_i2f_src":"cvt_i2f_src","c_f2i":"cvt_f2i","c_f2h":None,"c_f2h_dst":None,
        "c_f2bf":None,"c_ph2":None}
PAT = {"c_f2h":"01011481","c_f2h_dst":"b1011481","c_f2bf":"01011481","c_ph2":None}
for fn, mn in WANT.items():
    c = probe.Carrier(SRC, fn, BIN, WORK)
    print("== %-10s main=%dB sha256=%s" % (fn, len(c.main), hashlib.sha256(c.main).hexdigest()))
    toks = c.tokens()
    for (o,m,b,f) in toks:
        if m == mn or (mn is None and m in ("half_alu","<unknown>","cvt_f2h","cvt_f2h_dst","cvt_bf16")):
            print("   +%3d (0x%02x) %-16s %s" % (o,o,m,b.hex()[:40]))
