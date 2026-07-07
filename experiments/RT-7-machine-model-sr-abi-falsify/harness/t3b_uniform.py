#!/usr/bin/env python3
# RT-7 Task 3 (v2): uniform-source decode + count. For NU in {1,8,16,32,48,64,96}
# build out[gid]=a[gid]+p.f0 (struct of NU floats), report the add's encoding and
# whether it is falu2_uni (bit39 set, direct uniform src) or a uniform->GPR preload
# + plain add. Then, on a falu2_uni case, sweep the uniform index (byte+1) to count
# distinct uniform regs. Also verify runtime-uniform + the bit39 select.
# CLEAN-ROOM: OWN-SHADER + HW-PROBE.
import os, sys, subprocess, struct, importlib.util, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
sys.path.insert(0,HERE); from persistrun import PersistRunner

def build(NU,readfield=0):
    fields="".join("  float f%d;\n"%i for i in range(NU))
    src=("#include <metal_stdlib>\nusing namespace metal;\n"
         "struct P{\n%s};\n"%fields+
         "kernel void k(device float* out [[buffer(0)]], const device float* a [[buffer(1)]],\n"
         "              constant P& p [[buffer(2)]], uint gid [[thread_position_in_grid]]){ out[gid]=a[gid]+p.f%d; }\n"%readfield)
    kp=os.path.join(HERE,"kernels","uni%d.metal"%NU); open(kp,"w").write(src)
    arch=os.path.join(HERE,"uni%d.bin"%NU)
    subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
    return kp,arch

def find_fadd(main):
    # first 0x09 fadd (opsel 4) that is not part of store; report bytes
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

print("NU  add-bytes          bit39 byte1 exp uni_mov?  form")
forms={}
for NU in [1,8,16,32,48,64,96]:
    kp,arch=build(NU)
    buf=open(arch,"rb").read(); _,pieces=ap.extract_agx(buf); main=pieces["_agc.main"]
    cprog=pieces.get("_agc.main.constant_program",b"")
    fa=find_fadd(main)
    if not fa: print("%-3d  NO-FADD main=%s"%(NU,main.hex()[:40])); continue
    off,ln,by=fa; b1=by[1]; b4=by[4] if ln>4 else 0
    bit39=(b4>>7)&1; exp=b1>>4
    # uniform_mov (4B, Xb YY 01 08) in main?
    umov = any(main[i+2:i+4]==b"\x01\x08" and (main[i]&0x0f)==0x0b for i in range(0,len(main)-4))
    form="falu2_uni(direct)" if (bit39 and exp<8) else ("GPR-preload+add(uni_mov)" if umov else "plain/other")
    forms[NU]=(kp,arch,off,by,bit39,exp)
    print("%-3d  %-18s %-5d 0x%02x  %-3d %-8s %s"%(NU,by.hex(),bit39,b1,exp,umov,form))

# pick a falu2_uni NU to sweep the uniform index; else use NU=8 (RT-1a used 8)
target=None
for NU in [8,16,32,64,1]:
    if NU in forms and forms[NU][4] and (forms[NU][5]<8): target=NU; break
print("\nsweep target NU=",target)
if target:
    kp,arch,off,by,_,_=forms[target]
    loc=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","compute","--locate","_agc.main"],capture_output=True,text=True).stdout.split()
    abs1=int(loc[0])+off+1; size=by[1]&1
    abuf=os.path.join(HERE,"u_a.bin"); open(abuf,"wb").write(struct.pack("<f",0.0))
    vals=[1000.0+i for i in range(target)]
    pbuf=os.path.join(HERE,"u_p.bin"); open(pbuf,"wb").write(b"".join(struct.pack("<f",v) for v in vals))
    r=PersistRunner(source=kp,function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
    # runtime check
    print("runtime uniform check (vary bound p.f0):")
    for v0 in [7.0,100.0]:
        vv=[v0]+vals[1:]; open(pbuf,"wb").write(b"".join(struct.pack("<f",v) for v in vv))
        resp=r.request(archive=arch,grid=1,tg=1,ins={1:abuf,2:pbuf},outs={0:4},timeout=8)
        o=struct.unpack_from('<f',resp["outs"][0],0)[0] if resp["status"]=="OK" else None
        print("  p.f0=%s -> out=%s (a=0)"%(v0,o))
    open(pbuf,"wb").write(b"".join(struct.pack("<f",v) for v in vals))
    print("uniform-index sweep byte+1 -> out=uniform[idx], idx=out-1000:")
    hits={}
    for ur in range(0,80):
        b1v=(ur<<1)|size
        spa=os.path.join(HERE,"u_sp.bin"); shutil.copyfile(arch,spa)
        with open(spa,"r+b") as f: f.seek(abs1); f.write(bytes([b1v]))
        resp=r.request(archive=spa,grid=1,tg=1,ins={1:abuf,2:pbuf},outs={0:4},timeout=8)
        v=struct.unpack_from('<f',resp["outs"][0],0)[0] if resp["status"]=="OK" and 0 in resp["outs"] else None
        tag=""
        if v is not None and 1000<=v<1000+target: hits[ur]=int(v-1000); tag="=u[%d]"%int(v-1000)
        print("  ur=%-3d byte1=0x%02x exp=%d %-6s out=%s %s"%(ur,b1v,b1v>>4,resp["status"],v,tag))
    print("distinct uniforms:",sorted(set(hits.values())),"max ur:",max(hits) if hits else None)
    r.close()
