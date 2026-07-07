#!/usr/bin/env python3
# splice_u64.py -- EXP-0033: is the single-op u64 subtract a NATIVE 64-bit
# register-pair op? Splice u64_sub's isub (byte0 0x1f at main+0x20) -> iadd
# (0x9f) and test whether ONE op does 64-bit ADD with carry across the 32-bit
# boundary. Decisive: input low words that carry into the high word.
# CLEAN-ROOM: only our own compiled bytes spliced/executed.
import os, struct, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
intprobe = lm("intprobe", os.path.join(HERE, "intprobe.py"))
def u64(vals): return b"".join(struct.pack("<Q", x & (2**64-1)) for x in vals)
def rd_u64(h):
    b = bytes.fromhex(h); return [struct.unpack_from("<Q", b, i)[0] for i in range(0, len(b), 8)]

# carry cases: low-word add overflows -> must propagate to high word
LA = [0x0000_0000_FFFF_FFFF, 0x0000_0001_FFFF_FFFF, 0x1234_5678_9ABC_DEF0, 0xFFFF_FFFF_FFFF_FFFF]
LB = [0x0000_0000_0000_0001, 0x0000_0000_0000_0002, 0x0000_0000_8765_4321, 0x0000_0000_0000_0001]
k = len(LA)

p = intprobe.IntProbe("kernels/u64_sub.metal")
# locate the subtract op: from analysis it is at main offset 0x20 (0x1f byte0)
off = 0x20
main = p.main
print("byte at main+0x20 =", hex(main[off]), "(expect 0x1f isub)")

# 1) baseline (unmodified subtract) sanity
r = p.run({}, {0: u64(LA), 1: u64(LB)}, {2: k*2}, grid=k, signed=False)
print("SUB   got =", [hex(x) for x in rd_u64(r["_raw2"])])
print("SUB   exp =", [hex((a-b) & (2**64-1)) for a,b in zip(LA,LB)])

# 2) splice 0x1f -> 0x9f (subtract -> add): does ONE op do 64-bit add w/ carry?
r = p.run({off: 0x9f}, {0: u64(LA), 1: u64(LB)}, {2: k*2}, grid=k, signed=False)
got = [hex(x) for x in rd_u64(r["_raw2"])]
exp_native = [hex((a+b) & (2**64-1)) for a,b in zip(LA,LB)]
exp_lo32only = [hex((((a+b) & 0xffffffff) | (a & ~0xffffffff))) for a,b in zip(LA,LB)]
print("SPLICE add status =", r["_status"])
print("ADD   got =", got)
print("ADD   exp(native64) =", exp_native)
print("ADD   exp(lo32only) =", exp_lo32only)
print("=> NATIVE 64-bit" if got == exp_native else
      ("=> 32-bit only (no carry)" if got == exp_lo32only else "=> OTHER"))
p.close()
