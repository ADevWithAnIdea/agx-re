#!/usr/bin/env python3
# validate.py -- EXP-0006 HW splice-and-observe validations for the falu2
# operand encoding: packed immediate, dst field, and 16/32-bit size select.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are spliced/executed.
import os, sys, struct, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def load_mod(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
probe=load_mod("probe",os.path.join(HERE,"probe.py"))
analyze=load_mod("analyze",os.path.join(HERE,"analyze.py"))

def alu(p, which=0):
    toks=analyze.structural_tokens(p.main)
    a=[t for t in toks if t[0]=="ALU"][which]
    return a[1], a[3]   # offset, bytes

def approx(xs, ys, tol=1e-3):
    return len(xs)==len(ys) and all(abs(x-y)<=tol*max(1,abs(y)) for x,y in zip(xs,ys))

def pack_imm(K):
    """Encode K as the b1 minifloat byte + sign (b2 bit3). Returns (b1, sign)."""
    sign = 1 if K<0 else 0
    a=abs(float(K))
    best=None
    for e in range(8,16):
        for m in range(8):
            if e==8:  # subnormal: value = (m/8)*2^(9-11)
                v=(m/8.0)*(2.0**(9-11))
            else:
                v=(1+m/8.0)*(2.0**(e-11))
            b1=(e<<4)|(m<<1)|1
            if best is None or abs(v-a)<best[0]: best=(abs(v-a),b1,v)
    return best[1], sign, best[2]

def decode_imm(b1, sign):
    e=(b1>>4)&0xf; m=(b1>>1)&0x7
    if e==8: v=(m/8.0)*(2.0**(9-11))
    else:    v=(1+m/8.0)*(2.0**(e-11))
    return -v if sign else v

def imm_tests():
    print("\n===== IMMEDIATE: splice packed float, observe runtime = K =====")
    p=probe.Probe("kernels/add1.metal")
    off,b=alu(p); print(f"base ALU @{off:#x} = {b.hex()}  (a+1.0)")
    A=[10.0,20.0,30.0,40.0]
    # positions: b1 at off+1 (imm byte), b2 at off+2 (sign bit3)
    for K in [0.0,0.5,1.0,2.0,4.0,-1.0,-2.0,3.5,0.25,8.0,1.5,16.0,-0.5,0.0625,30.0,3.0]:
        b1,sign,vq=pack_imm(K)
        b2 = (b[2] & ~0x08) | (0x08 if sign else 0)
        ov={off+1:b1, off+2:b2}
        r=p.run(ov, {0:A}, {1:4}, grid=4)
        exp=[x+decode_imm(b1,sign) for x in A]
        ok=approx(r.get(1,[]), exp)
        print(f"  K={K:>7}  b1={b1:#04x} sign={sign} q={decode_imm(b1,sign):+.5g}  out={r.get(1)}  {'PASS' if ok else 'FAIL'}")
    p.close()

def dst_tests():
    print("\n===== DST: sweep b0[4:8], observe result relands (via dstc) =====")
    p=probe.Probe("kernels/dstc.metal")
    off,b=alu(p); print(f"base ALU @{off:#x} = {b.hex()}  (out=va+vb; o2=va; o3=vb)")
    A=[1.0,2.0,4.0,8.0]; B=[16.0,32.0,64.0,128.0]
    for hi in range(0,8):
        b0=(b[0]&0x0f)|(hi<<4)
        r=p.run({off:b0}, {0:A,1:B}, {2:4,3:4,4:4}, grid=4)
        def cls(v):
            for nm,ex in {"a+b":[x+y for x,y in zip(A,B)],"a":A,"b":B,"zero":[0]*4}.items():
                if approx(v,ex): return nm
            return "?"
        print(f"  b0={b0:#04x}(dst reg{hi})  out={cls(r.get(2,[]))}  o2={cls(r.get(3,[]))}  o3={cls(r.get(4,[]))}   st={r['_status']}")
    p.close()

def size_tests():
    print("\n===== SIZE bit (operand bit0): 32-bit vs 16-bit-half read =====")
    p=probe.Probe("kernels/add.metal")
    off,b=alu(p); print(f"base ALU @{off:#x} = {b.hex()}  srcA=b1={b[1]:#x} srcB=b3={b[3]:#x}")
    def hlo(x):  # low halfword of float32(x) reinterpreted as float16
        bits=struct.unpack("<I",struct.pack("<f",x))[0]&0xffff
        return probe._half_to_float(bits)
    def hhi(x):  # high halfword
        bits=(struct.unpack("<I",struct.pack("<f",x))[0]>>16)&0xffff
        return probe._half_to_float(bits)
    # a chosen so BOTH halfwords are nonzero/recognizable
    A=[1.1, 2.2, 3.3, 4.4]; B=[0.0,0.0,0.0,0.0]  # srcB reads b=0 -> out = srcA read
    print("  a =",A)
    print("  ref a low-half  as f16:", [round(hlo(x),5) for x in A])
    print("  ref a high-half as f16:", [round(hhi(x),5) for x in A])
    # srcA index b1: bit0=1 (orig, 32-bit). bit0=0 -> 16-bit; bit1 selects half.
    for lab,val in [("srcA 32-bit  (b1|1)",b[1]|1),
                    ("srcA 16-bit lo (b1&~3)",b[1]&~3),
                    ("srcA 16-bit hi (b1&~1|2)",(b[1]&~1)|2)]:
        r=p.run({off+1:val}, {0:A,1:B}, {2:4}, grid=4)
        print(f"  {lab}: b1={val:#04x} out={[round(x,5) for x in r.get(2,[])]}")
    p.close()

def modifier_tests():
    print("\n===== MODIFIERS: negate (6B, b5 bit3) & abs (10B) with signed inputs =====")
    # negate: plain add, splice b5 bit3, expect a + (-b)
    p=probe.Probe("kernels/add.metal")
    off,b=alu(p)
    A=[10.0,10.0,-10.0,-10.0]; B=[3.0,-3.0,3.0,-3.0]
    print(f"  add ALU={b.hex()}  A={A} B={B}")
    r0=p.run({}, {0:A,1:B}, {2:4}, grid=4)
    r1=p.run({off+5:(b[5]|0x08)}, {0:A,1:B}, {2:4}, grid=4)   # set b5 bit3
    print(f"  base (a+b)          out={r0.get(2)}  exp {[x+y for x,y in zip(A,B)]}")
    print(f"  splice b5|0x08(a-b) out={r1.get(2)}  exp {[x-y for x,y in zip(A,B)]}  "
          f"{'PASS' if approx(r1.get(2,[]),[x-y for x,y in zip(A,B)]) else 'FAIL'}")
    p.close()
    # abs: absb kernel (a+|b|), 10-byte form; verify vs signed b, then splice
    # abs-source-select byte and observe.
    pb=probe.Probe("kernels/absb.metal")
    offb,bb=alu(pb)
    print(f"  absb ALU={bb.hex()} ({len(bb)}B)  A={A} B={B}")
    rb=pb.run({}, {0:A,1:B}, {2:4}, grid=4)
    print(f"  base (a+|b|)        out={rb.get(2)}  exp {[x+abs(y) for x,y in zip(A,B)]}  "
          f"{'PASS' if approx(rb.get(2,[]),[x+abs(y) for x,y in zip(A,B)]) else 'FAIL'}")
    # splice negate bit (b5 bit3) into abs form -> a + (-|b|)
    rn=pb.run({offb+5:(bb[5]|0x08)}, {0:A,1:B}, {2:4}, grid=4)
    print(f"  splice b5|0x08      out={rn.get(2)}  exp a-|b| {[x-abs(y) for x,y in zip(A,B)]}  "
          f"{'PASS' if approx(rn.get(2,[]),[x-abs(y) for x,y in zip(A,B)]) else 'FAIL'}")
    pb.close()

def mode_tests():
    print("\n===== SRC-B IMMEDIATE MODE select (b4 bit7 = 0x80) =====")
    p=probe.Probe("kernels/add.metal")
    off,b=alu(p); print(f"  add ALU={b.hex()} (reg-reg mode, b4={b[4]:#x})")
    A=[10.0,20.0,30.0,40.0]; B=[7.0,7.0,7.0,7.0]
    r0=p.run({}, {0:A,1:B}, {2:4}, grid=4)
    print(f"  reg mode  (a+b)   out={r0.get(2)}  exp {[x+7 for x in A]}")
    # flip to immediate mode: b4|0x80, imm byte b1=0xb1(=1.0), srcA moves to b3=0x01(reg0=a),
    # sign(b2 bit3)=0
    b2=(b[2] & ~0x08)
    r1=p.run({off+4:(b[4]|0x80), off+1:0xb1, off+3:0x01, off+2:b2}, {0:A,1:B}, {2:4}, grid=4)
    ok=approx(r1.get(2,[]), [x+1.0 for x in A])
    print(f"  imm mode (a+1.0)  out={r1.get(2)}  exp {[x+1 for x in A]}  {'PASS' if ok else 'FAIL'}")
    p.close()

if __name__=="__main__":
    sel=sys.argv[1:] or ["imm","dst","size","mod","mode"]
    if "mode" in sel: mode_tests()
    if "imm" in sel: imm_tests()
    if "dst" in sel: dst_tests()
    if "size" in sel: size_tests()
    if "mod" in sel: modifier_tests()
