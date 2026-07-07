#!/usr/bin/env python3
# validate.py -- EXP-0026 (runs ON DEVICE). Compile OUR OWN MSL (fast + precise),
# run on the real A18 Pro GPU with known inputs, read back, and report the ULP
# error of the full lowered sequence vs a double-precision reference. Also used
# to read the RAW ESTIMATE via a store-source splice (--splice).
# CLEAN-ROOM: only OUR OWN compiled shader bytes are executed. No Apple binary
# is disassembled.
import os, sys, math, struct, subprocess, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse = lm("agxparse", os.path.join(HERE, "agxparse.py"))

WORK = "work"; os.makedirs(WORK, exist_ok=True)

def compile_arch(src, fast, func="k"):
    tag = ("fast" if fast else "prec") + "_" + os.path.basename(src).replace(".metal", "")
    out = os.path.join(WORK, "a_" + tag + ".bin")
    cmd = ["./shdump", "-o", out, "-f", func]
    if not fast: cmd.append("--no-fast-math")
    cmd.append(src)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError("shdump: " + r.stderr)
    return out

def splice_file(arch, splices):
    with open(arch, "rb") as f: buf = bytearray(f.read())
    for sym, off, hexb in splices:
        loc = agxparse.locate_region(bytes(buf), sym)
        base, length = loc
        nb = bytes.fromhex(hexb)
        buf[base+off:base+off+len(nb)] = nb
    out = arch.replace(".bin", "_sp.bin")
    with open(out, "wb") as f: f.write(bytes(buf))
    return out

def run(arch, src, ins, nout_bytes, grid, fast, func="k", outidx=None):
    # ins: {idx: list-of-floats}; write files
    cmd = ["./agxrun", "--archive", arch, "--source", src, "--function", func,
           "--grid", str(grid), "--tg", str(grid)]
    if not fast: cmd.append("--no-fast-math")
    for idx, vals in ins.items():
        p = os.path.join(WORK, f"in_{idx}.bin")
        with open(p, "wb") as f:
            f.write(b"".join(struct.pack("<f", float(v)) for v in vals))
        cmd += ["--buf", f"{idx}={p}"]
    if outidx is None:
        outidx = max(ins.keys()) + 1
    cmd += ["--out", f"{outidx}={nout_bytes}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    out = {}
    status = "?"
    for ln in r.stdout.splitlines():
        if ln.startswith("STATUS "): status = ln.split(None,1)[1]
        elif ln.startswith("OUT "):
            _, idx, hx = ln.split(None, 2); out[int(idx)] = bytes.fromhex(hx)
    return status, out, outidx

def f32(raw, i): return struct.unpack_from("<f", raw, i*4)[0]
def bits(x): return struct.unpack("<I", struct.pack("<f", float(x)))[0]
def ord_key(x):
    b = bits(x)
    return (b ^ 0x80000000) if (b & 0x80000000)==0 else (~b & 0xffffffff)
def ulp(got, ref):
    # ulp distance between two float32 (as fp32-rounded reference)
    reff = struct.unpack("<f", struct.pack("<f", ref))[0]
    if math.isnan(got) or math.isnan(reff): return float('nan')
    return abs(ord_key(got) - ord_key(reff))

# reference functions (double precision)
REF = {
    "rcp":   lambda a,b: 1.0/a, "fast_rcp": lambda a,b: 1.0/a, "prec_rcp": lambda a,b: 1.0/a,
    "rsqrt": lambda a,b: 1.0/math.sqrt(a), "fast_rsqrt": lambda a,b: 1.0/math.sqrt(a),
    "prec_rsqrt": lambda a,b: 1.0/math.sqrt(a),
    "sqrt":  lambda a,b: math.sqrt(a), "fast_sqrt": lambda a,b: math.sqrt(a),
    "prec_sqrt": lambda a,b: math.sqrt(a),
    "sin": lambda a,b: math.sin(a), "cos": lambda a,b: math.cos(a), "tan": lambda a,b: math.tan(a),
    "fast_sin": lambda a,b: math.sin(a), "fast_cos": lambda a,b: math.cos(a),
    "prec_sin": lambda a,b: math.sin(a),
    "exp2": lambda a,b: 2.0**a, "log2": lambda a,b: math.log2(a),
    "expe": lambda a,b: math.exp(a), "loge": lambda a,b: math.log(a),
    "exp10": lambda a,b: 10.0**a, "log10": lambda a,b: math.log10(a),
    "fast_exp2": lambda a,b: 2.0**a, "fast_log2": lambda a,b: math.log2(a),
    "prec_exp2": lambda a,b: 2.0**a, "prec_log2": lambda a,b: math.log2(a),
    "div": lambda a,b: a/b, "fast_div": lambda a,b: a/b,
    "pow": lambda a,b: a**b, "powr": lambda a,b: a**b,
    "fast_pow": lambda a,b: a**b, "prec_pow": lambda a,b: a**b,
}
TWO_ARG = {"div","pow","powr","fast_pow","prec_pow","fast_div"}

# input vectors
AIN = {
    "default": [1.0, 2.0, 3.0, 4.0, 0.5, 0.1, 10.0, 100.0],
    "trig":    [math.pi/6, math.pi/3, math.pi/4, math.pi/2, 1.0, -1.0, 3.0, 6.28318],
    "exp":     [0.0, 1.0, 2.0, 3.0, 10.0, -1.0, 0.5, -3.0],
    "log":     [1.0, 2.0, 2.718281828, 8.0, 10.0, 0.5, 100.0, 1000.0],
    "pos":     [1.0, 2.0, 3.0, 4.0, 9.0, 16.0, 0.25, 1000000.0],
}

def pick_in(name):
    if name in ("sin","cos","tan","fast_sin","fast_cos","prec_sin"): return AIN["trig"]
    if name in ("exp2","expe","exp10","fast_exp2","prec_exp2"): return AIN["exp"]
    if name in ("log2","loge","log10","fast_log2","prec_log2"): return AIN["log"]
    if name in ("sqrt","rsqrt","fast_sqrt","fast_rsqrt","prec_sqrt","prec_rsqrt"): return AIN["pos"]
    return AIN["default"]

def do(name, fast, splices=None):
    src = f"kernels/{name}.metal"
    arch = compile_arch(src, fast)
    if splices: arch = splice_file(arch, splices)
    a = pick_in(name)
    n = len(a)
    two = name in TWO_ARG
    if two:
        b = [2.0, 3.0, 0.5, 2.0, 10.0, 0.5, 3.0, -2.0]
        ins = {0: a, 1: b}
    else:
        b = [0.0]*n
        ins = {0: a}
    status, out, outidx = run(arch, src, ins, n*4, n, fast)
    if status != "OK":
        print(f"  {name:12s} {'fast' if fast else 'prec'}: STATUS {status}")
        return
    raw = out[outidx]
    print(f"  {name:12s} {'fast' if fast else 'prec'}:")
    ref = REF[name]
    maxulp = 0
    for i in range(n):
        got = f32(raw, i)
        r = ref(a[i], b[i] if two else 0.0)
        u = ulp(got, r)
        if not math.isnan(u): maxulp = max(maxulp, u)
        av = f"{a[i]:.6g}" + (f",{b[i]:.6g}" if two else "")
        print(f"     f({av:>16s}) = {got:.9g}   ref={r:.9g}   ulp={u}")
    print(f"     -> max ULP = {maxulp}")

if __name__ == "__main__":
    fast = "--fast" in sys.argv
    prec = "--prec" in sys.argv
    if not fast and not prec: fast = prec = True
    names = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not names:
        names = ["rcp","rsqrt","sqrt","div","sin","cos","tan","exp2","log2",
                 "expe","loge","exp10","log10","pow","powr",
                 "fast_rcp","fast_rsqrt","fast_sqrt","prec_rcp","prec_rsqrt","prec_sqrt"]
    for nm in names:
        if fast: do(nm, True)
        if prec: do(nm, False)
