#!/usr/bin/env python3
"""Pilot 8 (NOT gated): does the LONGER cf carrier change the skeleton's own
select-comparison constant?  Compares carrier_cf.metal (EXP-0112's own,
HW-validated) against carrier_cf2.metal on identical skeleton bytes."""
import struct, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; EXP=HERE.parents[1]; REPO=EXP.parents[1]
for p in ("tools/agx-isa","tools/shdump","tools/agxtest"): sys.path.insert(0,str(REPO/p))
sys.path.insert(0,str(EXP/"harness"))
import agxparse, isa_helpers as H, cases as C
from persistrun import PersistRunner
BIN=EXP/"work"/"bin"; K=EXP/"kernels"
(HERE/"cf_a.bin").write_bytes(b"".join(struct.pack("<f",v) for v in C.CF_A))
(HERE/"cf_n.bin").write_bytes(b"".join(struct.pack("<i",v) for v in C.CF_N))
(HERE/"poison.bin").write_bytes(b"".join(struct.pack("<i",C.POISON_WORD(i)) for i in range(64)))
for name, sent in (("carrier_cf.metal", False), ("carrier_cf2.metal", True),
                   ("carrier_cf2.metal", False)):
    src=K/name; arch=HERE/(Path(name).stem+"_p8.bin")
    subprocess.run([str(BIN/"shdump"),"-o",str(arch),"--no-fast-math",str(src),"-f","k"],
                   check=True,capture_output=True)
    buf=arch.read_bytes(); roff,_=agxparse.locate_region(buf,"_agc.main")
    _,pc=agxparse.extract_agx(buf); ML=len(pc["_agc.main"])
    prog=H.cf_program(carrier_len=ML, sentinel=sent)
    b=bytearray(buf); b[roff:roff+ML]=prog
    sp=HERE/("p8_%s_%d.bin"%(Path(name).stem,sent)); sp.write_bytes(bytes(b))
    r=PersistRunner(source=str(src),function="k",fast_math=False,
                    agxrun_persist=str(BIN/"agxrun_persist"))
    resp=r.request(archive=str(sp),grid=8,tg=8,
                   ins={0:str(HERE/"poison.bin"),1:str(HERE/"cf_a.bin"),2:str(HERE/"cf_n.bin")},
                   outs={0:64},timeout=8)
    r.close()
    vals=[struct.unpack_from("<f",resp["outs"][0],4*i)[0] for i in range(8)]
    print("%-20s ML=%-4d sentinel=%-5s %s %s"%(name,ML,sent,resp["status"],vals))
orc=[H.cf_oracle(C.CF_A[i],C.CF_N[i]) for i in range(8)]
print("%-20s %38s %s"%("HOST ORACLE","",orc))
