#!/usr/bin/env python3
# RT-1a-FIX item 4: characterize the two undecoded groups.
#  (a) byte0=0x60 -- appears as `60 00 00 00` right after the entry get_sr in the
#      spilling `big` kernel. No length rule -> tokenizer halts. Determine length
#      (=4 hypothesis) + role (splice/observe: load-bearing frame setup?).
#  (b) byte0=0x09 / byte+2=0x18 -- compact float-accumulate variant `19 0b 18 09`
#      in falubank's a2+a3+a4+a5+a6+a7 reduction. length rule already says 4 but no
#      descriptor matches. Prove it is an arithmetic accumulate (byte+1/byte+3 are
#      sources) and that 0x18 vs 0x38 are the same op (interchangeable).
import sys, os, subprocess, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from persistrun import PersistRunner

def locate(arch):
    return int(subprocess.check_output(["python3","agxparse.py",arch,"--locate","_agc.main"],text=True).split()[0])

# ---------- (a) 0x60 in big.bin ----------
print("## (a) big.bin byte0=0x60 `60 00 00 00` (spill/frame setup?)")
big = open("big.bin","rb").read(); bm = locate("big.bin")
sixty = bm + 0x04
print(f"   bytes at main+0x04: {big[sixty:sixty+8].hex()}  (0x60 op + following iadd2 start)")
# inputs: F(1) 16 floats, I(2) 16 ints, U(3) 16 uints ; out(0)
F = [1.5,2.5,3.5,4.5,5.5,6.5,7.5,8.5,9.5,10.5,11.5,12.5,13.5,14.5,15.5,16.5]
I = [3,-4,5,-6,7,8,9,10,11,12,13,14,15,16,17,-18]
U = [1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16]
open("F.bin","wb").write(struct.pack("<16f",*F))
open("I.bin","wb").write(struct.pack("<16i",*I))
open("U.bin","wb").write(struct.pack("<16I",*U))
ins = {1:"F.bin",2:"I.bin",3:"U.bin"}; outs={0:4}
r = PersistRunner(source="rt1a_big.metal", function="big", fast_math=False, agxrun_persist="./agxrun_persist")
def runbig(splices=None):
    sp = bytearray(big)
    for pos,val in (splices or []):
        sp[bm+pos] = val
    open("sp.bin","wb").write(sp)
    resp = r.request(archive="sp.bin", grid=1, tg=1, ins=ins, outs=outs, timeout=8)
    if resp["status"]!="OK": return resp["status"], None
    return "OK", struct.unpack("<I",resp["outs"][0])[0]
st0,base_out = runbig()
print(f"   baseline: {st0} out={base_out}")
# splice the 0x60 op's payload bytes (offsets +5,+6,+7 within _agc.main = the 00 00 00)
for name,pos,vals in [("byte0(+4)",4,[0x60,0x00,0xe0,0x40]),
                      ("byte+1(+5)",5,[0x00,0x01,0xff]),
                      ("byte+2(+6)",6,[0x00,0x01,0xff]),
                      ("byte+3(+7)",7,[0x00,0x01,0xff])]:
    for v in vals:
        st,o = runbig([(pos,v)])
        tag = " (orig)" if v==big[bm+pos] else ""
        chg = "" if o==base_out else "  <-- CHANGED" if o is not None else ""
        print(f"   splice {name}=0x{v:02x}: {st} out={o}{tag}{chg}")
r.close()

# ---------- (b) 0x18 compact accumulate in falubank.bin ----------
print("\n## (b) falubank.bin `19 0b 18 09` compact float-accumulate (byte+2=0x18)")
fb = open("falubank.bin","rb").read(); fm = locate("falubank.bin")
# from tokenization: the two 0x18 ops are at main +0x48 (19 0b 18 09) and +0x4c (09 05 18 07)
o18 = fm + 0x48
print(f"   op at main+0x48 = {fb[o18:o18+4].hex()} ; op at main+0x4c = {fb[fm+0x4c:fm+0x50].hex()}")
# v = a0..a7 ; out=a0+a1 ; out2 = a2+a3+a4+a5+a6+a7
v = [10.0,20.0, 3.0,4.0,5.0,6.0,7.0,8.0]
open("vfb.bin","wb").write(struct.pack("<8f",*v))
ins={2:"vfb.bin"}; outs={0:4,1:4}
r = PersistRunner(source="rt1a_falubank.metal", function="k", fast_math=False, agxrun_persist="./agxrun_persist")
def runfb(splices=None):
    sp = bytearray(fb)
    for pos,val in (splices or []):
        sp[fm+pos]=val
    open("sp.bin","wb").write(sp)
    resp = r.request(archive="sp.bin", grid=1, tg=1, ins=ins, outs=outs, timeout=6)
    if resp["status"]!="OK": return resp["status"],None,None
    return "OK", struct.unpack("<f",resp["outs"][0])[0], struct.unpack("<f",resp["outs"][1])[0]
st,o0,o1 = runfb()
print(f"   baseline: {st} out(a0+a1)={o0} out2(a2..a7)={o1}  (expect 30, 33)")
# splice byte+3 (srcB descriptor) of the +0x48 op -> should change out2 (it's a source)
for bo,label in [(0x48+3,"+0x48 byte+3 (srcB?)"),(0x48+1,"+0x48 byte+1 (srcA?)")]:
    orig=fb[fm+bo]
    for v2 in (orig, (orig^0x02), (orig^0x08)):
        st,o0,o1 = runfb([(bo,v2)])
        tag=" (orig)" if v2==orig else ""
        print(f"   splice {label}=0x{v2:02x}: {st} out2={o1}{tag}")
# splice byte+2 0x18 -> 0x38 (are they the same op?)
st,o0,o1 = runfb([(0x48+2,0x38)])
print(f"   splice +0x48 byte+2 0x18->0x38: {st} out2={o1}  (same as baseline 33 => interchangeable)")
r.close()
