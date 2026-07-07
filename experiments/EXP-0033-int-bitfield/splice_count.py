#!/usr/bin/env python3
# splice_count.py -- EXP-0033: map the bit-count/scan op-select for the single-op
# family. popcount = 27 05 56.., reverse_bits = a7 04 56.. (8B). Sweep
# (byte0 in {0x27,0xa7}) x (byte+1 in {0x04,0x05}) on the popcnt_u kernel op
# (main+0x12) and read outputs to identify the (byte0 bit7, byte+1) selector.
# CLEAN-ROOM: only our own compiled bytes spliced/executed.
import os, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
intprobe = lm("intprobe", os.path.join(HERE, "intprobe.py"))

def bitrev32(x):
    x &= 0xffffffff; r = 0
    for i in range(32): r = (r << 1) | ((x >> i) & 1)
    return r

A = [0x00000001, 0x0000FF00, 0xF0F0F0F0, 0x80000000]
n = len(A)
p = intprobe.IntProbe("kernels/popcnt_u.metal")
OFF = 0x12
print("base op bytes:", p.main[OFF:OFF+8].hex(), "(expect 2705560002005c04 popcount)")
print("ref popcount   :", [bin(x).count('1') for x in A])
print("ref reverse    :", [bitrev32(x) for x in A])
print("ref clz        :", [ (32 if x==0 else 31-x.bit_length()+1) for x in A])
print()
for b0 in (0x27, 0xa7):
    for b1 in (0x04, 0x05):
        r = p.run({OFF: b0, OFF+1: b1}, {0: ('u', A)}, {1: n}, grid=n, signed=False)
        out = [x & 0xffffffff for x in r[1]]
        print(f"  byte0={b0:#04x} byte+1={b1:#04x} -> {out}  st={r['_status']}")
p.close()
