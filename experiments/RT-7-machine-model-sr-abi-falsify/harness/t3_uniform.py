#!/usr/bin/env python3
# RT-7 Task 3: falsify the uniform-source decode (falu2_uni) + count uniform regs.
# Kernel: out[gid] = a[gid] + p.f[0], a[gid]=0, p.f[i]=1000+i (distinct).
#  (A) vary the bound p buffer -> out tracks it (proves a RUNTIME uniform, not imm).
#  (B) confirm op is falu2_uni: byte+4 bit7(=bit39) set AND byte+1 exp-nibble<8.
#  (C) splice byte+1 (uniform index) -> sweep; out-0 = uniform value = which reg.
#      Count distinct uniforms + find the addressable cap (byte+1 exp<8 => 6-bit?).
#  (D) select bit: clear bit39 (byte+4 bit7) -> should become a GPR read, not uniform.
# CLEAN-ROOM: OWN-SHADER + HW-PROBE.
import os, sys, subprocess, struct, importlib.util, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
sys.path.insert(0,HERE); from persistrun import PersistRunner
NU=96
def src():
    fields="".join("  float f%d;\n"%i for i in range(NU))
    return ("#include <metal_stdlib>\nusing namespace metal;\n"
            "struct P{\n%s};\n"%fields+
            "kernel void k(device float* out [[buffer(0)]],\n"
            "              device const float* a [[buffer(1)]],\n"
            "              constant P& p [[buffer(2)]],\n"
            "              uint gid [[thread_position_in_grid]]){ out[gid]=a[gid]+p.f0; }\n")
kp=os.path.join(HERE,"kernels","uni.metal"); open(kp,"w").write(src())
arch=os.path.join(HERE,"uni.bin")
subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
buf=open(arch,"rb").read(); _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
# find falu2_uni: 0x09, byte+4 bit7 set (bit39), byte+1 exp nibble (>>4) < 8
i=0;n=len(main);uni=None
while i+6<=n:
    if main[i]==0x09:
        length=8 if (main[i+2]&0x02) else 6
        if (main[i+4]>>7)&1 and (main[i+1]>>4)<8:
            uni=(i,length,main[i:i+length].hex()); break
        i+=length
    elif main[i] in (0x67,0xe7): i+=14
    elif main[i]==0x0e: i+=4
    else: i+=2
print("falu2_uni:",uni)
if uni is None:
    print("MAIN:",main.hex()); sys.exit("no falu2_uni found")
off,length,hx=uni; b1=main[off+1]; b4=main[off+4]
print("op bytes=%s  byte+1=0x%02x (ureg=%d exp=%d) byte+4=0x%02x bit39=%d"%(hx,b1,b1>>1,b1>>4,b4,(b4>>7)&1))
loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
base=int(loc[0]); abs1=base+off+1; abs4=base+off+4
abuf=os.path.join(HERE,"u_a.bin"); open(abuf,"wb").write(struct.pack("<f",0.0))
def pbuf(vals):
    p=os.path.join(HERE,"u_p.bin"); open(p,"wb").write(b"".join(struct.pack("<f",v) for v in vals)); return p
allv=[1000.0+i for i in range(NU)]
pdef=pbuf(allv)
r=PersistRunner(source=kp,function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
# (A) runtime uniform check: vary p.f0
print("\n(A) runtime-uniform check (out should track bound p.f0):")
for v0 in [7.0,100.0,1000.0]:
    pv=pbuf([v0]+allv[1:])
    resp=r.request(archive=arch,grid=1,tg=1,ins={1:abuf,2:pv},outs={0:4},timeout=8)
    out=struct.unpack_from('<f',resp["outs"][0],0)[0] if resp["status"]=="OK" else None
    print("   p.f0=%-7s -> out=%s"%(v0,out))
# (C) sweep uniform index byte+1 (keep size bit)
print("\n(C) uniform-index sweep (byte+1); out = a(0) + uniform[idx]; decode idx=out-1000:")
size=b1&1; res={}
for ur in range(0,128):
    b1v=(ur<<1)|size
    spa=os.path.join(HERE,"u_sp.bin"); shutil.copyfile(arch,spa)
    with open(spa,"r+b") as f: f.seek(abs1); f.write(bytes([b1v]))
    resp=r.request(archive=spa,grid=1,tg=1,ins={1:abuf,2:pdef},outs={0:4},timeout=8)
    v=struct.unpack_from('<f',resp["outs"][0],0)[0] if resp["status"]=="OK" and 0 in resp["outs"] else None
    res[ur]=(resp["status"],b1v,v)
uni_hits={}
for ur in range(128):
    s,b1v,v=res[ur]
    tag=""
    if s=="OK" and v is not None and 1000<=v<1000+NU: uni_hits[ur]=int(v-1000); tag="=uniform[%d]"%int(v-1000)
    exp=b1v>>4
    print("   ur=%-3d byte1=0x%02x exp=%d %-10s out=%s %s"%(ur,b1v,exp,s,v,tag))
print("\ndistinct uniforms read:",sorted(set(uni_hits.values())))
print("max ur giving a uniform:",max(uni_hits) if uni_hits else None," count:",len(uni_hits))
# (D) select bit: clear bit39 on the original op
print("\n(D) clear bit39 (byte+4 bit7) -> uniform becomes GPR read?:")
spa=os.path.join(HERE,"u_sp.bin"); shutil.copyfile(arch,spa)
with open(spa,"r+b") as f: f.seek(abs4); f.write(bytes([b4 & 0x7f]))
resp=r.request(archive=spa,grid=1,tg=1,ins={1:abuf,2:pdef},outs={0:4},timeout=8)
v=struct.unpack_from('<f',resp["outs"][0],0)[0] if resp["status"]=="OK" and 0 in resp["outs"] else None
print("   bit39 cleared -> out=%s (uniform was 1000; if GPR read -> different/0)"%v)
r.close()
