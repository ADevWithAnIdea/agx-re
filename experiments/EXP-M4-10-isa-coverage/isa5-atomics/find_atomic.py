#!/usr/bin/env python3
# Locate the 0x67 atomic op inside an _agc.main hex string and report its byte
# offset, byte+1 (mode), byte+12 (op selector). Uses the project tokenizer to
# find instruction boundaries; only inspects OUR OWN compiled shader bytes.
import sys, os, subprocess, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
AGXISA = os.path.join(ROOT, "tools", "agx-isa", "agxisa.py")

def tokenize(mainhex):
    r = subprocess.run(["python3", AGXISA, "tokenize", mainhex],
                       capture_output=True, text=True)
    return r.stdout

def find_atomics(mainhex):
    out = tokenize(mainhex)
    res = []
    for line in out.splitlines():
        m = re.match(r"\s*\+0x([0-9a-fA-F]+)\s+(\S+)\s+([0-9a-fA-F]+)\s", line)
        if not m:
            continue
        off = int(m.group(1), 16)
        mnem = m.group(2)
        raw = m.group(3)
        b = bytes.fromhex(raw)
        if len(b) >= 1 and b[0] == 0x67:
            res.append((off, mnem, raw, b))
    return res

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "?"
    mainhex = sys.argv[2].strip()
    ats = find_atomics(mainhex)
    if not ats:
        print(f"{name}: NO 0x67 atomic found")
    for off, mnem, raw, b in ats:
        b1 = b[1] if len(b) > 1 else None
        b12 = b[12] if len(b) > 12 else None
        b13 = b[13] if len(b) > 13 else None
        print(f"{name}: off=+0x{off:02x} mnem={mnem} len={len(b)} "
              f"byte+1=0x{b1:02x} byte+12=0x{b12:02x} byte+13=0x{b13:02x} "
              f"abs_byte12_off=0x{off+12:02x} raw={raw}")
