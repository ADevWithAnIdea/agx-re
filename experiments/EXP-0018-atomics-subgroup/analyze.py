#!/usr/bin/env python3
# EXP-0018 analysis: split each _agc.main into structural pieces and isolate the
# op body (between the input load(s) and the final store). CLEAN-ROOM: operates
# only on hex of OUR OWN compiled shaders.
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools", "agx-isa"))
import isadb

def load_mains(path):
    out = {}
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"): continue
        parts = line.split()
        if len(parts) < 3: continue
        src, fn, hexs = parts[0], parts[1], parts[2]
        out[f"{src}.{fn}"] = hexs
    return out

def tok(hexs):
    buf = bytes.fromhex(hexs)
    recs, leftover = isadb.disassemble(buf)
    return recs, leftover

def fmt_recs(recs):
    parts = []
    for r in recs:
        if "error" in r:
            parts.append(f"<UNK:{r['hex']}>")
        else:
            m = r.get("op_mnemonic") or r["mnemonic"]
            parts.append(f"{m}({r['hex']})")
    return "  ".join(parts)

if __name__ == "__main__":
    mains = load_mains(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "raw", "mains.txt"))
    filt = sys.argv[2] if len(sys.argv) > 2 else ""
    for name, hexs in mains.items():
        if filt and filt not in name: continue
        recs, leftover = tok(hexs)
        clean = leftover == b"" and all("error" not in r for r in recs)
        print(f"\n=== {name}  ({'CLEAN' if clean else 'PARTIAL'}, {len(hexs)//2} bytes) ===")
        print(fmt_recs(recs))
