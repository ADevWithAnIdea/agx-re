#!/usr/bin/env python3
# runval.py -- EXP-0033 device-side behaviour validation. Runs each kernel
# UNMODIFIED with known inputs and checks the runtime output matches the
# reference integer/bitfield op. Confirms semantics on the real A18 Pro GPU.
# Uses the IntProbe splice-and-observe harness (one persistent runner/kernel).
# CLEAN-ROOM: only OUR OWN compiled shader bytes are executed.
import os, sys, struct, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
intprobe = lm("intprobe", os.path.join(HERE, "intprobe.py"))

def u32(vals): return b"".join(struct.pack("<I", x & 0xffffffff) for x in vals)
def i32(vals): return b"".join(struct.pack("<i", x) for x in vals)
def u64(vals): return b"".join(struct.pack("<Q", x & 0xffffffffffffffff) for x in vals)
def i64(vals): return b"".join(struct.pack("<q", x) for x in vals)
def rd_u32(res, idx): return [x & 0xffffffff for x in res[idx]]
def rd_u64(raw_hex):
    b = bytes.fromhex(raw_hex)
    return [struct.unpack_from("<Q", b, i)[0] for i in range(0, len(b), 8)]

PASS = 0; FAIL = 0
def check(name, got, exp):
    global PASS, FAIL
    ok = got == exp
    if ok: PASS += 1
    else: FAIL += 1
    print(f"  [{'OK' if ok else 'FAIL'}] {name:18s} got={got} exp={exp}")

def run(kernel, ins, outs, grid, signed=True):
    p = intprobe.IntProbe(f"kernels/{kernel}.metal")
    r = p.run({}, ins, outs, grid=grid, signed=signed)
    p.close()
    return r

def bitrev32(x):
    x &= 0xffffffff; r = 0
    for i in range(32):
        r = (r << 1) | ((x >> i) & 1)
    return r
def clz32(x):
    x &= 0xffffffff
    if x == 0: return 32
    n = 0
    for i in range(31, -1, -1):
        if (x >> i) & 1: break
        n += 1
    return n
def ctz32(x):
    x &= 0xffffffff
    if x == 0: return 32
    n = 0
    for i in range(32):
        if (x >> i) & 1: break
        n += 1
    return n

def main():
    A = [0x00000001, 0x80000000, 0x0000FF00, 0xF0F0F0F0, 0x00000000, 0x7FFFFFFF]
    n = len(A)
    # ---- Task 1: bit count / scan ----
    print("== Task 1: bit-count / scan ==")
    r = run("popcnt_u", {0: ('u', A)}, {1: n}, n, signed=False)
    check("popcount", rd_u32(r, 1), [bin(x).count('1') for x in A])
    r = run("clz_u", {0: ('u', A)}, {1: n}, n, signed=False)
    check("clz", rd_u32(r, 1), [clz32(x) for x in A])
    r = run("ctz_u", {0: ('u', A)}, {1: n}, n, signed=False)
    check("ctz", rd_u32(r, 1), [ctz32(x) for x in A])
    r = run("revbits_u", {0: ('u', A)}, {1: n}, n, signed=False)
    check("reverse_bits", rd_u32(r, 1), [bitrev32(x) for x in A])

    # ---- Task 2: bitfield ----
    print("== Task 2: bitfield extract/insert ==")
    B = [0xABCDEF12, 0x0000FF00, 0x12345678, 0xFFFFFFFF]
    m = len(B)
    r = run("extr_u_imm", {0: ('u', B)}, {1: m}, m, signed=False)
    check("extract_u(4,8)", rd_u32(r, 1), [(x >> 4) & 0xFF for x in B])
    # signed extract: sign-extend an 8-bit field at offset 4
    def sext(x, off, cnt):
        f = (x >> off) & ((1 << cnt) - 1)
        if f & (1 << (cnt - 1)): f -= (1 << cnt)
        return f
    r = run("extr_s_imm", {0: ('u', B)}, {1: m}, m, signed=True)
    check("extract_s(4,8)", r[1], [sext(x, 4, 8) for x in B])
    # insert_bits(base, insert, 3, 5): replace bits [3,8) of base with low5 of insert
    base = [0x00000000, 0xFFFFFFFF, 0x12345678, 0xAAAAAAAA]
    ins_ = [0x1F, 0x00, 0x15, 0x0A]
    def insbits(bs, ins, off, cnt):
        mask = ((1 << cnt) - 1) << off
        return ((bs & ~mask) | ((ins << off) & mask)) & 0xffffffff
    r = run("insert_imm", {0: ('u', base), 1: ('u', ins_)}, {2: 4}, 4, signed=False)
    check("insert(3,5)", rd_u32(r, 2), [insbits(bs, i, 3, 5) for bs, i in zip(base, ins_)])

    # ---- Task 3: rotate ----
    print("== Task 3: rotate ==")
    RA = [0x00000001, 0x80000001, 0x12345678, 0xF0000000]
    RN = [1, 4, 8, 4]
    def rotl(x, n): n &= 31; return ((x << n) | (x >> ((32 - n) & 31))) & 0xffffffff if n else x & 0xffffffff
    r = run("rotl_var", {0: ('u', RA), 1: ('u', RN)}, {2: 4}, 4, signed=False)
    check("rotate(a,n)", rd_u32(r, 2), [rotl(x, nn) for x, nn in zip(RA, RN)])
    r = run("rotl_imm", {0: ('u', RA)}, {1: 4}, 4, signed=False)
    check("rotate(a,5)", rd_u32(r, 1), [rotl(x, 5) for x in RA])

    # ---- Task 4: min3/max3/median3/clamp ----
    print("== Task 4: min3/max3/median3/clamp ==")
    P = [3, 10, -5, 7]; Q = [5, 2, -1, 7]; R3 = [1, 8, -9, 0]
    r = run("min3", {0: P, 1: Q, 2: R3}, {3: 4}, 4)
    check("min3", r[3], [min(a, b, c) for a, b, c in zip(P, Q, R3)])
    r = run("max3", {0: P, 1: Q, 2: R3}, {3: 4}, 4)
    check("max3", r[3], [max(a, b, c) for a, b, c in zip(P, Q, R3)])
    r = run("median3", {0: P, 1: Q, 2: R3}, {3: 4}, 4)
    check("median3", r[3], [sorted([a, b, c])[1] for a, b, c in zip(P, Q, R3)])
    lo = [0, 0, -3, 5]; hi = [4, 4, 3, 6]; xv = [-1, 10, 0, 8]
    r = run("clamp_i", {0: xv, 1: lo, 2: hi}, {3: 4}, 4)
    check("clamp_i", r[3], [max(l, min(x, h)) for x, l, h in zip(xv, lo, hi)])

    # ---- Task 6: 64-bit integer ----
    print("== Task 6: 64-bit integer ==")
    LA = [0x1_0000_0001, 0xFFFF_FFFF, 0x1234_5678_9ABC, 0x8000_0000_0000_0000]
    LB = [0x0_0000_0002, 0x0000_0001, 0x1000_0000_0001, 0x0000_0000_0000_0001]
    k = len(LA)
    def run64(kernel, ins, nout_u64, grid):
        p = intprobe.IntProbe(f"kernels/{kernel}.metal")
        r = p.run({}, ins, {list(_outidx(kernel))[0]: nout_u64 * 2}, grid=grid, signed=False)
        p.close()
        return r
    def _outidx(kernel):
        return {"u64_add": [2], "u64_sub": [2], "u64_mul": [2], "u64_shl": [2],
                "u64_shr": [2], "u64_from32": [2]}[kernel]
    for kernel, fn in [("u64_add", lambda a, b: (a + b) & ((1 << 64) - 1)),
                       ("u64_sub", lambda a, b: (a - b) & ((1 << 64) - 1)),
                       ("u64_mul", lambda a, b: (a * b) & ((1 << 64) - 1))]:
        p = intprobe.IntProbe(f"kernels/{kernel}.metal")
        r = p.run({}, {0: u64(LA), 1: u64(LB)}, {2: k * 2}, grid=k, signed=False)
        p.close()
        got = rd_u64(r["_raw2"])
        check(kernel, [hex(x) for x in got], [hex(fn(a, b)) for a, b in zip(LA, LB)])
    # 64-bit shifts
    SN = [1, 4, 33, 63]
    p = intprobe.IntProbe("kernels/u64_shl.metal")
    r = p.run({}, {0: u64(LA), 1: ('u', SN)}, {2: k * 2}, grid=k, signed=False); p.close()
    check("u64_shl", [hex(x) for x in rd_u64(r["_raw2"])],
          [hex((a << (s & 63)) & ((1 << 64) - 1)) for a, s in zip(LA, SN)])
    p = intprobe.IntProbe("kernels/u64_shr.metal")
    r = p.run({}, {0: u64(LA), 1: ('u', SN)}, {2: k * 2}, grid=k, signed=False); p.close()
    check("u64_shr", [hex(x) for x in rd_u64(r["_raw2"])],
          [hex(a >> (s & 63)) for a, s in zip(LA, SN)])
    # 64-bit compare
    p = intprobe.IntProbe("kernels/u64_cmp.metal")
    r = p.run({}, {0: u64(LA), 1: u64(LB)}, {2: k}, grid=k, signed=False); p.close()
    check("u64_cmp(<)", rd_u32(r, 2), [1 if a < b else 0 for a, b in zip(LA, LB)])
    # 32x32->64 widening mul
    WA = [0xFFFF_FFFF, 0x1_0000, 12345, 0x8000_0000]
    WB = [0xFFFF_FFFF, 0x1_0000, 100000, 2]
    p = intprobe.IntProbe("kernels/u64_from32.metal")
    r = p.run({}, {0: ('u', WA), 1: ('u', WB)}, {2: 4 * 2}, grid=4, signed=False); p.close()
    check("u64_from32(mul)", [hex(x) for x in rd_u64(r["_raw2"])],
          [hex(a * b) for a, b in zip(WA, WB)])

    print(f"\nTOTAL: {PASS} pass, {FAIL} fail")

if __name__ == "__main__":
    main()
