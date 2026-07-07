#!/usr/bin/env python3
# dump_alu.py -- EXP-0013. Compile each kernel (OUR OWN MSL), extract _agc.main,
# tokenize structurally, print the ALU-region bytes + whole main hex. Runs ON DEVICE.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are inspected.
import os, sys, subprocess, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse = lm("agxparse", os.path.join(HERE, "agxparse.py"))
probe = lm("probe", os.path.join(HERE, "probe.py"))

def main_of(source, func="k", fast_math=False, workdir="work"):
    os.makedirs(workdir, exist_ok=True)
    base = os.path.join(workdir, "d.bin")
    cmd = ["./shdump", "-o", base, "-f", func]
    if not fast_math: cmd.append("--no-fast-math")
    cmd.append(source)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError("shdump: " + r.stderr)
    with open(base, "rb") as f: buf = f.read()
    _, pieces = agxparse.extract_agx(buf)
    return pieces["_agc.main"]

if __name__ == "__main__":
    fast = "--fast" in sys.argv
    kernels = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not kernels:
        kernels = [f[:-6] for f in sorted(os.listdir("kernels")) if f.endswith(".metal")]
    for k in kernels:
        src = f"kernels/{k}.metal"
        try:
            m = main_of(src, fast_math=fast)
        except Exception as e:
            print(f"\n=== {k} ===\n  ERROR {e}"); continue
        toks = probe.structural_tokens(m)
        alus = [t for t in toks if t[0] == "ALU"]
        seq = " ".join(f"{t[0]}({t[2]})" for t in toks)
        print(f"\n=== {k}  ({'fast' if fast else 'nofast'})  mainlen={len(m)} ===")
        print(f"  toks: {seq}")
        print(f"  main: {m.hex()}")
        for i, a in enumerate(alus):
            print(f"  ALU[{i}] @{a[1]:#x} len={a[2]}  {a[3].hex()}")
