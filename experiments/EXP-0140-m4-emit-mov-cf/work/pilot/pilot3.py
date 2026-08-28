#!/usr/bin/env python3
"""Pilot 3 (NOT gated): CF skeleton baseline on carrier_cf."""
import struct, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
EXP = HERE.parents[1]; REPO = EXP.parents[1]
for p in ("tools/agx-isa","tools/shdump","tools/agxtest"): sys.path.insert(0,str(REPO/p))
sys.path.insert(0, str(EXP/"harness"))
import isadb, agxparse, isa_helpers as H
from persistrun import PersistRunner
BIN=EXP/"work"/"bin"; K=EXP/"kernels"; SRC=K/"carrier_cf.metal"
arch=HERE/"carrier_cf.bin"
subprocess.run([str(BIN/"shdump"),"-o",str(arch),"--no-fast-math",str(SRC),"-f","k"],check=True,capture_output=True)
buf=arch.read_bytes(); roff,_=agxparse.locate_region(buf,"_agc.main")
_,pc=agxparse.extract_agx(buf); main=pc["_agc.main"]
print("cf main_len",len(main))
# base_slot re-derivation
off=0; loads=[]; stores=[]
while off<len(main):
    rec,L=isadb.decode_one(main,off)
    if rec["mnemonic"]=="device_load": loads.append(rec["fields"]["base_slot"])
    if rec["mnemonic"]=="device_store": stores.append(rec["fields"]["base_slot"])
    off+=L
print("loads",loads,"stores",stores)
A=[10.0]*8; N=[5]*8
(HERE/"cf_a.bin").write_bytes(b"".join(struct.pack("<f",v) for v in A))
(HERE/"cf_n.bin").write_bytes(b"".join(struct.pack("<i",v) for v in N))
prog=H.cf_program()
H.assert_round_trip(prog)
print("cf prog len",len(prog))
b=bytearray(buf); b[roff:roff+len(main)]=prog
sp=HERE/"cfsp.bin"; sp.write_bytes(bytes(b))
r=PersistRunner(source=str(SRC),function="k",fast_math=False,agxrun_persist=str(BIN/"agxrun_persist"))
resp=r.request(archive=str(sp),grid=8,tg=8,ins={1:str(HERE/"cf_a.bin"),2:str(HERE/"cf_n.bin")},outs={0:32},timeout=8)
vals=[struct.unpack_from("<f",resp["outs"].get(0,b"\0"*32),i)[0] for i in range(0,32,4)]
print("cf spliced-skeleton", resp["status"], vals, "oracle", H.cf_oracle(10.0,5))
# unmodified carrier control
resp2=r.request(archive=str(arch),grid=8,tg=8,ins={1:str(HERE/"cf_a.bin"),2:str(HERE/"cf_n.bin")},outs={0:32},timeout=8)
vals2=[struct.unpack_from("<f",resp2["outs"].get(0,b"\0"*32),i)[0] for i in range(0,32,4)]
print("cf natural       ", resp2["status"], vals2)
r.close()
