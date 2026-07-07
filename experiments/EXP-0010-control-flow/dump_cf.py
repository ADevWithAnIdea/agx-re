#!/usr/bin/env python3
# dump_cf.py -- EXP-0010. Compile each control-flow kernel (OUR OWN MSL), extract
# _agc.main + _agc.main.constant_program + whole __text, print hex, run the
# agx-isa tokenizer over _agc.main and report where it breaks (candidate
# control-flow opcodes = byte0 groups the DB does not yet know). Runs ON DEVICE.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are inspected.
import os, sys, subprocess, importlib.util, collections

HERE = os.path.dirname(os.path.abspath(__file__))

def load_mod(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m

agxparse = load_mod("agxparse", os.path.join(HERE, "agxparse.py"))
isadb = None
ip = os.path.join(HERE, "isadb.py")
if os.path.exists(ip):
    isadb = load_mod("isadb", ip)

def pieces_of(source, func="k", fast_math=False, workdir="work"):
    os.makedirs(workdir, exist_ok=True)
    base = os.path.join(workdir, "d.bin")
    cmd = ["./shdump", "-o", base, "-f", func]
    if not fast_math: cmd.append("--no-fast-math")
    cmd.append(source)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0: raise RuntimeError("shdump: " + r.stderr)
    with open(base, "rb") as f: buf = f.read()
    _, pieces = agxparse.extract_agx(buf)
    return pieces

# Known-good opcode length table copy so this works even if isadb absent.
def tokenize_report(main):
    if isadb is None:
        return "(no isadb)"
    recs, leftover = isadb.disassemble(main)
    seq = " ".join((r.get("op_mnemonic") or r["mnemonic"]) for r in recs if "error" not in r)
    tail = ""
    if leftover:
        bad = recs[-1]
        tail = f"  [BREAK @ byte0={leftover[0]:#04x} leftover={leftover.hex()[:40]}...]"
    return seq + tail

if __name__ == "__main__":
    fast = "--fast" in sys.argv
    kernels = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not kernels:
        kernels = [f[:-6] for f in sorted(os.listdir("kernels")) if f.endswith(".metal")]
    unknown_hist = collections.Counter()
    for k in kernels:
        src = f"kernels/{k}.metal"
        try:
            pieces = pieces_of(src, fast_math=fast)
        except Exception as e:
            print(f"{k:12s}: ERROR {e}"); continue
        main = pieces.get("_agc.main", b"")
        cp = pieces.get("_agc.main.constant_program", b"")
        whole = pieces.get("__whole_text__", b"")
        print(f"\n=== {k}  ({'fast' if fast else 'nofast'})  mainlen={len(main)} cplen={len(cp)} wholelen={len(whole)} ===")
        print(f"  const_program: {cp.hex()}")
        print(f"  main:          {main.hex()}")
        print(f"  tokens:        {tokenize_report(main)}")
        # histogram of byte0 at instruction starts we can walk; if tokenizer
        # breaks, record the break byte0.
        if isadb is not None:
            recs, leftover = isadb.disassemble(main)
            if leftover:
                unknown_hist[leftover[0]] += 1
    if unknown_hist:
        print("\n=== candidate control-flow byte0 groups (tokenizer break points) ===")
        for b0, c in unknown_hist.most_common():
            print(f"  byte0 {b0:#04x}: {c} kernels")
