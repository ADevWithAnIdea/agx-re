#!/usr/bin/env python3
# RT-7 Task 3 (v3): characterize the ACTUAL uniform-source form the current compiler
# emits for a[gid]+p.k = `09 01 0c 0d 00 c2` (EXP-0020 form: byte+2 bit4 clear +
# byte+5 bit1 set), which RT-1a-FIX declared "wrong/superseded" by falu2_uni.
#  (A) runtime uniform: vary bound p.f0 -> out tracks it.
#  (B) sweep byte+3 (uniform index candidate) on an 8-uniform kernel -> map/count.
#  (C) toggle candidate select bits (byte+2 bit4, byte+5 bit1, bit39) -> which flips
#      uniform<->GPR?
#  (D) fast-math vs no-fast-math + operand order: does falu2_uni (bit39 set) EVER appear?
# CLEAN-ROOM: OWN-SHADER + HW-PROBE.
import os, sys, subprocess, struct, importlib.util, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
sys.path.insert(0,HERE); from persistrun import PersistRunner

def build(NU, fast, name, extra=""):
    fields="".join("  float f%d;\n"%i for i in range(NU))
    src=("#include <metal_stdlib>\nusing namespace metal;\n"
         "struct P{\n%s};\n"%fields+
         "kernel void k(device float* out [[buffer(0)]], const device float* a [[buffer(1)]],\n"
         "              constant P& p [[buffer(2)]], uint gid [[thread_position_in_grid]]){ %s }\n"%extra)
    kp=os.path.join(HERE,"kernels","%s.metal"%name); open(kp,"w").write(src)
    arch=os.path.join(HERE,"%s.bin"%name)
    cmd=[os.path.join(HERE,"shdump"),"-o",arch,"-f","k",kp]
    if not fast: cmd.insert(-1,"--no-fast-math")
    subprocess.run(cmd,capture_output=True)
    return kp,arch
def getmain(arch):
    buf=open(arch,"rb").read(); _,p=ap.extract_agx(buf); return p["_agc.main"]
def first_fadd(main):
    i=0;n=len(main)
    while i+6<=n:
        if main[i]==0x09:
            length=8 if (main[i+2]&0x02) else 6
            if (main[i+2]&0x07)==0b100: return (i,length,main[i:i+length])
            i+=length
        elif main[i] in (0x67,0xe7): i+=14
        elif main[i]==0x0e: i+=4
        else: i+=2
    return None

# (D) does falu2_uni ever appear?
print("=== (D) encoding vs fast-math / operand order ===")
for fast in (False,True):
    for extra,lbl in [("out[gid]=a[gid]+p.f0;","a+p.k"),("out[gid]=p.f0+a[gid];","p.k+a")]:
        kp,arch=build(1,fast,"ud",extra)
        fa=first_fadd(getmain(arch))
        print("  fast=%-5s %-8s -> %s"%(fast,lbl,fa[2].hex() if fa else "none"))

# (A,B,C) use 8-uniform kernel, no-fast-math (the 0c..c2 form)
kp,arch=build(8,False,"u8","out[gid]=a[gid]+p.f0;")
main=getmain(arch); fa=first_fadd(main); off,ln,by=fa
print("\n8-uniform add bytes:",by.hex(),"off",off)
loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
base=int(loc[0])
abuf=os.path.join(HERE,"u_a.bin"); open(abuf,"wb").write(struct.pack("<f",0.0))
vals=[1000.0+i for i in range(8)]
pbuf=os.path.join(HERE,"u_p.bin"); open(pbuf,"wb").write(b"".join(struct.pack("<f",v) for v in vals))
r=PersistRunner(source=kp,function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
print("\n=== (A) runtime uniform (vary p.f0, a=0) ===")
for v0 in [7.0,55.0,1000.0]:
    vv=[v0]+vals[1:]; open(pbuf,"wb").write(b"".join(struct.pack("<f",v) for v in vv))
    resp=r.request(archive=arch,grid=1,tg=1,ins={1:abuf,2:pbuf},outs={0:4},timeout=8)
    o=struct.unpack_from('<f',resp["outs"][0],0)[0] if resp["status"]=="OK" else None
    print("  p.f0=%-6s -> out=%s"%(v0,o))
open(pbuf,"wb").write(b"".join(struct.pack("<f",v) for v in vals))
print("\n=== (B) sweep byte+3 (uniform index candidate); out=uniform[idx], idx=out-1000 ===")
hits={}
for idx in range(0,64):
    b3=(idx<<1)|(by[3]&1)
    spa=os.path.join(HERE,"u_sp.bin"); shutil.copyfile(arch,spa)
    with open(spa,"r+b") as f: f.seek(base+off+3); f.write(bytes([b3]))
    resp=r.request(archive=spa,grid=1,tg=1,ins={1:abuf,2:pbuf},outs={0:4},timeout=8)
    v=struct.unpack_from('<f',resp["outs"][0],0)[0] if resp["status"]=="OK" and 0 in resp["outs"] else None
    tag="=u[%d]"%int(v-1000) if (v is not None and 1000<=v<1008) else ""
    if tag: hits[idx]=int(v-1000)
    if idx<16 or tag: print("  idx=%-3d byte3=0x%02x %-6s out=%s %s"%(idx,b3,resp["status"],v,tag))
print("  uniform-index map (byte+3):",hits)
print("\n=== (C) toggle select-bit candidates on the a+p.f0 op (uniform=1000, a=0) ===")
for name,boff,mask in [("byte+2 bit4",2,0x10),("byte+5 bit1",5,0x02),("bit39=byte+4 bit7",4,0x80)]:
    spa=os.path.join(HERE,"u_sp.bin"); shutil.copyfile(arch,spa)
    nb=by[boff]^mask
    with open(spa,"r+b") as f: f.seek(base+off+boff); f.write(bytes([nb]))
    resp=r.request(archive=spa,grid=1,tg=1,ins={1:abuf,2:pbuf},outs={0:4},timeout=8)
    v=struct.unpack_from('<f',resp["outs"][0],0)[0] if resp["status"]=="OK" and 0 in resp["outs"] else None
    print("  toggle %-18s (0x%02x->0x%02x) -> out=%s %s"%(name,by[boff],nb,v,"(uniform still 1000)" if v==1000 else "(CHANGED)"))
r.close()
