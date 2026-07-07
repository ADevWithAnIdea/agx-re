#!/usr/bin/env python3
# dump_seq.py -- EXP-0026 (runs ON DEVICE). Compile OUR OWN MSL, extract
# _agc.main, and walk it with the agx-isa DB, printing each instruction. When
# the DB does not know an opcode (e.g. the transcendental ESTIMATE op) it is
# flagged UNKNOWN and the remaining bytes are printed grouped in 2-byte parcels
# so the estimate-op encoding can be read off by hand.
# CLEAN-ROOM: only OUR OWN compiled shader bytes are inspected.
import os, sys, subprocess, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))

def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse = lm("agxparse", os.path.join(HERE, "agxparse.py"))
isadb    = lm("isadb", os.path.join(HERE, "isadb.py"))

# Provisional lengths for candidate estimate opcodes so the walk can continue
# past them (refined once the real length is confirmed from the byte stream).
PROVISIONAL = {}   # byte0 -> length (bytes)

def instr_len(buf, off):
    b0 = buf[off]
    if b0 in PROVISIONAL:
        return PROVISIONAL[b0]
    return isadb.instr_length(buf, off)

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

EST = {0x09: "frcp_est", 0x0b: "frsqrt_est", 0x0d: "fsqrt_est"}

def label(main, off, L):
    b0 = main[off]
    chunk = bytes(main[off:off+L])
    # explicit estimate-op labelling: byte0 0x29, subop at byte+3
    if b0 == 0x29 and L == 6:
        return EST.get(main[off+3], f"est?{main[off+3]:#04x}")
    try:
        rec, _ = isadb.decode_one(chunk, 0)
        mn = rec.get("op_mnemonic") or rec.get("mnemonic") or "?"
        if "error" in rec: mn = "ERR"
        return mn
    except Exception:
        return f"raw{b0:#04x}"

def walk(main):
    off = 0; n = len(main); out = []
    unk = None
    while off < n:
        L = instr_len(main, off)
        if L is None or off + L > n:
            # accumulate unknown parcels; try to resync at the next known op
            if unk is None: unk = off
            off += 2
            continue
        if unk is not None:
            blob = main[unk:off]
            parcels = " ".join(blob[i:i+2].hex() for i in range(0, len(blob), 2))
            out.append(("??", unk, len(blob), blob.hex(), parcels))
            unk = None
        mn = label(main, off, L)
        out.append((mn, off, L, bytes(main[off:off+L]).hex(), ""))
        off += L
    if unk is not None:
        blob = main[unk:]
        parcels = " ".join(blob[i:i+2].hex() for i in range(0, len(blob), 2))
        out.append(("??", unk, len(blob), blob.hex(), parcels))
    return out

if __name__ == "__main__":
    fast = "--fast" in sys.argv
    # allow --prov BYTE0:LEN to inject a provisional length for the walk
    for a in sys.argv[1:]:
        if a.startswith("--prov"):
            _, spec = a.split("=", 1)
            b0s, ls = spec.split(":")
            PROVISIONAL[int(b0s, 0)] = int(ls, 0)
    kernels = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not kernels:
        kernels = [f[:-6] for f in sorted(os.listdir("kernels")) if f.endswith(".metal")]
    for k in kernels:
        src = f"kernels/{k}.metal"
        try:
            m = main_of(src, fast_math=fast)
        except Exception as e:
            print(f"\n=== {k} ===\n  ERROR {e}"); continue
        toks = walk(m)
        print(f"\n=== {k}  ({'fast' if fast else 'nofast'})  mainlen={len(m)} ===")
        print(f"  main: {m.hex()}")
        for mn, off, L, hx, note in toks:
            line = f"  @{off:#05x} {L:2d}B  {mn:14s} {hx}"
            if note: line += "   " + note
            print(line)
