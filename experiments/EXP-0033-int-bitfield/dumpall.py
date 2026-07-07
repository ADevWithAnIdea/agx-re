#!/usr/bin/env python3
# dumpall.py -- EXP-0033 device-side: compile every kernels/*.metal with shdump,
# extract _agc.main (+ constant_program) AGX bytes with agxparse, emit hex.
# Records compile failures (e.g. an MSL builtin that does not exist) as negatives.
# CLEAN-ROOM: only OUR OWN MSL compiled; only our own bytes inspected.
import os, sys, glob, subprocess, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))

def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

agxparse = load_mod("agxparse", os.path.join(HERE, "agxparse.py"))

KD = os.path.join(HERE, "kernels")
WORK = os.path.join(HERE, "work"); os.makedirs(WORK, exist_ok=True)
SHDUMP = os.path.join(HERE, "shdump")

def dump_one(src):
    name = os.path.splitext(os.path.basename(src))[0]
    arch = os.path.join(WORK, name + ".bin")
    cmd = [SHDUMP, "-o", arch, "-f", "k", "--no-fast-math", src]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(arch):
        err = (r.stderr or r.stdout or "").strip().replace("\n", " | ")
        return name, None, None, f"COMPILE_FAIL: {err[:400]}"
    with open(arch, "rb") as f:
        buf = f.read()
    try:
        _, pieces = agxparse.extract_agx(buf)
    except Exception as e:
        return name, None, None, f"EXTRACT_FAIL: {e}"
    main = pieces.get("_agc.main")
    const = pieces.get("_agc.main.constant_program")
    mh = main.hex() if main else None
    ch = const.hex() if const else None
    return name, mh, ch, "OK"

def main():
    srcs = sorted(glob.glob(os.path.join(KD, "*.metal")))
    for src in srcs:
        name, mh, ch, status = dump_one(src)
        print(f"KERNEL {name}")
        print(f"STATUS {status}")
        if mh is not None:
            print(f"MAIN {mh}")
        if ch is not None:
            print(f"CONST {ch}")
        print("ENDK")
        sys.stdout.flush()

if __name__ == "__main__":
    main()
