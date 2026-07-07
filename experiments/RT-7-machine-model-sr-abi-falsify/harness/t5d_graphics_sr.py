#!/usr/bin/env python3
# RT-7 Task 5: (1) confirm threadgroups_per_grid real builtin computes grid/tg
# end-to-end; (2) read off graphics-stage get_sr codes (vertex_id/instance_id in
# VS; front_facing/simd_is_helper in FS) via shdump --render.
# CLEAN-ROOM: OWN-SHADER + HW-PROBE.
import os, sys, subprocess, struct, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
spec=importlib.util.spec_from_file_location("ap",os.path.join(HERE,"agxparse.py")); ap=importlib.util.module_from_spec(spec); spec.loader.exec_module(ap)
sys.path.insert(0,HERE); from persistrun import PersistRunner

def find_getsr(main):
    hits=[];i=0;n=len(main)
    while i+4<=n:
        if (main[i]&0x07)==0x04 and main[i+2]==0x10 and main[i+3]==0x06:
            hits.append((main[i],main[i+1])); i+=4; continue
        if main[i] in (0x67,0xe7): i+=14
        elif main[i]==0x0e: i+=4
        else: i+=2
    return hits

# ---- (1) real threadgroups_per_grid builtin end-to-end ----
print("=== (1) real builtins end-to-end (compute) ===")
for attr,name in [("threadgroups_per_grid","threadgroups_per_grid.x"),("threads_per_threadgroup","threads_per_threadgroup.x")]:
    src=("#include <metal_stdlib>\nusing namespace metal;\n"
         "kernel void k(device uint* out [[buffer(0)]], uint3 v [[%s]], uint3 g [[thread_position_in_grid]]) { out[g.x]=v.x; }\n"%attr)
    kp=os.path.join(HERE,"kernels","tgpg_real.metal"); open(kp,"w").write(src)
    arch=os.path.join(HERE,"tgpg_real.bin")
    subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"-f","k","--no-fast-math",kp],capture_output=True)
    r=PersistRunner(source=kp,function="k",fast_math=False,agxrun_persist=os.path.join(HERE,"agxrun_persist"))
    for grid,tg in [(256,64),(192,64),(128,32)]:
        resp=r.request(archive=arch,grid=grid,tg=tg,ins={},outs={0:grid*4},timeout=8)
        v0=struct.unpack_from('<I',resp["outs"][0],0)[0] if resp["status"]=="OK" else None
        print("  %-26s grid=%-4d tg=%-3d -> %s   (grid/tg=%d, tg=%d)"%(name,grid,tg,v0,grid//tg,tg))
    r.close()

# ---- (2) graphics stage get_sr read-off ----
print("\n=== (2) graphics get_sr codes (read-off) ===")
GRAPHICS=[
 # (name, MSL, vfn, ffn, stage_to_scan, doc_code)
 ("vertex_id",
  "#include <metal_stdlib>\nusing namespace metal;\n"
  "struct VO{float4 p [[position]]; float v;};\n"
  "vertex VO vmain(uint vid [[vertex_id]]){VO o; o.p=float4(0,0,0,1); o.v=as_type<float>(vid); return o;}\n"
  "fragment float4 fmain(VO i){return float4(i.v,0,0,1);}\n","vmain","fmain","vertex",0xdd),
 ("instance_id",
  "#include <metal_stdlib>\nusing namespace metal;\n"
  "struct VO{float4 p [[position]]; float v;};\n"
  "vertex VO vmain(uint iid [[instance_id]]){VO o; o.p=float4(0,0,0,1); o.v=as_type<float>(iid); return o;}\n"
  "fragment float4 fmain(VO i){return float4(i.v,0,0,1);}\n","vmain","fmain","vertex",0xd8),
 ("front_facing",
  "#include <metal_stdlib>\nusing namespace metal;\n"
  "struct VO{float4 p [[position]];};\n"
  "vertex VO vmain(uint vid [[vertex_id]]){VO o; o.p=float4(0,0,0,1); return o;}\n"
  "fragment float4 fmain(bool ff [[front_facing]]){return float4(ff?1.0:0.0,0,0,1);}\n","vmain","fmain","fragment",0xc5),
 ("simd_is_helper_thread",
  "#include <metal_stdlib>\nusing namespace metal;\n"
  "struct VO{float4 p [[position]];};\n"
  "vertex VO vmain(uint vid [[vertex_id]]){VO o; o.p=float4(0,0,0,1); return o;}\n"
  "fragment float4 fmain(bool h [[simd_is_helper_thread]]){return float4(h?1.0:0.0,0,0,1);}\n","vmain","fmain","fragment",0x84),
]
for name,msl,vfn,ffn,stage,doc in GRAPHICS:
    kp=os.path.join(HERE,"kernels","g_%s.metal"%name); open(kp,"w").write(msl)
    arch=os.path.join(HERE,"g_%s.bin"%name)
    r=subprocess.run([os.path.join(HERE,"shdump"),"-o",arch,"--render","--vertex",vfn,"--fragment",ffn,kp],capture_output=True,text=True)
    if not os.path.exists(arch): print("  %-24s COMPILE_FAIL %s"%(name,r.stderr[-120:])); continue
    hx=subprocess.run(["python3",os.path.join(HERE,"agxparse.py"),arch,"--stage",stage,"--extract-hex","--symbol","_agc.main"],capture_output=True,text=True).stdout.strip().replace(" ","").replace("\n","")
    main=bytes.fromhex(hx)
    codes=[c[1] for c in find_getsr(main)]
    obs=",".join("0x%02x"%c for c in codes) if codes else "none"
    verdict="CONFIRM" if doc in codes else (">>> doc 0x%02x NOT in observed"%doc)
    print("  %-24s stage=%-8s doc=0x%02x obs=[%s]  %s"%(name,stage,doc,obs,verdict))
