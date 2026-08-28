#!/usr/bin/env python3
"""Pilot 4 (NOT gated): per-byte sweep of sel.body (dsel5) and psel (gsel4)."""
import struct, subprocess, sys, time, json
from pathlib import Path
HERE=Path(__file__).resolve().parent; EXP=HERE.parents[1]; REPO=EXP.parents[1]
for p in ("tools/agx-isa","tools/shdump","tools/agxtest"): sys.path.insert(0,str(REPO/p))
sys.path.insert(0,str(EXP/"harness"))
import isadb, agxparse
from persistrun import PersistRunner
BIN=EXP/"work"/"bin"; K=EXP/"kernels"
def build(src):
    arch=HERE/(src.stem+".bin")
    subprocess.run([str(BIN/"shdump"),"-o",str(arch),"--no-fast-math",str(src),"-f","k"],check=True,capture_output=True)
    buf=arch.read_bytes(); roff,_=agxparse.locate_region(buf,"_agc.main")
    _,pc=agxparse.extract_agx(buf); return arch,buf,roff,pc["_agc.main"]
def ints(raw): return [struct.unpack_from("<i",raw,i)[0] for i in range(0,len(raw)-3,4)]
a=list(range(8)); (HERE/"a_int.bin").write_bytes(b"".join(struct.pack("<i",v) for v in a))
out={}
for name, instr_off, nbytes in (("dsel5",0x18,3),("gsel4",0x0a,3)):
    src=K/(name+".metal"); arch,buf,roff,main=build(src)
    base=main[instr_off:instr_off+4]
    print("==",name,"instr at +0x%x ="%instr_off, base.hex())
    r=PersistRunner(source=str(src),function="k",fast_math=False,agxrun_persist=str(BIN/"agxrun_persist"))
    sp=HERE/(name+"_sp.bin"); t0=time.time(); n=0
    for bi in range(1,4):
        res={}
        for v in range(256):
            b=bytearray(buf); b[roff+instr_off+bi]=v; sp.write_bytes(bytes(b))
            resp=r.request(archive=str(sp),grid=8,tg=8,ins={1:str(HERE/"a_int.bin")},outs={0:32},timeout=8)
            n+=1
            key = resp["status"] if resp["status"]!="OK" else tuple(ints(resp["outs"][0]))
            res.setdefault(str(key),[]).append(v)
        print(" byte+%d: %d distinct outcomes" % (bi, len(res)))
        for k2,vs in sorted(res.items(), key=lambda kv:-len(kv[1]))[:14]:
            print("    %-70s n=%3d  vals=%s" % (k2[:70], len(vs), vs[:8]))
        out["%s.b%d"%(name,bi)]=res
    print(" elapsed %.1fs for %d cases (%.3f s/case)"%(time.time()-t0,n,(time.time()-t0)/n))
    r.close()
json.dump(out, open(HERE/"pilot4.json","w"))
