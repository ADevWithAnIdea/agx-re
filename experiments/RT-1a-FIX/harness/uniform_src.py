#!/usr/bin/env python3
# RT-1a-FIX item 3: INDEPENDENT HW re-validation of the float uniform-source.
# Claim (RT-1a): `a[gid] + p.k` compiles to `09 0d 14 01 80 c0` and reads a REAL
# uniform register (a=10,u=7 -> 17); but the DB decodes byte+1=0x0d as a falu2i
# packed-minifloat immediate (~0.00085) -- wrong operand, wrong value. The
# distinguishing signal is byte+1's exponent nibble (bits[12:16]) under bit39:
# a real minifloat has exp>=8; a uniform-register index has exp<8.
#
# Method:
#  A) Prove it's a real uniform: run uni.metal (a=10) with p.k in {7,100,0.5} and
#     confirm out = a+p.k (an immediate could NOT change with the buffer).
#  B) Show the disambiguation: cadd (a+1.0, NO uniform bound) byte+1=0xb1 is a
#     minifloat (exp=0xb, out=a+1); splice cadd byte+1 -> 0x0d (exp=0) and the op
#     reads an UNBOUND uniform reg (=0) -> out=a+0, NOT a+imm_decode(0x0d).
#  C) Map the uniform index: uni_multi.metal (8 distinct uniforms k0..k7 = distinct
#     primes) reads k0; sweep the add's byte+1 and see which uniform each value
#     selects -> the uniform-register index encoding.
import sys, os, subprocess, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from persistrun import PersistRunner

def locate(arch):
    return int(subprocess.check_output(["python3","agxparse.py",arch,"--locate","_agc.main"],text=True).split()[0])

def find_falu(base, moff, mlen):
    # first 6-byte op with byte0 low-nibble 9 and bit39 (byte+4 bit7) set
    off = moff
    # crude: scan for '09 .. 14 01 80 c0'-shaped op by low nibble 9 + byte+4 bit0x80
    for i in range(moff, moff+mlen-6):
        if (base[i] & 0x0f) == 0x09 and (base[i+4] & 0x80):
            return i - moff
    return None

# ---- A) uni.metal reads a real uniform ----
print("## A) uni.metal a[gid]+p.k : does it read the runtime uniform?")
r = PersistRunner(source="rt1a_uni.metal", function="k", fast_math=False, agxrun_persist="./agxrun_persist")
open("a10.bin","wb").write(struct.pack("<f",10.0))
for pk in (7.0, 100.0, 0.5, 2.0):
    open("pk.bin","wb").write(struct.pack("<f",pk))
    resp = r.request(archive="uni.bin", grid=1, tg=1, ins={1:"a10.bin",2:"pk.bin"}, outs={0:4}, timeout=6)
    o = struct.unpack("<f",resp["outs"][0])[0] if resp["status"]=="OK" else None
    print(f"  p.k={pk:<6g} -> {resp['status']} out={o}  (a+p.k={10.0+pk})  match={abs((o or -1)-(10.0+pk))<1e-3}")
r.close()

# ---- B) cadd minifloat vs uniform disambiguation ----
print("\n## B) cadd (a+1.0, no uniform) byte+1=0xb1 minifloat; splice->0x0d reads unbound uniform(=0)")
r = PersistRunner(source="cadd.metal", function="k", fast_math=False, agxrun_persist="./agxrun_persist")
cadd = open("cadd.bin","rb").read(); cm = locate("cadd.bin")
coff = find_falu(cadd, cm, 0x40)
print(f"   cadd falu at main+0x{coff:x} = {cadd[cm+coff:cm+coff+6].hex()}")
open("a10.bin","wb").write(struct.pack("<f",10.0))
for b1 in (0xb1, 0x0d, 0x00):
    sp = bytearray(cadd); sp[cm+coff+1] = b1
    open("sp.bin","wb").write(sp)
    resp = r.request(archive="sp.bin", grid=1, tg=1, ins={1:"a10.bin"}, outs={0:4}, timeout=6)
    o = struct.unpack("<f",resp["outs"][0])[0] if resp["status"]=="OK" else None
    e = (b1>>4)&0xf
    print(f"   byte+1=0x{b1:02x} (exp nibble={e}) -> {resp['status']} out={o}")
r.close()

# ---- C) map the uniform index via uni_multi (k0..k7 = distinct primes) ----
print("\n## C) uni_multi: sweep the add's byte+1 -> which uniform is selected")
subprocess.run(["./shdump","-o","unimulti.bin","-f","k","uni_multi.metal"], check=True,
               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
um = locate("unimulti.bin"); umb = open("unimulti.bin","rb").read()
uoff = find_falu(umb, um, 0x60)
print(f"   uni_multi falu at main+0x{uoff:x} = {umb[um+uoff:um+uoff+6].hex()}")
primes = [7.0,11.0,13.0,17.0,19.0,23.0,29.0,31.0]
open("pmulti.bin","wb").write(struct.pack("<8f",*primes))
open("a10.bin","wb").write(struct.pack("<f",10.0))
r = PersistRunner(source="uni_multi.metal", function="k", fast_math=False, agxrun_persist="./agxrun_persist")
orig_b1 = umb[um+uoff+1]
print(f"   original byte+1 = 0x{orig_b1:02x}")
for b1 in range(0x00, 0x20):
    sp = bytearray(umb); sp[um+uoff+1] = b1
    open("sp.bin","wb").write(sp)
    resp = r.request(archive="sp.bin", grid=1, tg=1, ins={1:"a10.bin",2:"pmulti.bin"}, outs={0:4}, timeout=6)
    if resp["status"]!="OK":
        print(f"   byte+1=0x{b1:02x} {resp['status']}"); continue
    o = struct.unpack("<f",resp["outs"][0])[0]
    ku = o - 10.0
    which = None
    for i,p in enumerate(primes):
        if abs(ku-p) < 1e-3: which = f"k{i}"
    tag = "  <== ORIG" if b1==orig_b1 else ""
    print(f"   byte+1=0x{b1:02x} out={o:<8g} uniform_val={ku:<8g} {which or ''}{tag}")
r.close()
