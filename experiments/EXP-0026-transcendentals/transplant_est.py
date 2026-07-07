#!/usr/bin/env python3
# transplant_est.py -- EXP-0026 (runs ON DEVICE). Cleanly isolate the raw 0x29
# ESTIMATE by transplanting the 6-byte estimate op into a simple carrier kernel
# (out=a*a: load a->Rx, <op> ->Ry, store Ry) that has NO Newton-Raphson
# refinement, so the estimate output register stays live. The carrier's load is
# byte-identical to the transcendental kernels' load, so the transplanted
# estimate (byte+1 srcA descriptor unchanged) reads the same x. We then sweep the
# store's data-source register to find where the coarse estimate lands and read
# it back for many x -> mantissa-bit precision.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are spliced/executed.
import os, sys, math, struct, importlib.util, subprocess
HERE=os.path.dirname(os.path.abspath(__file__))
def lm(n,p):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse=lm("agxparse",os.path.join(HERE,"agxparse.py"))
persistrun=lm("persistrun",os.path.join(HERE,"persistrun.py"))
WORK="work"; os.makedirs(WORK,exist_ok=True)

SUBOP={"rcp":0x09,"rsqrt":0x0b,"sqrt":0x0d}
REF={"rcp":lambda x:1.0/x,"rsqrt":lambda x:1.0/math.sqrt(x),"sqrt":lambda x:math.sqrt(x)}

def build(src):
    out=os.path.join(WORK,"sq.bin")
    r=subprocess.run(["./shdump","-o",out,"-f","k","--no-fast-math",src],capture_output=True,text=True)
    if r.returncode: raise RuntimeError(r.stderr)
    with open(out,"rb") as f: return out,f.read()

def f32(raw,i): return struct.unpack_from("<f",raw,i*4)[0]

def main():
    name=sys.argv[1] if len(sys.argv)>1 else "rcp"
    subop=SUBOP[name]
    _,buf=build("kernels/sq.metal")
    off,_=agxparse.locate_region(buf,"_agc.main")
    _,pieces=agxparse.extract_agx(buf); main_b=pieces["_agc.main"]
    # carrier layout: get_sr(4) load(14) ALU(6) store(14) stop(4)
    # find the ALU op (first op after the load block that is not 0x67/0xe7/0x0e)
    o=0
    if (main_b[0]&0x0f)==0x0c: o=4
    while o<len(main_b) and main_b[o]==0x67: o+=14
    alu_rel=o
    store_rel=max(i for i in range(len(main_b)) if main_b[i]==0xe7)
    print(f"carrier sq: mainlen={len(main_b)} alu@{alu_rel:#x}({main_b[alu_rel:alu_rel+6].hex()}) store@{store_rel:#x}")
    est_bytes=bytes([0x29,0x81,0x25,subop,0x00,0xc2])
    # transplant estimate op over the 6-byte ALU
    base=bytearray(buf)
    base[off+alu_rel:off+alu_rel+6]=est_bytes
    src_byte_abs=off+store_rel+8
    xin=[1.3,1.7,2.3,3.0,5.0,7.0,11.0,13.0]
    inpath=os.path.join(WORK,"xin.bin")
    with open(inpath,"wb") as f: f.write(b"".join(struct.pack("<f",v) for v in xin))
    R=persistrun.PersistRunner(source="kernels/sq.metal",function="k",fast_math=False,agxrun_persist="./agxrun_persist")
    ref=[REF[name](x) for x in xin]
    print(f"  transplanted estimate op {est_bytes.hex()} ; ref f(x)={[round(r,5) for r in ref]}")
    est_reg=None
    for reg in range(0,32):
        b=bytearray(base); b[src_byte_abs]=(reg<<1)|1
        sp=os.path.join(WORK,"sp.bin")
        with open(sp,"wb") as f: f.write(bytes(b))
        resp=R.request(archive=sp,grid=len(xin),tg=len(xin),ins={0:inpath},outs={1:len(xin)*4},timeout=8)
        if resp["status"]!="OK": continue
        raw=resp["outs"].get(1,b"")
        vals=[f32(raw,k) for k in range(len(xin))]
        errs=[abs(v-r)/abs(r) for v,r in zip(vals,ref) if r and math.isfinite(v)]
        if len(errs)==len(ref) and max(errs)<0.05:
            print(f"  reg{reg:2d}: "+" ".join(f"{v:.6g}" for v in vals)+f"  maxrel={max(errs):.3e} ~{-math.log2(max(errs)):.1f} bits  <== ESTIMATE")
            if est_reg is None: est_reg=reg
        else:
            m=max(errs) if errs else float('inf')
            print(f"  reg{reg:2d}: "+" ".join(f"{v:.5g}" for v in vals)+f"  maxrel={m:.2e}")
    if est_reg is None:
        print("  no estimate register found"); R.close(); return
    # dense sweep across the mantissa period to get worst-case precision
    descr=(est_reg<<1)|1
    N=64
    if name=="rcp": xs=[1.0+1.0*k/N for k in range(N)]
    else: xs=[1.0+3.0*k/N for k in range(N)]   # [1,4) spans one exponent period for sqrt-family
    worst=0.0; wx=None
    xp=os.path.join(WORK,"dense.bin")
    with open(xp,"wb") as f: f.write(b"".join(struct.pack("<f",x) for x in xs))
    b=bytearray(base); b[src_byte_abs]=descr
    sp=os.path.join(WORK,"sp.bin")
    with open(sp,"wb") as f: f.write(bytes(b))
    resp=R.request(archive=sp,grid=len(xs),tg=min(len(xs),256),ins={0:xp},outs={1:len(xs)*4},timeout=10)
    if resp["status"]=="OK":
        raw=resp["outs"][1]
        for k,x in enumerate(xs):
            v=f32(raw,k); r=REF[name](x)
            if not math.isfinite(v) or v==0: continue
            e=abs(v-r)/abs(r)
            if e>worst: worst=e; wx=x
        print(f"\n  DENSE sweep on reg{est_reg} ({len(xs)} pts over one period):")
        print(f"    WORST-CASE relerr={worst:.4e} at x={wx:.4f} -> ~{-math.log2(worst):.2f} good mantissa bits")
    R.close()

if __name__=="__main__":
    main()
