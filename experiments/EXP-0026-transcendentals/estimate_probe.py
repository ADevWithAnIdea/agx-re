#!/usr/bin/env python3
# estimate_probe.py -- EXP-0026 (runs ON DEVICE). Reads the RAW output of the
# 0x29 transcendental ESTIMATE op (before Newton-Raphson refinement) by splicing
# the precise kernel's final device_store to read each GPR in turn, then reports
# the register whose value is a low-precision 1/x (rcp) / 1/sqrt(x) (rsqrt) /
# sqrt(x) (sqrt) -- that is the estimate -- and measures its mantissa precision.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are spliced/executed.
import os, sys, math, struct, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse = lm("agxparse", os.path.join(HERE, "agxparse.py"))
persistrun = lm("persistrun", os.path.join(HERE, "persistrun.py"))
import subprocess

WORK = "work"; os.makedirs(WORK, exist_ok=True)

def build(src, fast, func="k"):
    out = os.path.join(WORK, "base.bin")
    cmd = ["./shdump", "-o", out, "-f", func]
    if not fast: cmd.append("--no-fast-math")
    cmd.append(src)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError("shdump: " + r.stderr)
    with open(out, "rb") as f: buf = f.read()
    return out, buf

def f32(raw, i): return struct.unpack_from("<f", raw, i*4)[0]

REF = {"rcp": lambda x: 1.0/x, "rsqrt": lambda x: 1.0/math.sqrt(x), "sqrt": lambda x: math.sqrt(x)}

def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "rcp"
    src = f"kernels/{name}.metal"
    base_path, buf = build(src, fast=False)
    off, length = agxparse.locate_region(buf, "_agc.main")
    _, pieces = agxparse.extract_agx(buf)
    main_b = pieces["_agc.main"]
    # locate the last device_store (0xe7 .. 14B) in _agc.main
    store_rel = None
    i = 0
    while i < len(main_b):
        if main_b[i] == 0xe7:
            store_rel = i
        i += 1
    # find estimate op offset (0x29)
    est_rel = main_b.find(bytes.fromhex("2981"))
    print(f"{name}: mainlen={len(main_b)} est@{est_rel:#x} ({main_b[est_rel:est_rel+6].hex()}) store@{store_rel:#x}")
    src_byte_abs = off + store_rel + 8   # device_store byte+8 = data-source reg descr
    xin = [2.0, 3.0, 4.0, 5.0, 7.0, 9.0, 16.0, 100.0]
    inpath = os.path.join(WORK, "xin.bin")
    with open(inpath, "wb") as f:
        f.write(b"".join(struct.pack("<f", v) for v in xin))
    R = persistrun.PersistRunner(source=src, function="k", fast_math=False,
                                 agxrun_persist="./agxrun_persist")
    orig_descr = main_b[store_rel+8]
    print(f"  store byte+8 (orig data reg descr) = {orig_descr:#04x} (reg {orig_descr>>1}, size {orig_descr&1})")
    print(f"  inputs x = {xin}")
    ref = [REF[name](x) for x in xin]
    print(f"  ref f(x) = {[round(r,6) for r in ref]}")
    for reg in range(0, 48):
        descr = (reg << 1) | 1
        b = bytearray(buf)
        b[src_byte_abs] = descr
        sp = os.path.join(WORK, "sp.bin")
        with open(sp, "wb") as f: f.write(bytes(b))
        resp = R.request(archive=sp, grid=len(xin), tg=len(xin),
                         ins={0: inpath}, outs={1: len(xin)*4}, timeout=8)
        if resp["status"] != "OK":
            print(f"  reg{reg:2d} descr={descr:#04x}: STATUS {resp['status']}")
            continue
        raw = resp["outs"].get(1, b"")
        vals = [f32(raw, k) for k in range(len(xin))]
        # relative error vs f(x) at each input, worst-case bits
        rels = []
        for v, r in zip(vals, ref):
            rels.append(abs(v - r)/abs(r) if (r and math.isfinite(v)) else float('inf'))
        mr = max(rels)
        tag = ""
        if mr < 1e-6: tag = "  <-- FINAL RESULT"
        elif mr < 0.1: tag = f"  <-- ESTIMATE ~{-math.log2(mr):.1f} bits" if mr>0 else "final"
        print(f"  reg{reg:2d} d={descr:#04x}: " + " ".join(f"{v:.6g}" for v in vals) + f"   maxrel={mr:.3e}{tag}")
    R.close()

if __name__ == "__main__":
    main()
