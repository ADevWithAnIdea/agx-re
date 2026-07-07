#!/usr/bin/env python3
# RT-7 Task 6: re-prove vertex-attribute fetch is IN-SHADER software by varying the
# MTLVertexDescriptor (stride/offset/format/step) and diffing the VS AGX bytes.
# If fetch were fixed-function, the VS code would NOT change; if in-shader, each
# knob moves specific VS bytes (load address / width / convert / index SR).
# CLEAN-ROOM: OWN-SHADER (our attrdump harness + our MSL).
import os, sys, subprocess, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
SRC=os.path.join(HERE,"kernels","attr_stagein.metal")
def extract_vs(arch):
    hx=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage","vertex","--extract-hex","--symbol","_agc.main"],capture_output=True,text=True).stdout.strip().replace(" ","").replace("\n","")
    return bytes.fromhex(hx) if hx else b""
def build(name,args):
    arch=os.path.join(HERE,"%s.bin"%name)
    cmd=[os.path.join(HERE,"attrdump"),"-o",arch,"--source",SRC,"--vertex","v_main","--fragment","f_main"]+args
    r=subprocess.run(cmd,capture_output=True,text=True)
    return arch,r.stderr.strip()
def diff(a,b):
    # byte-level diff regions
    n=max(len(a),len(b)); regs=[]; i=0
    while i<n:
        av=a[i] if i<len(a) else None; bv=b[i] if i<len(b) else None
        if av!=bv:
            j=i
            while j<n and ((a[j] if j<len(a) else None)!=(b[j] if j<len(b) else None)): j+=1
            regs.append((i,a[i:j].hex(),b[i:j].hex())); i=j
        else: i+=1
    return regs
BASE=["--fmt0","31","--off0","0","--fmt1","28","--off1","16","--stride","32","--nattr","2","--step","0"]
VARIANTS=[
 ("baseline",BASE),
 ("stride 32->64",["--fmt0","31","--off0","0","--fmt1","28","--off1","16","--stride","64","--nattr","2","--step","0"]),
 ("off1 16->12",["--fmt0","31","--off0","0","--fmt1","28","--off1","12","--stride","32","--nattr","2","--step","0"]),
 ("fmt0 float3->uchar4Norm(45)",["--fmt0","45","--off0","0","--fmt1","28","--off1","16","--stride","32","--nattr","2","--step","0"]),
 ("fmt1 float4->half4(25)",["--fmt0","31","--off0","0","--fmt1","25","--off1","16","--stride","32","--nattr","2","--step","0"]),
 ("step perVertex->perInstance",["--fmt0","31","--off0","0","--fmt1","28","--off1","16","--stride","32","--nattr","2","--step","1"]),
]
built={}
for name,args in VARIANTS:
    arch,err=build(name.split()[0],args)
    if not os.path.exists(arch): print("%-32s BUILD_FAIL %s"%(name,err[-100:])); continue
    built[name]=extract_vs(arch)
    print("%-32s VS_len=%d  %s"%(name,len(built[name]),err))
base=built.get("baseline",b"")
print("\n=== VS byte-diffs vs baseline (proves fetch params live IN the VS code) ===")
for name,_ in VARIANTS[1:]:
    if name not in built: continue
    regs=diff(base,built[name])
    print("%-32s -> %d changed region(s):"%(name,len(regs)))
    for off,a,b in regs[:8]:
        print("    @%-4d base=%s  variant=%s"%(off,a,b))
