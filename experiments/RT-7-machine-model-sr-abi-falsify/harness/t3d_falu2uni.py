#!/usr/bin/env python3
# RT-7 Task 3 (v4): confirm the srcA-uniform (falu2_uni) form `09 0d 14 01 80 c0`
# reads a runtime uniform and that ITS select is bit39 (byte+4 bit7) + byte+1 index.
# Emitted by fast-math a[gid]+p.f0. Compare to the srcB form (t3c) whose select is
# byte+2 bit4 + byte+5 bit1. => BOTH forms are valid uniform sources (per operand
# position); RT-1a-FIX's "supersedes/was-wrong" framing is the discrepancy.
# CLEAN-ROOM: OWN-SHADER + HW-PROBE.
import os, sys, subprocess, struct, importlib.util, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
sys.path.insert(0,HERE); from persistrun import PersistRunner
src=("#include <metal_stdlib>\nusing namespace metal;\n"
     "struct P{ float f0; };\n"
     "kernel void k(device float* out [[buffer(0)]], const device float* a [[buffer(1)]],\n"
     "              constant P& p [[buffer(2)]], uint gid [[thread_position_in_grid]]){ out[gid]=a[gid]+p.f0; }\n")
kp=os.path.join(HERE,"kernels","fu.metal"); open(kp,"w").write(src)
arch=os.path.join(HERE,"fu.bin")
subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k",kp],capture_output=True)  # FAST MATH (default)
buf=open(arch,"rb").read(); _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
i=0;n=len(main);fa=None
while i+6<=n:
    if main[i]==0x09:
        length=8 if (main[i+2]&0x02) else 6
        if (main[i+2]&0x07)==0b100: fa=(i,length,main[i:i+length]); break
        i+=length
    elif main[i] in (0x67,0xe7): i+=14
    elif main[i]==0x0e: i+=4
    else: i+=2
off,ln,by=fa; print("falu2_uni bytes:",by.hex(),"byte+1=0x%02x(exp %d) byte+4=0x%02x bit39=%d"%(by[1],by[1]>>4,by[4],(by[4]>>7)&1))
loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
base=int(loc[0])
abuf=os.path.join(HERE,"u_a.bin"); open(abuf,"wb").write(struct.pack("<f",0.0))
pbuf=os.path.join(HERE,"u_p.bin")
r=PersistRunner(source=kp,function="k",fast_math=True,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
print("\n(A) runtime uniform (a=0):")
for v0 in [7.0,55.0,1000.0]:
    open(pbuf,"wb").write(struct.pack("<f",v0))
    resp=r.request(archive=arch,grid=1,tg=1,ins={1:abuf,2:pbuf},outs={0:4},timeout=8)
    o=struct.unpack_from('<f',resp["outs"][0],0)[0] if resp["status"]=="OK" else None
    print("  p.f0=%-6s -> out=%s"%(v0,o))
open(pbuf,"wb").write(struct.pack("<f",1000.0))
print("\n(C) toggle candidate select bits (uniform=1000,a=0):")
for name,boff,mask in [("bit39=byte+4 bit7",4,0x80),("byte+2 bit4",2,0x10),("byte+5 bit1",5,0x02)]:
    spa=os.path.join(HERE,"u_sp.bin"); shutil.copyfile(arch,spa)
    nb=by[boff]^mask
    with open(spa,"r+b") as f: f.seek(base+off+boff); f.write(bytes([nb]))
    resp=r.request(archive=spa,grid=1,tg=1,ins={1:abuf,2:pbuf},outs={0:4},timeout=8)
    v=struct.unpack_from('<f',resp["outs"][0],0)[0] if resp["status"]=="OK" and 0 in resp["outs"] else None
    print("  toggle %-18s (0x%02x->0x%02x) -> out=%s %s"%(name,by[boff],nb,v,"(unchanged)" if v==1000 else "(CHANGED)"))
r.close()
