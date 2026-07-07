#!/usr/bin/env python3
# halfpack_val.py -- EXP-0033 Task 5: HW-validate native-half packed ALU (0x10)
# and the pack/unpack conversion ops (pack_float_to_unorm2x16=0x97,
# unpack_unorm2x16_to_float=0x17). half/half2 I/O via raw float16 bytes.
# CLEAN-ROOM: only our own compiled bytes executed.
import os, struct, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
intprobe = lm("intprobe", os.path.join(HERE, "intprobe.py"))

def half2_bytes(pairs):  # list of (lo,hi) -> 4 bytes each
    return b"".join(struct.pack("<ee", a, b) for a, b in pairs)
def rd_half2(h):
    b = bytes.fromhex(h)
    return [struct.unpack_from("<ee", b, i) for i in range(0, len(b), 4)]
def f32_2(pairs):
    return b"".join(struct.pack("<ff", a, b) for a, b in pairs)
def rd_f32_2(h):
    b = bytes.fromhex(h)
    return [struct.unpack_from("<ff", b, i) for i in range(0, len(b), 8)]

PASS=[0]; FAIL=[0]
def check(name, got, exp, tol=None):
    if tol is None:
        ok = got == exp
    else:
        ok = all(abs(g-e) <= tol for gr, er in zip(got, exp) for g, e in zip(gr, er))
    (PASS if ok else FAIL)[0] += 1
    print(f"  [{'OK' if ok else 'FAIL'}] {name:16s} got={got} exp={exp}")

# --- half2 packed add / mul (0x10 native-half ALU, 2 lanes/op) ---
A = [(1.0, 2.0), (3.5, -1.0), (10.0, 0.5)]
B = [(0.5, 0.25), (1.5, 4.0), (-2.0, 8.0)]
n = len(A)
p = intprobe.IntProbe("kernels/half2_add.metal")
r = p.run({}, {0: half2_bytes(A), 1: half2_bytes(B)}, {2: n*1}, grid=n, signed=False); p.close()
check("half2_add", [tuple(round(x,3) for x in t) for t in rd_half2(r["_raw2"])],
      [(a0+b0, a1+b1) for (a0,a1),(b0,b1) in zip(A,B)], tol=0.01)
p = intprobe.IntProbe("kernels/half2_mul.metal")
r = p.run({}, {0: half2_bytes(A), 1: half2_bytes(B)}, {2: n*1}, grid=n, signed=False); p.close()
check("half2_mul", [tuple(round(x,3) for x in t) for t in rd_half2(r["_raw2"])],
      [(a0*b0, a1*b1) for (a0,a1),(b0,b1) in zip(A,B)], tol=0.01)

# --- pack_float_to_unorm2x16 (0x97) ---
F = [(0.0, 1.0), (0.5, 0.25), (1.0, 0.0), (0.75, 0.333)]
m = len(F)
def pack_unorm(x, y):
    q = lambda v: round(min(max(v,0.0),1.0)*65535)
    return (q(x) | (q(y) << 16)) & 0xffffffff
p = intprobe.IntProbe("kernels/pack_unorm2x16.metal")
r = p.run({}, {0: f32_2(F)}, {1: m}, grid=m, signed=False); p.close()
got = [x & 0xffffffff for x in r[1]]
exp = [pack_unorm(x,y) for x,y in F]
check("pack_unorm2x16", got, exp)

# --- unpack_unorm2x16_to_float (0x17) ---
U = [0x00000000, 0xFFFFFFFF, 0x8000_4000, 0x0000_FFFF]
def unpack_unorm(u):
    lo = (u & 0xffff)/65535.0; hi = ((u>>16)&0xffff)/65535.0
    return (lo, hi)
p = intprobe.IntProbe("kernels/unpack_unorm2x16.metal")
r = p.run({}, {0: ('u', U)}, {1: len(U)*2}, grid=len(U), signed=False); p.close()
got = [tuple(round(x,4) for x in t) for t in rd_f32_2(r["_raw1"])]
exp = [tuple(round(x,4) for x in unpack_unorm(u)) for u in U]
check("unpack_unorm2x16", got, exp, tol=1e-3)

print(f"\nTOTAL: {PASS[0]} pass, {FAIL[0]} fail")
