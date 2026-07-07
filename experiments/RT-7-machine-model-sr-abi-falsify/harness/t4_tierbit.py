#!/usr/bin/env python3
# RT-7 Task 4: falsify the occupancy tier bit (launch +0x00 bit23 flips at ~12 GPRs).
# Build kernels hitting target f0 in {8,11,12,14,20}, run each under iotrace (SIGUSR1
# dump via cfgcap), scan captured BOs for the launch-descriptor config word
# (0x00080000 clear / 0x00880000 set, from EXP-0020), and report bit23 vs f0.
# CLEAN-ROOM: OWN-SHADER + DATA-TRACE.
import os, sys, subprocess, struct, importlib.util, glob, shutil
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

def kern(K,ty):
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device %s* out [[buffer(0)]], device const %s* in [[buffer(1)]], constant uint& n [[buffer(2)]], uint gid [[thread_position_in_grid]]) {"%(ty,ty)]
    for k in range(K): L.append("  %s a%d = in[gid*%d+%d];"%(ty,k,K,k))
    L.append("  for(uint i=1;i<n;i++){ %s t=in[i];"%ty)
    for k in range(K): L.append("    a%d=a%d*t+a%d;"%(k,k,(k+1)%K))
    L.append("  }")
    for k in range(K): L.append("  out[gid*%d+%d]=a%d;"%(K,k,k))
    L.append("}")
    return "\n".join(L)+"\n"

def gpu(buf):
    for off,size,note in ap.iter_gpu_images(buf):
        try: mo=ap.MachO(buf,off)
        except ValueError: continue
        if mo.cputype==ap.APPLE_GPU_CPUTYPE: return mo
def tf(buf,tp):
    so=struct.unpack_from('<i',buf,tp)[0]; vt=tp-so; nf=(struct.unpack_from('<H',buf,vt)[0]-4)//2; f={}
    for i in range(nf):
        fo=struct.unpack_from('<H',buf,vt+4+i*2)[0]
        if fo: f[i]=tp+fo
    return f
def f0_of(arch):
    buf=open(arch,"rb").read(); mo=gpu(buf)
    s=mo.find_section("__TEXT","__compute"); nb=mo.base+s["offset"]; nm=ap.MachO(buf,nb); meta=None
    for sec in nm.sections:
        if sec["seg"]=="__GPU_METADATA": o=nb+sec["offset"]; meta=bytes(buf[o:o+sec["size"]])
    root=struct.unpack_from('<I',meta,0)[0]; rf=tf(meta,root); sub=rf[0]+struct.unpack_from('<I',meta,rf[0])[0]; ff=tf(meta,sub)
    return struct.unpack_from('<I',meta,ff[0])[0] if 0 in ff else -1

def build_target(f0target):
    # search K over both types for an exact f0 match
    for ty in ("half","float"):
        for K in range(2,40):
            src=kern(K,ty); kp=os.path.join(HERE,"kernels","cf_%s%d.metal"%(ty,K)); open(kp,"w").write(src)
            arch=os.path.join(HERE,"cf_%s%d.bin"%(ty,K))
            subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
            if not os.path.exists(arch): continue
            if f0_of(arch)==f0target: return kp,arch,ty,K
    return None,None,None,None

def capture(kp,tag):
    dump=os.path.join(HERE,"cap_%s"%tag)
    shutil.rmtree(dump,ignore_errors=True)
    env=dict(os.environ, IOTRACE_DUMP_ON_USR1="1", IOTRACE_DUMP_DIR=dump,
             DYLD_INSERT_LIBRARIES=os.path.join(HERE,"iotrace.dylib"),
             IOTRACE_LOG=os.path.join(HERE,"cap_%s.log"%tag))
    subprocess.run([os.path.join(HERE,"cfgcap"),kp],env=env,capture_output=True,timeout=60)
    # scan every dumped hex BO for the config word candidates
    found=[]
    for hx in glob.glob(os.path.join(dump,"*.hex")):
        data=open(hx).read().split()
        # hex files store space/line separated hex bytes? read raw
    # robust: read files as raw hex text -> bytes
    words=set()
    for hxf in glob.glob(os.path.join(dump,"*.hex")):
        txt=open(hxf).read().strip().replace("\n","").replace(" ","")
        try: b=bytes.fromhex(txt)
        except: continue
        for off in range(0,len(b)-3):
            w=struct.unpack_from('<I',b,off)[0]
            if w in (0x00080000,0x00880000,0x00080001,0x00880001): words.add((os.path.basename(hxf)[:24],off,w))
    return dump,sorted(words,key=lambda x:x[2])

if __name__=="__main__":
    targets=[int(x) for x in sys.argv[1:]] if len(sys.argv)>1 else [8,11,12,14,20]
    print("building cfgcap dispatcher...")
    r=subprocess.run(["clang","-fobjc-arc","-framework","Metal","-framework","Foundation","-o",os.path.join(HERE,"cfgcap"),os.path.join(HERE,"cfgcap.m")],capture_output=True,text=True)
    if not os.path.exists(os.path.join(HERE,"cfgcap")): print("cfgcap build fail:",r.stderr[-300:]); sys.exit(1)
    print("%-6s %-14s %-8s %s"%("f0","kernel","bit23","config words found (BO,off,val)"))
    for f0t in targets:
        kp,arch,ty,K=build_target(f0t)
        if not kp: print("%-6d NO-KERNEL-FOUND"%f0t); continue
        dump,words=capture(kp,"f%d"%f0t)
        vals=set(w for _,_,w in words)
        set23 = any((w>>23)&1 for w in vals)
        clr = any(not ((w>>23)&1) for w in vals)
        bit="SET(1)" if (set23 and not clr) else ("CLEAR(0)" if (clr and not set23) else ("MIXED" if words else "none"))
        print("%-6d %-14s %-8s %s"%(f0t,"%s K=%d"%(ty,K),bit,[(w[0],w[1],hex(w[2])) for w in words[:4]]))
