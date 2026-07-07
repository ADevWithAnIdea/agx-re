#!/usr/bin/env python3
# sweep.py -- EXP-0006 field sweeper. Splices one byte (or bit-mask) of the
# falu2 ALU instruction across a value range, dispatches on the A18 Pro GPU with
# distinct known inputs, and classifies each output. Reveals operand roles
# (dst/srcA/srcB), the register-index encoding, field widths, and modifiers.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are spliced/executed.
import os, sys, argparse, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def load_mod(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
probe=load_mod("probe",os.path.join(HERE,"probe.py"))
analyze=load_mod("analyze",os.path.join(HERE,"analyze.py"))

# distinct, power-of-two inputs so sums/passthroughs are unambiguous
A=[1.0, 2.0, 4.0, 8.0]
B=[16.0, 32.0, 64.0, 128.0]

def cand():
    c={}
    c["a+b"]=[x+y for x,y in zip(A,B)]
    c["a-b"]=[x-y for x,y in zip(A,B)]
    c["b-a"]=[y-x for x,y in zip(A,B)]
    c["a*b"]=[x*y for x,y in zip(A,B)]
    c["a+a"]=[2*x for x in A]
    c["b+b"]=[2*y for y in B]
    c["a"]=list(A); c["b"]=list(B)
    c["-a"]=[-x for x in A]; c["-b"]=[-y for y in B]
    c["-(a+b)"]=[-(x+y) for x,y in zip(A,B)]
    c["zero"]=[0.0,0.0,0.0,0.0]
    return c

def classify(vals, tol=1e-3):
    if not vals: return "NOOUT"
    for name,exp in cand().items():
        if len(vals)==len(exp) and all(abs(x-y)<=tol*max(1,abs(y)) for x,y in zip(vals,exp)):
            return name
    return None

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",default="kernels/add.metal")
    ap.add_argument("--rel",type=lambda s:int(s,0),default=None,help="byte offset relative to ALU start to sweep")
    ap.add_argument("--which-alu",type=int,default=0)
    ap.add_argument("--lo",type=lambda s:int(s,0),default=0)
    ap.add_argument("--hi",type=lambda s:int(s,0),default=256)
    ap.add_argument("--timeout",type=float,default=5.0)
    ap.add_argument("--fast",action="store_true")
    ap.add_argument("--fixed",default="",help="comma list rel:val extra fixed splices")
    ap.add_argument("--out",default=None)
    args=ap.parse_args()

    p=probe.Probe(args.source, fast_math=args.fast)
    toks=analyze.structural_tokens(p.main)
    alus=[t for t in toks if t[0]=="ALU"]
    alu_off=alus[args.which_alu][1]; alu_bytes=alus[args.which_alu][3]
    print(f"# source={args.source} ALU@{alu_off:#x} bytes={alu_bytes.hex()} sweeping rel {args.rel:#x} (abs {alu_off+args.rel:#x})")
    print(f"# A={A} B={B}")
    fixed={}
    for kv in args.fixed.split(","):
        if not kv.strip(): continue
        r,v=kv.split(":"); fixed[alu_off+int(r,0)]=int(v,0)
    base=probe.f32  # noqa
    ins={0:A,1:B}
    out=open(args.out,"w") if args.out else None
    def emit(s):
        print(s)
        if out: out.write(s+"\n"); out.flush()
    emit(f"# sweep rel={args.rel:#x} abs={alu_off+args.rel:#x} baseALU={alu_bytes.hex()}")
    counts={}
    for v in range(args.lo,args.hi):
        ov=dict(fixed); ov[alu_off+args.rel]=v
        r=p.run(ov, ins, {2:4}, grid=4, timeout=args.timeout)
        st=r["_status"]
        if st!="OK":
            tag=f"FAULT:{st}"
            emit(f"{v:#04x}  {tag}")
        else:
            vals=r[2]; cls=classify(vals)
            tag=cls if cls else "OTHER"
            vs=" ".join(f"{x:g}" for x in vals)
            emit(f"{v:#04x}  OK  {tag:8s} [{vs}]  raw={r['_raw2']}")
        counts[tag]=counts.get(tag,0)+1
    emit("# SUMMARY: "+", ".join(f"{k}={counts[k]}" for k in sorted(counts)))
    p.close()

if __name__=="__main__": main()
