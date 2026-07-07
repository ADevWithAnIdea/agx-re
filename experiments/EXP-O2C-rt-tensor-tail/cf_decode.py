#!/usr/bin/env python3
# EXP-O2C task 6: HW splice-and-observe decode of the 0xcf matrix-MAC operand
# selectors. Locates the single 0xcf in mad_f32, splices each field, runs on the
# real A18 GPU with distinct known A,B,C, and classifies the output against every
# candidate matrix product. CLEAN-ROOM: only our own compiled+spliced bytes run.
import os, struct, subprocess, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse = lm("agxparse", os.path.join(HERE, "agxparse.py"))
PR = lm("persistrun", os.path.join(HERE, "persistrun.py")).PersistRunner

def pf(v): return b"".join(struct.pack('<f', float(x)) for x in v)
def uf(r, n): return [struct.unpack_from('<f', r, k*4)[0] for k in range(n)]
def mm(X, Y, Z, N=8):
    R = [0.0]*(N*N)
    for i in range(N):
        for j in range(N):
            s = Z[i*N+j]
            for k in range(N): s += X[i*N+k]*Y[k*N+j]
            R[i*N+j] = s
    return R
def cl(R, E, t=1e-2): return len(R) == len(E) and all(abs(a-b) <= t*(1+abs(b)) for a, b in zip(R, E))

N = 8
A = [float((i*8+j) % 7 - 3) for i in range(N) for j in range(N)]
B = [float(((i*3+j*5) % 9) - 4) for i in range(N) for j in range(N)]
C = [float(10+i*8+j) for i in range(N) for j in range(N)]
Z = [0.0]*(N*N)
# candidate products to classify against
CAND = {
    "A*B+C": mm(A, B, C), "A*B": mm(A, B, Z),
    "B*A+C": mm(B, A, C), "B*A": mm(B, A, Z),
    "A*A+C": mm(A, A, C), "A*A": mm(A, A, Z),
    "B*B+C": mm(B, B, C), "B*B": mm(B, B, Z),
    "C*B+C": mm(C, B, C), "A*C+C": mm(A, C, C),
    "C":     C[:],        "A":   A[:], "B": B[:],
    "zero":  Z[:],
}
def classify(R):
    if not R: return "(no-out)"
    for name, E in CAND.items():
        if cl(R, E): return name
    return "OTHER r[0:4]=" + str([round(x, 1) for x in R[:4]])

src = os.path.join(HERE, "kernels", "tensor.metal")
base = os.path.join(HERE, "work", "cf_mad.bin")
os.makedirs(os.path.join(HERE, "work"), exist_ok=True)
subprocess.run(["./shdump", "-o", base, "-f", "mad_f32", "--no-fast-math", src],
               check=True, capture_output=True, text=True, cwd=HERE)
buf = open(base, "rb").read()
off, length = agxparse.locate_region(buf, "_agc.main")
main = buf[off:off+length]
cf = main.find(bytes.fromhex("cf0256"))
cfbytes = main[cf:cf+12]
print(f"0xcf @ main+{cf}: {cfbytes.hex()}")
print(f"          +0 +1 +2 +3 +4 +5 +6 +7 +8 +9 +10 +11")
print(f"  bytes:  " + " ".join(f"{x:02x}" for x in cfbytes))

runner = PR(source=src, function="mad_f32", fast_math=False, agxrun_persist="./agxrun_persist")
def run(splices):
    b = bytearray(buf)
    for mo, v in splices.items(): b[off+cf+mo] = v
    arch = os.path.join(HERE, "work", "cf_sp.bin"); open(arch, "wb").write(b)
    ip = {}
    for idx, v in {0: A, 1: B, 2: C}.items():
        p = os.path.join(HERE, "work", f"cf_{idx}.bin"); open(p, "wb").write(pf(v)); ip[idx] = p
    r = runner.request(archive=arch, grid=32, tg=32, ins=ip, outs={3: N*N*4}, timeout=12)
    R = uf(r["outs"][3], N*N) if r["status"] == "OK" else []
    return r["status"], classify(R)

TESTS = [
    ("baseline",                {}),
    # operand A/B (multiply left/right) -- hypothesis +5=left(A), +6=right(B)
    ("+5 04->08 (left->b reg)",  {5: 0x08}),
    ("+6 08->04 (right->a reg)", {6: 0x04}),
    ("+5/+6 swap (b*a)",         {5: 0x08, 6: 0x04}),
    ("+5 04->00",                {5: 0x00}),
    ("+6 08->00",                {6: 0x00}),
    ("+5 04->09 (left->c reg)",  {5: 0x09}),
    ("+6 08->09 (right->c reg)", {6: 0x09}),
    # C accumulator (EXP-0022: +7)
    ("+7 09->00 (C->reg0)",      {7: 0x00}),
    ("+7 09->04 (C->a reg)",     {7: 0x04}),
    # accumulate-enable (EXP-0022: +11 bit0)
    ("+11 01->00 (acc off)",     {11: 0x00}),
    # dst (+8 candidate)
    ("+8 d4->00",                {8: 0x00}),
    ("+8 d4->d6",                {8: 0xd6}),
    # +3/+4 (unknown, constant across a/b/c swaps)
    ("+3 02->00",                {3: 0x00}),
    ("+3 02->04",                {3: 0x04}),
    ("+4 00->02",                {4: 0x02}),
    # +9/+10
    ("+9 43->41",                {9: 0x41}),
    ("+10 24->00",               {10: 0x00}),
    # dtype / mode
    ("+1 02->00 (dtype f16?)",   {1: 0x00}),
    ("+2 56->54 (mode tiled)",   {2: 0x54}),
]
try:
    for label, sp in TESTS:
        st, cls = run(sp)
        print(f"  {label:28s} status={st:12s} -> {cls}")
finally:
    runner.close()
