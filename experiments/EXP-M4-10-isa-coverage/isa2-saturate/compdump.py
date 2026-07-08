#!/usr/bin/env python3
# compdump.py — compile OUR OWN MSL to an archive and dump _agc.main hex.
# Clean-room: only our own compiled shader bytes are inspected. Uses shdump +
# agxparse (our tools). No GPU run, no Apple binary introspection.
#
#   python3 compdump.py SRC.metal [-f FUNC] [--no-fast-math]
#   -> prints "MAIN <hex>"
import os, sys, subprocess, hashlib, importlib.util, argparse

ROOT = "/Users/user/cleanroom_gpu"
SHDUMP = os.path.join(ROOT, "tools/agxtest/shdump")
AGXPARSE = os.path.join(ROOT, "tools/shdump/agxparse.py")
WORK = os.path.join(ROOT, "experiments/EXP-M4-10-isa-coverage/_work")

def load_agxparse():
    spec = importlib.util.spec_from_file_location("agxparse", AGXPARSE)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

def compile_main(src, func, fast_math):
    os.makedirs(WORK, exist_ok=True)
    with open(src, "rb") as f: sb = f.read()
    tag = hashlib.sha256(sb + str(fast_math).encode() + (func or "").encode()).hexdigest()[:12]
    out = os.path.join(WORK, f"a_{tag}.bin")
    cmd = [SHDUMP, "-o", out]
    if func: cmd += ["-f", func]
    if not fast_math: cmd += ["--no-fast-math"]
    cmd += [src]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        raise RuntimeError(f"shdump failed:\n{r.stderr}")
    ap = load_agxparse()
    with open(out, "rb") as f: buf = f.read()
    _, pieces = ap.extract_agx(buf)
    return pieces["_agc.main"]

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("-f", "--function", default="k")
    p.add_argument("--no-fast-math", action="store_true")
    a = p.parse_args()
    mb = compile_main(a.src, a.function, not a.no_fast_math)
    print("MAIN " + mb.hex())
