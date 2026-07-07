#!/usr/bin/env python3
# est_precision.py -- EXP-0026 (runs ON DEVICE). Measure the raw 0x29 ESTIMATE
# precision. Method: in the PRECISE kernel, redirect the final device_store to
# read the register that (under multi-lane dispatch) holds the pre-refinement
# estimate, auto-detecting both the register and the constant lane-shift, then
# run a DENSE multi-lane sweep over one mantissa period and report the worst-case
# relative error -> good mantissa bits.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are spliced/executed.
import os, sys, math, struct, importlib.util, subprocess
HERE=os.path.dirname(os.path.abspath(__file__))
def lm(n,p):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse=lm("agxparse",os.path.join(HERE,"agxparse.py"))
persistrun=lm("persistrun",os.path.join(HERE,"persistrun.py"))
WORK="work"; os.makedirs(WORK,exist_ok=True)
REF={"rcp":lambda x:1.0/x,"rsqrt":lambda x:1.0/math.sqrt(x),"sqrt":lambda x:math.sqrt(x)}

def build(src):
    out=os.path.join(WORK,"base.bin")
    r=subprocess.run(["./shdump","-o",out,"-f","k","--no-fast-math",src],capture_output=True,text=True)
    if r.returncode: raise RuntimeError(r.stderr)
    with open(out,"rb") as f: return out,f.read()
def f32(raw,i): return struct.unpack_from("<f",raw,i*4)[0]

def run(R, base, src_byte_abs, descr, xs, inpath):
    b=bytearray(base); b[src_byte_abs]=descr
    sp=os.path.join(WORK,"sp.bin")
    with open(sp,"wb") as f: f.write(bytes(b))
    resp=R.request(archive=sp,grid=len(xs),tg=min(len(xs),256),ins={0:inpath},outs={1:len(xs)*4},timeout=10)
    if resp["status"]!="OK": return None
    raw=resp["outs"].get(1,b"")
    return [f32(raw,k) for k in range(len(xs))]

def worst_match(vals, xs, ref):
    # match each finite nonzero output to the nearest reference value over the
    # grid, return worst-case relative error (nearest-neighbour; shift-agnostic)
    worst=0.0; wx=None; nmatched=0
    for v in vals:
        if not math.isfinite(v) or v==0: continue
        best=None
        for x,r in zip(xs,ref):
            e=abs(v-r)/abs(r)
            if best is None or e<best[0]: best=(e,x)
        if best[0]<0.05:
            nmatched+=1
            if best[0]>worst: worst=best[0]; wx=best[1]
    return worst,wx,nmatched

def main():
    name=sys.argv[1] if len(sys.argv)>1 else "rcp"
    _,buf=build(f"kernels/{name}.metal")
    off,_=agxparse.locate_region(buf,"_agc.main")
    _,pieces=agxparse.extract_agx(buf); main_b=pieces["_agc.main"]
    store_rel=max(i for i in range(len(main_b)) if main_b[i]==0xe7)
    src_byte_abs=off+store_rel+8
    # coarse probe: distinct x per lane, find the register giving coarse f(x)
    xin=[2.0,3.0,4.0,5.0,7.0,9.0,16.0,100.0]
    ip=os.path.join(WORK,"xin.bin")
    with open(ip,"wb") as f: f.write(b"".join(struct.pack("<f",v) for v in xin))
    ref8=[REF[name](x) for x in xin]
    R=persistrun.PersistRunner(source=f"kernels/{name}.metal",function="k",fast_math=False,agxrun_persist="./agxrun_persist")
    est_reg=None; best_matched=0
    for reg in range(0,32):
        vals=run(R,buf,src_byte_abs,(reg<<1)|1,xin,ip)
        if not vals: continue
        w,wx,nm=worst_match(vals,xin,ref8)
        if nm>=6 and w<0.02 and w>1e-4:   # a coarse (not exact, not garbage) f(x)
            if nm>best_matched: best_matched=nm; est_reg=reg
    if est_reg is None:
        print(f"{name}: no coarse-estimate register found"); R.close(); return
    descr=(est_reg<<1)|1
    # dense sweep over one mantissa period
    N=96
    if name=="rcp": xs=[1.0+1.0*k/N for k in range(1,N)]
    else:           xs=[1.0+3.0*k/N for k in range(1,N)]
    ref=[REF[name](x) for x in xs]
    with open(ip,"wb") as f: f.write(b"".join(struct.pack("<f",v) for v in xs))
    vals=run(R,buf,src_byte_abs,descr,xs,ip)
    w,wx,nm=worst_match(vals,xs,ref)
    print(f"=== {name}: raw estimate in reg{est_reg} (store byte+8 descr {descr:#04x}) ===")
    print(f"    dense sweep {nm}/{len(xs)} lanes matched a coarse {name}(x)")
    print(f"    WORST-CASE relerr = {w:.4e} at x~{wx:.4f}  ->  ~{-math.log2(w):.2f} good mantissa bits")
    # a few sample (value, nearest-ref) pairs
    shown=0
    for v in vals:
        if shown>=6 or not math.isfinite(v) or v==0: continue
        best=min(((abs(v-r)/abs(r),x,r) for x,r in zip(xs,ref)),key=lambda t:t[0])
        if best[0]<0.05:
            print(f"      est={v:.7g}  ~ {name}({best[1]:.4f})={best[2]:.7g}  relerr={best[0]:.3e}")
            shown+=1
    R.close()

if __name__=="__main__":
    for nm in (sys.argv[1:] or ["rcp","rsqrt","sqrt"]):
        main.__globals__  # noop
        sys.argv=[sys.argv[0],nm]; main()
