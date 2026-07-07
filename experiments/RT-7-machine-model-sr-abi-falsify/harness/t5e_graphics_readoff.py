#!/usr/bin/env python3
# RT-7 Task 5 graphics get_sr read-off (fixed MSL + relaxed get_sr scan that prints
# EVERY get_sr-group op with its byte1/byte2/byte3 so no code is missed by a suffix filter).
# CLEAN-ROOM: OWN-SHADER.
import os, sys, subprocess, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)

def all_getsr(main):
    # get_sr group = byte0 bits[0:3]==0b100 AND byte3==0x06 (suffix hi byte) -> print full
    hits=[];i=0;n=len(main)
    while i+4<=n:
        if (main[i]&0x07)==0x04 and main[i+3]==0x06 and main[i+2] in (0x10,0x11,0x00,0x08,0x09,0x26,0x27):
            hits.append((i,main[i],main[i+1],main[i+2],main[i+3])); i+=4; continue
        if main[i] in (0x67,0xe7): i+=14
        elif main[i]==0x0e: i+=4
        else: i+=2
    return hits

GRAPHICS=[
 ("vertex_id",
  "#include <metal_stdlib>\nusing namespace metal;\n"
  "struct VO{float4 p [[position]]; float4 c [[user(locn0)]];};\n"
  "vertex VO vmain(uint vid [[vertex_id]]){VO o; o.p=float4(0,0,0,1); o.c=float4(vid,0,0,0); return o;}\n"
  "fragment float4 fmain(VO i [[stage_in]]){return i.c;}\n","vmain","fmain","vertex",0xdd),
 ("instance_id",
  "#include <metal_stdlib>\nusing namespace metal;\n"
  "struct VO{float4 p [[position]]; float4 c [[user(locn0)]];};\n"
  "vertex VO vmain(uint iid [[instance_id]]){VO o; o.p=float4(0,0,0,1); o.c=float4(iid,0,0,0); return o;}\n"
  "fragment float4 fmain(VO i [[stage_in]]){return i.c;}\n","vmain","fmain","vertex",0xd8),
 ("front_facing",
  "#include <metal_stdlib>\nusing namespace metal;\n"
  "struct VO{float4 p [[position]];};\n"
  "vertex VO vmain(uint vid [[vertex_id]]){VO o; o.p=float4(0,0,0,1); return o;}\n"
  "fragment float4 fmain(bool ff [[front_facing]]){return float4(ff?1.0:0.0,0,0,1);}\n","vmain","fmain","fragment",0xc5),
 ("simd_is_helper_thread",
  "#include <metal_stdlib>\nusing namespace metal;\n"
  "struct VO{float4 p [[position]];};\n"
  "vertex VO vmain(uint vid [[vertex_id]]){VO o; o.p=float4(0,0,0,1); return o;}\n"
  "fragment float4 fmain(){float h = simd_is_helper_thread()?1.0:0.0; return float4(h,0,0,1);}\n","vmain","fmain","fragment",0x84),
]
for name,msl,vfn,ffn,stage,doc in GRAPHICS:
    kp=os.path.join(HERE,"kernels","g2_%s.metal"%name); open(kp,"w").write(msl)
    arch=os.path.join(HERE,"g2_%s.bin"%name)
    r=subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"--render","--vertex",vfn,"--fragment",ffn,kp],capture_output=True,text=True)
    if not os.path.exists(arch): print("%-24s COMPILE_FAIL %s"%(name,r.stderr.strip()[-160:])); continue
    hx=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage",stage,"--extract-hex","--symbol","_agc.main"],capture_output=True,text=True).stdout.strip().replace(" ","").replace("\n","")
    main=bytes.fromhex(hx)
    hits=all_getsr(main)
    obs=[(h[0],"b0=0x%02x b1=0x%02x b2=0x%02x"%(h[1],h[2],h[3])) for h in hits]
    codes=[h[2] for h in hits]
    verdict="CONFIRM (0x%02x present)"%doc if doc in codes else ">>> doc 0x%02x NOT found; all get_sr b1=%s"%(doc,[hex(c) for c in codes])
    print("%-24s stage=%-8s doc=0x%02x  %s"%(name,stage,doc,verdict))
    for o in obs: print("      get_sr off=%-4d %s"%o)
    print("      MAIN[:64]=",main[:64].hex())
