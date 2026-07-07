#!/usr/bin/env python3
# intval.py -- EXP-0007 targeted HW splice-and-observe validations for the
# integer ALU: integer immediate encoding, add<->sub negate, min/max signedness,
# the 10/12-byte length bit, and dst relocation.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are spliced/executed.
import os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
intprobe = lm("intprobe", os.path.join(HERE, "intprobe.py"))
M = 0xffffffff
def s32(x):
    x &= M; return x - (1<<32) if x & 0x80000000 else x

def imm_tests():
    print("\n===== INTEGER IMMEDIATE: splice (K<<1) into b5:b6 of a+imm form =====")
    p = intprobe.IntProbe("kernels/addimm5.metal")
    off, b = p.alu(); print(f"base a+5 ALU@{off:#x} = {b.hex()}  (b5={b[5]:#x}=5<<1)")
    A = [1000, 2000, 3000, 4000]
    ok_all = True
    for K in [0,1,2,5,7,15,16,31,63,64,100,127,128,200,255,256,511,512,1000,4095,
              -1,-2,-5,-100,-255,-256]:
        field = (K << 1) & 0xffff   # candidate: value = imm<<1 (bit0 flag=0)
        b5 = field & 0xff; b6 = (field >> 8) & 0xff
        r = p.run({off+5: b5, off+6: b6}, {0: A}, {1: 4}, grid=4)
        exp = [s32(a+K) for a in A]
        ok = r.get(1) == exp
        ok_all &= ok
        print(f"  K={K:>6}  b5:b6={b5:#04x}:{b6:#04x}  out={r.get(1)}  exp={exp}  {'PASS' if ok else 'FAIL'}  st={r['_status']}")
    p.close(); print(f"  IMMEDIATE (imm<<1) {'ALL PASS' if ok_all else 'some FAIL'}")

def negate_tests():
    print("\n===== ADD<->SUB: locate the negate that turns a+b into a-b/b-a =====")
    p = intprobe.IntProbe("kernels/iadd.metal")
    off, b = p.alu(); print(f"iadd ALU = {b.hex()}")
    A = [10,10,-10,-10]; B = [3,-3,3,-3]
    base = p.run({}, {0:A,1:B}, {2:4}, grid=4)
    print(f"  base a+b        out={base.get(2)}  exp {[s32(a+bb) for a,bb in zip(A,B)]}")
    # b0 bit7 clear (0x9f->0x1f) observed to give b-a (negate srcA). Confirm with signed.
    r = p.run({off: b[0] & 0x7f}, {0:A,1:B}, {2:4}, grid=4)
    exp_ba = [s32(bb-a) for a,bb in zip(A,B)]
    print(f"  b0&0x7f (0x1f)  out={r.get(2)}  exp b-a {exp_ba}  {'PASS' if r.get(2)==exp_ba else 'FAIL'}")
    # try the exact isub encoding's extra bits (b5 clear 0x08->0x00, b6 set 0x00->0x10) -> a-b
    r2 = p.run({off: b[0] & 0x7f, off+5: b[5] & ~0x08 & 0xff, off+6: b[6] | 0x10},
               {0:A,1:B}, {2:4}, grid=4)
    exp_ab = [s32(a-bb) for a,bb in zip(A,B)]
    print(f"  isub-form       out={r2.get(2)}  exp a-b {exp_ab}  {'PASS' if r2.get(2)==exp_ab else 'FAIL'}")
    p.close()

def signed_tests():
    print("\n===== MIN/MAX signedness (0x02 group b4 sel bit1) =====")
    # signed vs unsigned differ only when sign bits differ
    A = [-5, 100, -1, 7]; B = [3, -6, 2, -8]
    def us(x): return x & M
    for kern, sel_name in [("imin","signed min b4=0x07"), ("umin","unsigned min b4=0x05"),
                           ("imax","signed max b4=0x06"), ("umax","unsigned max b4=0x04")]:
        p = intprobe.IntProbe(f"kernels/{kern}.metal")
        off, b = p.alu()
        r = p.run({}, {0:A,1:B}, {2:4}, grid=4, signed=True)
        if "min" in kern and kern[0]=='i': exp=[min(a,bb) for a,bb in zip(A,B)]
        elif "max" in kern and kern[0]=='i': exp=[max(a,bb) for a,bb in zip(A,B)]
        elif "min" in kern: exp=[s32(min(us(a),us(bb))) for a,bb in zip(A,B)]
        else: exp=[s32(max(us(a),us(bb))) for a,bb in zip(A,B)]
        print(f"  {kern:5s} b4={b[4]:#04x}  out={r.get(2)}  exp={exp}  {'PASS' if r.get(2)==exp else 'FAIL'}")
        p.close()
    # splice signed->unsigned: take imin (b4=0x07), clear bit1 -> 0x05 unsigned min
    p = intprobe.IntProbe("kernels/imin.metal")
    off,b = p.alu()
    r = p.run({off+4: b[4] & ~0x02 & 0xff}, {0:A,1:B}, {2:4}, grid=4)
    exp=[s32(min(us(a),us(bb))) for a,bb in zip(A,B)]
    print(f"  splice imin b4 clear bit1 -> unsigned min  out={r.get(2)} exp={exp} {'PASS' if r.get(2)==exp else 'FAIL'}")
    p.close()

def lengthbit_test():
    print("\n===== LENGTH BIT b1 (10B 2-src vs 12B mad) =====")
    p = intprobe.IntProbe("kernels/iadd.metal")
    off, b = p.alu(); print(f"iadd(10B) ALU={b.hex()} b1={b[1]:#x}")
    A=[12,20,7,100]; B=[3,6,5,8]
    base = p.run({}, {0:A,1:B}, {2:4}, grid=4)
    print(f"  base(b1=01) out={base.get(2)} (a+b) st={base['_status']}")
    # clear b1 bit0 -> GPU should read this as the 12-byte form, consuming 2 bytes
    # of the following store -> corrupted stream (fault or wrong output).
    r = p.run({off+1: b[1] & ~0x01 & 0xff}, {0:A,1:B}, {2:4}, grid=4)
    print(f"  b1&~1 (=00) out={r.get(2)} st={r['_status']}  (expect broken: length now read as 12B)")
    p.close()

def dst_test():
    print("\n===== DST relocation (dstc: out=va+vb, o2=va, o3=vb) =====")
    p = intprobe.IntProbe("kernels/dstc.metal")
    off, b = p.alu(); print(f"dstc add ALU={b.hex()}")
    A=[1,2,4,8]; B=[16,32,64,128]
    def cls(v):
        for nm,ex in {"a+b":[a+bb for a,bb in zip(A,B)],"a":A,"b":B,"zero":[0]*4}.items():
            if v==ex: return nm
        return "?"
    # b3 in dstc-add = 0x06 vs iadd 0x00 -> candidate dst field. sweep b3 low bits.
    for b3 in range(0, 8):
        r=p.run({off+3:b3}, {0:A,1:B}, {2:4,3:4,4:4}, grid=4)
        print(f"  b3={b3:#04x}  out={cls(r.get(2,[]))} o2={cls(r.get(3,[]))} o3={cls(r.get(4,[]))} st={r['_status']}")
    p.close()

if __name__ == "__main__":
    sel = sys.argv[1:] or ["imm","neg","signed","len","dst"]
    if "imm" in sel: imm_tests()
    if "neg" in sel: negate_tests()
    if "signed" in sel: signed_tests()
    if "len" in sel: lengthbit_test()
    if "dst" in sel: dst_test()
