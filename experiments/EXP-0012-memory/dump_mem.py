#!/usr/bin/env python3
# dump_mem.py -- EXP-0012 memory-family byte extractor. Runs ON DEVICE.
# For each kernel: compile OUR OWN MSL (shdump), extract _agc.main +
# constant_program, print a structural breakdown (device load 0x67 / store 0xe7 /
# other opcodes) and dump full hex to raw/. No GPU dispatch here -- pure
# compilation + our own Mach-O parser. CLEAN-ROOM: only our own bytes.
import os, sys, subprocess, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def lm(n, p):
    s = importlib.util.spec_from_file_location(n, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse = lm("agxparse", os.path.join(HERE, "agxparse.py"))

SHDUMP = os.path.join(HERE, "shdump")
KDIR = os.path.join(HERE, "kernels")
RAW = os.path.join(HERE, "raw")
os.makedirs(RAW, exist_ok=True)
os.makedirs(os.path.join(HERE, "work"), exist_ok=True)

# length rule for the instrs we care about + best-effort skip for others
def instr_len(main, off):
    b0 = main[off]; lo = b0 & 0x0f
    if b0 == 0x0e: return 4
    if lo == 0x0c: return 4
    if b0 in (0x67, 0xe7): return 14
    if lo == 0x09: return 8 if (off+2 < len(main) and main[off+2] & 0x02) else 6
    if lo == 0x0b: return 10
    if b0 in (0x9f, 0x1f, 0xa7): return 10 if (main[off+1] & 1) else 12
    if b0 == 0x27: return 8
    if b0 == 0x02: return 6
    if b0 == 0x12: return 14 if (main[off+2] & 0x0f) == 0x0d else 6
    if b0 == 0x0a: return 6
    if b0 in (0x05, 0x16): return 4
    if b0 == 0x0f and off+1 < len(main) and main[off+1] == 0x00: return 10
    return None

def tokenize(main):
    """Greedy tokenize; on unknown opcode, emit a '?' token of 2 bytes and continue."""
    toks = []; off = 0; n = len(main)
    while off < n:
        L = instr_len(main, off)
        if L is None or off + (L or 0) > n:
            # unknown: grab 2 bytes as a parcel and mark
            toks.append(("?", off, 2, bytes(main[off:off+2])))
            off += 2
            continue
        b0 = main[off]
        name = {0x67:"dev_load",0xe7:"dev_store",0x0e:"stop"}.get(b0)
        if name is None:
            lo = b0 & 0x0f
            name = {0x0c:"get_sr"}.get(lo, f"op{b0:02x}")
        toks.append((name, off, L, bytes(main[off:off+L])))
        off += L
    return toks

def dump(name, funcs=("k",), extra=()):
    src = os.path.join(KDIR, name + ".metal")
    out = {}
    for fn in funcs:
        base = os.path.join(HERE, "work", f"{name}.bin")
        cmd = [SHDUMP, "-o", base, "-f", fn, "--no-fast-math"] + list(extra) + [src]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(base):
            print(f"[{name}] shdump FAILED: {r.stderr.strip()[:200]}"); return None
        with open(base, "rb") as f: buf = f.read()
        _, pieces = agxparse.extract_agx(buf)
        if not pieces:
            print(f"[{name}] no AGX"); return None
        main = pieces.get("_agc.main", b"")
        cp = pieces.get("_agc.main.constant_program", b"")
        out["main"] = main; out["cp"] = cp
        with open(os.path.join(RAW, f"{name}.main.hex"), "w") as f: f.write(main.hex())
        with open(os.path.join(RAW, f"{name}.cp.hex"), "w") as f: f.write(cp.hex())
        print(f"\n=== {name}  (main {len(main)}B) ===")
        print("  main:", main.hex())
        toks = tokenize(main)
        for (tn, off, L, b) in toks:
            print(f"    [{off:3d}] {tn:10s} {b.hex()}")
        # summary: count loads/stores + list any non-standard mem opcodes
        loads = [t for t in toks if t[0]=="dev_load"]
        stores = [t for t in toks if t[0]=="dev_store"]
        others = sorted(set(t[0] for t in toks if t[0].startswith("op") or t[0]=="?"))
        print(f"  SUMMARY: dev_load x{len(loads)}, dev_store x{len(stores)}, other={others}")
    return out

if __name__ == "__main__":
    names = sys.argv[1:] or [
        "copy1","off1","off2","off4","str2","str4","offn",
        "ld_char","ld_uchar","ld_short","ld_ushort","ld_long","st_char","st_short",
        "copyf","vec2","vec3","vec4","vec2i","vec4i",
        "tg_copy","tg_shift","tg_shift1",
        "const_copy","const_idx","scalaru","atomic_add",
    ]
    for nm in names:
        try: dump(nm)
        except Exception as e:
            import traceback; print(f"[{nm}] EXC:"); traceback.print_exc()
