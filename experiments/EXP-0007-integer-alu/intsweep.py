#!/usr/bin/env python3
# intsweep.py -- EXP-0007 field sweeper for the integer ALU. Splices one byte of
# a chosen kernel's ALU instruction across a value range, dispatches on the A18
# Pro GPU with distinct known int inputs, and classifies each output against a
# bank of candidate integer operations. Reveals op-select + operand fields.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are spliced/executed.
import os, sys, argparse, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
intprobe = lm("intprobe", os.path.join(HERE, "intprobe.py"))

M = 0xffffffff
def s32(x):
    x &= M
    return x - (1 << 32) if x & 0x80000000 else x

# distinct inputs so most integer ops give unique outputs
A = [12, 20, 7, 100]
B = [3, 6, 5, 8]

def cands(A, B):
    c = {}
    c["a+b"]  = [s32(a+b) for a,b in zip(A,B)]
    c["a-b"]  = [s32(a-b) for a,b in zip(A,B)]
    c["b-a"]  = [s32(b-a) for a,b in zip(A,B)]
    c["a*b"]  = [s32(a*b) for a,b in zip(A,B)]
    c["a&b"]  = [s32(a&b) for a,b in zip(A,B)]
    c["a|b"]  = [s32(a|b) for a,b in zip(A,B)]
    c["a^b"]  = [s32(a^b) for a,b in zip(A,B)]
    c["min"]  = [min(a,b) for a,b in zip(A,B)]
    c["max"]  = [max(a,b) for a,b in zip(A,B)]
    c["a<<b"] = [s32((a << (b & 31))) for a,b in zip(A,B)]
    c["a>>b"] = [s32(a >> (b & 31)) for a,b in zip(A,B)]
    c["a"]    = [s32(a) for a in A]
    c["b"]    = [s32(b) for b in B]
    c["~a"]   = [s32(~a) for a in A]
    c["~b"]   = [s32(~b) for b in B]
    c["a+a"]  = [s32(a+a) for a in A]
    c["b+b"]  = [s32(b+b) for b in B]
    c["-a"]   = [s32(-a) for a in A]
    c["-b"]   = [s32(-b) for b in B]
    c["zero"] = [0,0,0,0]
    c["not(a&b)"] = [s32(~(a&b)) for a,b in zip(A,B)]
    c["not(a|b)"] = [s32(~(a|b)) for a,b in zip(A,B)]
    c["not(a^b)"] = [s32(~(a^b)) for a,b in zip(A,B)]
    return c

def classify(vals, A, B):
    if not vals: return "NOOUT"
    for name, exp in cands(A, B).items():
        if len(vals) == len(exp) and all(x == y for x,y in zip(vals, exp)):
            return name
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="kernels/iadd.metal")
    ap.add_argument("--rel", type=lambda s: int(s,0), required=True, help="byte offset within ALU to sweep")
    ap.add_argument("--which-alu", type=int, default=0)
    ap.add_argument("--lo", type=lambda s: int(s,0), default=0)
    ap.add_argument("--hi", type=lambda s: int(s,0), default=256)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--fixed", default="", help="comma list rel:val extra fixed splices")
    ap.add_argument("--nin", type=int, default=2, help="1 for a+imm kernels (only buffer 0)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    p = intprobe.IntProbe(args.source, fast_math=args.fast)
    alu_off, alu_bytes = p.alu(args.which_alu)
    fixed = {}
    for kv in args.fixed.split(","):
        if not kv.strip(): continue
        r, v = kv.split(":"); fixed[alu_off + int(r,0)] = int(v,0)
    ins = {0: A, 1: B} if args.nin == 2 else {0: A}
    outidx = 2 if args.nin == 2 else 1
    out = open(args.out, "w") if args.out else None
    def emit(s):
        print(s)
        if out: out.write(s + "\n"); out.flush()
    emit(f"# source={args.source} ALU@{alu_off:#x} len={len(alu_bytes)} bytes={alu_bytes.hex()}")
    emit(f"# sweeping rel={args.rel:#x} (abs {alu_off+args.rel:#x})  A={A} B={B}  fixed={args.fixed}")
    counts = {}
    for v in range(args.lo, args.hi):
        ov = dict(fixed); ov[alu_off + args.rel] = v
        r = p.run(ov, ins, {outidx: 4}, grid=4, timeout=args.timeout)
        st = r["_status"]
        if st != "OK":
            tag = f"FAULT:{st}"; emit(f"{v:#04x}  {tag}")
        else:
            vals = r[outidx]; cls = classify(vals, A, B)
            tag = cls if cls else "OTHER"
            vs = " ".join(str(x) for x in vals)
            emit(f"{v:#04x}  OK  {tag:10s} [{vs}]  raw={r['_raw'+str(outidx)]}")
        counts[tag] = counts.get(tag, 0) + 1
    emit("# SUMMARY: " + ", ".join(f"{k}={counts[k]}" for k in sorted(counts)))
    p.close()

if __name__ == "__main__":
    main()
