#!/usr/bin/env python3
# validate.py -- EXP-0013 HW splice-and-observe validation of the scalar ALU
# (conversions, FMA 3rd-source, float unary op-select, fmin/fmax, bitwise
# truth-table, shifts, compare condition codes). Runs ON THE DEVICE.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are spliced/executed.
import os, sys, struct, math, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
probe = importlib.util.module_from_spec(importlib.util.spec_from_file_location("probe", os.path.join(HERE,"probe.py")))
importlib.util.spec_from_file_location("probe", os.path.join(HERE,"probe.py")).loader.exec_module(probe)
Probe = probe.Probe

def f2bits(x): return struct.unpack('<I', struct.pack('<f', x))[0]
def h2bits(x): return struct.unpack('<H', struct.pack('<e', x))[0]
NAN=float('nan'); INF=float('inf')
def approx(a,b,t=1e-3):
    if isinstance(a,float) and math.isnan(a): return isinstance(b,float) and math.isnan(b)
    return abs(a-b) <= t*max(1,abs(b))

def sec(t): print(f"\n{'='*70}\n{t}\n{'='*70}")

# ---------------------------------------------------------------- CONVERSIONS
def conversions():
    sec("1. CONVERSIONS")
    # fp32 -> fp16 (byte0 0x11 half-group)
    p = Probe("kernels/cv_f2h.metal"); off,b = p.alu()
    A=[3.5, 1.0, 65504.0, 0.1]
    r = p.run({}, {0:('f',A)}, {1:('h',4)}, grid=4)
    exp=[struct.unpack('<e',struct.pack('<e',x))[0] for x in A]
    print(f"  f2h ALU={b.hex()} out={r[1]} exp={exp} {'PASS' if all(approx(o,e,1e-2) for o,e in zip(r[1],exp)) else 'FAIL'} st={r['_status']}")
    p.close()
    # fp16 -> fp32 (byte0 0x09 float ALU, 16-bit source)
    p = Probe("kernels/cv_h2f.metal"); off,b=p.alu()
    Ah=[3.5,1.25,-2.0,0.5]
    r=p.run({}, {0:('h',Ah)}, {1:('f',4)}, grid=4)
    print(f"  h2f ALU={b.hex()} out={r[1]} exp={Ah} {'PASS' if all(approx(o,e) for o,e in zip(r[1],Ah)) else 'FAIL'} st={r['_status']}")
    p.close()
    # fp32 -> int (byte0 0x27) : truncation toward zero
    p = Probe("kernels/cv_f2i.metal"); off,b=p.alu()
    A=[3.9,-3.9,2.5,-2.5]
    r=p.run({}, {0:('f',A)}, {1:('i',4)}, grid=4)
    exp=[int(x) for x in A]  # C trunc toward zero
    print(f"  f2i ALU={b.hex()} out={r[1]} exp(trunc)={exp} {'PASS' if r[1]==exp else 'FAIL'} st={r['_status']}")
    # splice signed bit byte+7 0x48 -> 0x08 (should become unsigned convert -> f2u behaviour)
    r2=p.run({off+7: 0x08}, {0:('f',[3.9,5.0,10.0,255.0])}, {1:('u',4)}, grid=4)
    print(f"    splice b7 0x48->0x08 (sign bit): out(u)={r2[1]} (f2u expects [3,5,10,255]) st={r2['_status']}")
    p.close()
    # int -> fp32 (byte0 0xa7)
    p = Probe("kernels/cv_i2f.metal"); off,b=p.alu()
    A=[3,-3,1000000,-7]
    r=p.run({}, {0:('i',A)}, {1:('f',4)}, grid=4)
    print(f"  i2f ALU={b.hex()} out={r[1]} exp={[float(x) for x in A]} {'PASS' if all(approx(o,float(e)) for o,e in zip(r[1],A)) else 'FAIL'} st={r['_status']}")
    # splice signed bit byte+7 0x60 -> 0x20 -> unsigned convert
    r2=p.run({off+7:0x20}, {0:('i',[-1,-3,7,10])}, {1:('f',4)}, grid=4)
    print(f"    splice b7 0x60->0x20 (sign bit): -1 as u32=4294967295 -> out={r2[1]} st={r2['_status']}")
    p.close()
    # fp32 -> uint / uint -> fp32
    p=Probe("kernels/cv_f2u.metal"); off,b=p.alu()
    r=p.run({}, {0:('f',[3.9,0.0,100.5,4000000000.0])}, {1:('u',4)}, grid=4)
    print(f"  f2u ALU={b.hex()} out={r[1]} exp=[3,0,100,4000000000] st={r['_status']}")
    p.close()
    p=Probe("kernels/cv_u2f.metal"); off,b=p.alu()
    r=p.run({}, {0:('u',[3,0,4294967295,100])}, {1:('f',4)}, grid=4)
    print(f"  u2f ALU={b.hex()} out={r[1]} exp=[3,0,4294967295,100] st={r['_status']}")
    p.close()
    # integer width/sign: int->short->int (sign-extend from 16)
    p=Probe("kernels/cv_i2s.metal"); off,b=p.alu()
    A=[0x00007FFF, 0x00008000, -1, 0x00012345]  # 0x8000 as s16 = -32768
    r=p.run({}, {0:('i',A)}, {1:('i',4)}, grid=4)
    exp=[struct.unpack('<h',struct.pack('<I',x&0xffffffff)[:2])[0] for x in A]
    print(f"  i2s(sext16) ALU={b.hex()} out={r[1]} exp={exp} {'PASS' if r[1]==exp else 'FAIL'} st={r['_status']}")
    p.close()
    # uint->ushort->uint (zero-extend from 16) byte0 0x13
    p=Probe("kernels/cv_u2us.metal"); off,b=p.alu()
    A=[0x0000FFFF, 0x00018000, 0xFFFFFFFF, 0x12345]
    r=p.run({}, {0:('u',A)}, {1:('u',4)}, grid=4)
    exp=[x & 0xFFFF for x in A]
    print(f"  u2us(zext16) ALU={b.hex()} out={r[1]} exp={exp} {'PASS' if r[1]==exp else 'FAIL'} st={r['_status']}")
    p.close()
    # uint->uchar->uint (zero-extend from 8) byte0 0x0b (and-imm 0xff)
    p=Probe("kernels/cv_u2uc.metal"); off,b=p.alu()
    A=[0x1234, 0xFF, 0x100, 0xABCDEF]
    r=p.run({}, {0:('u',A)}, {1:('u',4)}, grid=4)
    exp=[x & 0xFF for x in A]
    print(f"  u2uc(zext8=and0xff) ALU={b.hex()} out={r[1]} exp={exp} {'PASS' if r[1]==exp else 'FAIL'} st={r['_status']}")
    p.close()

# ---------------------------------------------------------------- FMA
def fma_test():
    sec("2. FMA (0x09 8-byte 3-source) -- confirm a*b+c and locate srcC (byte+5)")
    p=Probe("kernels/fma.metal"); off,b=p.alu()
    print(f"  fma ALU@{off:#x}={b.hex()}")
    A=[1,2,3,4]; B=[2,2,2,2]; C=[100,200,300,400]
    r=p.run({}, {0:('f',A),1:('f',B),2:('f',C)}, {3:('f',4)}, grid=4)
    exp=[a*bb+c for a,bb,c in zip(A,B,C)]
    print(f"  base out={r[3]} exp a*b+c={exp} {'PASS' if all(approx(o,e) for o,e in zip(r[3],exp)) else 'FAIL'}")
    # confirm srcC is byte+5: set byte+5 := byte+4 (srcB descriptor) -> addend becomes b
    r2=p.run({off+5: b[4]}, {0:('f',A),1:('f',B),2:('f',C)}, {3:('f',4)}, grid=4)
    exp2=[a*bb+bb for a,bb in zip(A,B)]
    print(f"  splice b5:=b4(0x{b[4]:02x}) out={r2[3]} exp a*b+b={exp2} {'PASS' if all(approx(o,e) for o,e in zip(r2[3],exp2)) else 'FAIL'}  (proves b5=srcC)")
    # set byte+5 := byte+3 (srcA) -> addend becomes a
    r3=p.run({off+5: b[3]}, {0:('f',A),1:('f',B),2:('f',C)}, {3:('f',4)}, grid=4)
    exp3=[a*bb+a for a,bb in zip(A,B)]
    print(f"  splice b5:=b3(0x{b[3]:02x}) out={r3[3]} exp a*b+a={exp3} {'PASS' if all(approx(o,e) for o,e in zip(r3[3],exp3)) else 'FAIL'}")
    p.close()

# ---------------------------------------------------------------- FLOAT UNARY
def unary():
    sec("3. FLOAT UNARY: fneg/fabs op-select (0x0b byte+5) + special funcs (0x2f/0xaf)")
    p=Probe("kernels/un_fneg.metal"); off,b=p.alu()
    A=[1.0,-2.0,3.0,-4.0]
    r=p.run({}, {0:('f',A)}, {1:('f',4)}, grid=4)
    print(f"  fneg ALU={b.hex()} out={r[1]} exp={[-x for x in A]} {'PASS' if all(approx(o,-x) for o,x in zip(r[1],A)) else 'FAIL'}")
    # splice byte+5 0x0a -> 0x02 (abs)
    r2=p.run({off+5:0x02}, {0:('f',A)}, {1:('f',4)}, grid=4)
    print(f"  splice b5 0x0a->0x02 out={r2[1]} exp abs={[abs(x) for x in A]} {'PASS' if all(approx(o,abs(x)) for o,x in zip(r2[1],A)) else 'FAIL'}")
    # splice byte+5 -> 0x00 (fmov / passthrough)
    r3=p.run({off+5:0x00}, {0:('f',A)}, {1:('f',4)}, grid=4)
    print(f"  splice b5 0x0a->0x00 out={r3[1]} exp mov={A} {'PASS' if all(approx(o,x) for o,x in zip(r3[1],A)) else 'FAIL'}")
    # splice byte+5 -> 0x0a again but also abs bit => neg(abs)= -|a|
    r4=p.run({off+5:0x08}, {0:('f',A)}, {1:('f',4)}, grid=4)
    print(f"  splice b5 0x0a->0x08 (neg only,no abs) out={r4[1]} (bit3=neg,bit1=abs)")
    p.close()
    # special funcs single-op group 0x2f/0xaf
    for kern,fn,name in [("un_fexp2",lambda x:2**x,"exp2"),("un_flog2",lambda x:math.log2(x),"log2"),
                         ("un_ffloor",math.floor,"floor"),("un_fceil",math.ceil,"ceil"),
                         ("un_ftrunc",math.trunc,"trunc"),("un_frint",lambda x:float(round(x)),"rint")]:
        p=Probe(f"kernels/{kern}.metal"); off,b=p.alu()
        A=[2.0,3.0,4.5,-1.5] if name in("floor","ceil","trunc","rint") else [1.0,2.0,4.0,8.0]
        r=p.run({}, {0:('f',A)}, {1:('f',4)}, grid=4)
        exp=[float(fn(x)) for x in A]
        print(f"  {name:6s} ALU={b.hex()} out={r[1]} exp={exp} {'PASS' if all(approx(o,e,1e-2) for o,e in zip(r[1],exp)) else 'FAIL'}")
        p.close()
    # floor kernel: sweep byte+8 to enumerate round-mode (00=rint,02=floor,04=ceil,06=trunc)
    p=Probe("kernels/un_ffloor.metal"); off,b=p.alu()
    A=[2.4,2.6,-2.4,-2.6]
    print(f"  round-mode sweep on floor base (byte+8), A={A}:")
    for v in (0x00,0x02,0x04,0x06):
        r=p.run({off+8:v}, {0:('f',A)}, {1:('f',4)}, grid=4)
        print(f"    b8={v:#04x} out={r[1]} st={r['_status']}")
    p.close()

# ---------------------------------------------------------------- FMIN/FMAX
def minmax():
    sec("4. FMIN/FMAX (0x12 byte+4 sel) + NaN/signed-zero behaviour")
    p=Probe("kernels/fmax.metal"); off,b=p.alu()
    A=[1.0,5.0,3.0,8.0]; B=[4.0,2.0,7.0,6.0]
    r=p.run({}, {0:('f',A),1:('f',B)}, {2:('f',4)}, grid=4)
    print(f"  fmax ALU={b.hex()} out={r[2]} exp={[max(a,bb) for a,bb in zip(A,B)]}")
    # splice byte+4 0x00->0x01 -> fmin
    r2=p.run({off+4:0x01}, {0:('f',A),1:('f',B)}, {2:('f',4)}, grid=4)
    print(f"  splice b4 0x00->0x01 out={r2[2]} exp min={[min(a,bb) for a,bb in zip(A,B)]} {'PASS' if all(approx(o,min(a,bb)) for o,a,bb in zip(r2[2],A,B)) else 'FAIL'}")
    # NaN behaviour: fmax(nan,x) and fmax(x,nan)
    An=[NAN,3.0,NAN,3.0]; Bn=[3.0,NAN,NAN,3.0]
    r3=p.run({}, {0:('f',An),1:('f',Bn)}, {2:('f',4)}, grid=4)
    print(f"  fmax NaN: a={An} b={Bn} -> out={r3[2]}  (IEEE maxNum returns non-NaN)")
    r4=p.run({off+4:0x01}, {0:('f',An),1:('f',Bn)}, {2:('f',4)}, grid=4)
    print(f"  fmin NaN: a={An} b={Bn} -> out={r4[2]}")
    # signed zero
    r5=p.run({}, {0:('f',[-0.0,0.0,-0.0,0.0]),1:('f',[0.0,-0.0,-0.0,0.0])}, {2:('f',4)}, grid=4)
    print(f"  fmax(+-0): out bits={[f2bits(x) for x in r5[2]]} (0x80000000=-0)")
    p.close()

# ---------------------------------------------------------------- BITWISE
def bitwise():
    sec("5a. BITWISE truth-table (0x0b) -- run all 8 + sweep op/invert on ixor base")
    AA=0xAAAAAAAA; CC=0xCCCCCCCC  # per-bit (b,a) index -> LUT readout
    def lut(outv):
        # outv over bit i where a_bit=i&1, b_bit=(i>>1)&1 ; sample bit0..3
        return [ (outv>>i)&1 for i in range(4) ]  # [a0b0,a1b0,a0b1,a1b1]
    for kern,fn in [("iand",lambda a,b:a&b),("ior",lambda a,b:a|b),("ixor",lambda a,b:a^b),
                    ("iandn",lambda a,b:a&(~b)),("iorn",lambda a,b:a|(~b)),
                    ("ixnor",lambda a,b:~(a^b)),("inand",lambda a,b:~(a&b)),("inor",lambda a,b:~(a|b))]:
        p=Probe(f"kernels/{kern}.metal"); off,b=p.alu()
        r=p.run({}, {0:('u',[AA]*4),1:('u',[CC]*4)}, {2:('u',4)}, grid=4)
        exp=fn(AA,CC)&0xFFFFFFFF
        ok = r[2] and r[2][0]==exp
        print(f"  {kern:6s} ALU={b.hex()} out={r[2][0]:#010x} exp={exp:#010x} LUT={lut(r[2][0])} {'PASS' if ok else 'FAIL'}")
        p.close()
    # sweep byte+2 (op) and byte+4 (invert) on the ixor base
    sec("5a'. ixor-base sweep: byte+2 in {1e,1f} x byte+4 in 0..3 x byte+5 bit3")
    p=Probe("kernels/ixor.metal"); off,b=p.alu()
    print(f"  base ixor ALU={b.hex()}  (b2={b[2]:#x} b4={b[4]:#x} b5={b[5]:#x})")
    for b2 in (0x1e,0x1f):
        for b4 in (0x00,0x01,0x02,0x03):
            for b5 in (b[5]&~0x08, b[5]|0x08):
                r=p.run({off+2:b2, off+4:b4, off+5:b5}, {0:('u',[AA]*4),1:('u',[CC]*4)}, {2:('u',4)}, grid=4)
                if r[2]:
                    print(f"    b2={b2:#04x} b4={b4:#04x} b5={b5:#04x} -> {r[2][0]:#010x} LUT={lut(r[2][0])} st={r['_status']}")
                else:
                    print(f"    b2={b2:#04x} b4={b4:#04x} b5={b5:#04x} -> (no out) st={r['_status']}")
    p.close()

# ---------------------------------------------------------------- SHIFTS
def shifts():
    sec("5b. SHIFTS / BITFIELD (0xa7 / 0x9f)")
    # arithmetic shift-right immediate (0xa7 10B)
    p=Probe("kernels/iashr_i.metal"); off,b=p.alu()   # a>>2 signed
    A=[-16,16,-64,255]
    r=p.run({}, {0:('i',A)}, {1:('i',4)}, grid=4)
    print(f"  ashr_i(>>2) ALU={b.hex()} out={r[1]} exp={[x>>2 for x in A]} {'PASS' if r[1]==[x>>2 for x in A] else 'FAIL'} (b6={b[6]:#x}=shamt)")
    # sweep the shift-amount byte+6
    for sh,bv in [(1,0x04),(2,0x08),(4,0x10),(8,0x20)]:
        r=p.run({off+6:bv}, {0:('i',[256,-256,1024,-1024])}, {1:('i',4)}, grid=4)
        print(f"    b6={bv:#04x} -> out={r[1]} (if shamt={sh}: {[x>>sh for x in [256,-256,1024,-1024]]})")
    p.close()
    # logical shift-right immediate (0xa7 12B bfe form)
    p=Probe("kernels/ushr_i.metal"); off,b=p.alu()
    A=[0xFFFFFFF0, 16, 0x80000000, 255]
    r=p.run({}, {0:('u',A)}, {1:('u',4)}, grid=4)
    print(f"  lshr_i(>>2) ALU={b.hex()} out={[hex(x) for x in r[1]]} exp={[hex(x>>2) for x in A]} {'PASS' if r[1]==[x>>2 for x in A] else 'FAIL'}")
    p.close()
    # shift-left immediate (0x9f 10B)
    p=Probe("kernels/ishl_i.metal"); off,b=p.alu()
    A=[1,3,-1,100]
    r=p.run({}, {0:('i',A)}, {1:('i',4)}, grid=4)
    exp=[(x<<3) & 0xffffffff for x in A]; exp=[e-(1<<32) if e&0x80000000 else e for e in exp]
    print(f"  shl_i(<<3) ALU={b.hex()} out={r[1]} exp={exp} {'PASS' if r[1]==exp else 'FAIL'}")
    p.close()
    # bitfield-extract (0xa7 12B)
    p=Probe("kernels/ibfe.metal"); off,b=p.alu()
    A=[0xABCDEF12, 0xFFFFFFFF, 0x00000F00, 0x12345678]
    r=p.run({}, {0:('u',A)}, {1:('u',4)}, grid=4)
    exp=[(x>>4)&0xFF for x in A]
    print(f"  bfe(4,8) ALU={b.hex()} out={[hex(x) for x in r[1]]} exp={[hex(e) for e in exp]} {'PASS' if r[1]==exp else 'FAIL'}")
    p.close()

# ---------------------------------------------------------------- COMPARE CC
def compare():
    sec("6. COMPARE condition codes (0x12 icmpsel 14B) -- run all 18 + sweep byte+6")
    inputs = {"i":([1,5,5,-3],[5,5,1,2]), "u":([1,5,5,7],[5,5,1,3]), "f":([1.,5.,5.,-3.],[5.,5.,1.,2.])}
    tests = [("icmp_eq","i",lambda a,b:a==b),("icmp_ne","i",lambda a,b:a!=b),
             ("icmp_lt","i",lambda a,b:a<b),("icmp_le","i",lambda a,b:a<=b),
             ("icmp_gt","i",lambda a,b:a>b),("icmp_ge","i",lambda a,b:a>=b),
             ("ucmp_lt","u",lambda a,b:a<b),("ucmp_le","u",lambda a,b:a<=b),
             ("ucmp_gt","u",lambda a,b:a>b),("ucmp_ge","u",lambda a,b:a>=b),
             ("ucmp_eq","u",lambda a,b:a==b),("ucmp_ne","u",lambda a,b:a!=b),
             ("fcmp_eq","f",lambda a,b:a==b),("fcmp_ne","f",lambda a,b:a!=b),
             ("fcmp_lt","f",lambda a,b:a<b),("fcmp_le","f",lambda a,b:a<=b),
             ("fcmp_gt","f",lambda a,b:a>b),("fcmp_ge","f",lambda a,b:a>=b)]
    for nm,ty,fn in tests:
        p=Probe(f"kernels/{nm}.metal"); off,b=p.alu()
        A,B=inputs[ty]
        r=p.run({}, {0:(ty,A),1:(ty,B)}, {2:('i',4)}, grid=4)
        exp=[1 if fn(a,bb) else 0 for a,bb in zip(A,B)]
        cc=f"b4={b[4]:#04x} b5={b[5]:#04x} b6={b[6]:#04x} b9={b[9]:#04x}"
        print(f"  {nm:8s} {cc} out={r[2]} exp={exp} {'PASS' if r[2]==exp else 'FAIL'}")
        p.close()
    # sweep byte+6 (condition) on icmp_lt base; inputs cover lt/eq/gt and a signed-negative
    sec("6'. icmp_lt base: sweep byte+6 (condition code), signed A=[1,5,5,-3] B=[5,5,1,2]")
    p=Probe("kernels/icmp_lt.metal"); off,b=p.alu()
    A=[1,5,5,-3]; B=[5,5,1,2]
    print(f"  base icmp_lt {b.hex()}  a<b expect [1,0,0,1] (signed -3<2)")
    for v in range(0,8):
        r=p.run({off+6:v}, {0:('i',A),1:('i',B)}, {2:('i',4)}, grid=4)
        print(f"    b6={v:#04x} -> out={r[2]} st={r['_status']}")
    # also sweep byte+4 (0x22 vs 0x26)
    print("  sweep byte+4 (0x22 relational vs 0x26 equality) at b6=base:")
    for v in (0x22,0x26):
        r=p.run({off+4:v}, {0:('i',A),1:('i',B)}, {2:('i',4)}, grid=4)
        print(f"    b4={v:#04x} -> out={r[2]}")
    p.close()

if __name__=="__main__":
    todo = sys.argv[1:] or ["conv","fma","unary","minmax","bitwise","shifts","compare"]
    if "conv" in todo: conversions()
    if "fma" in todo: fma_test()
    if "unary" in todo: unary()
    if "minmax" in todo: minmax()
    if "bitwise" in todo: bitwise()
    if "shifts" in todo: shifts()
    if "compare" in todo: compare()
    print("\n[validate.py done]")
