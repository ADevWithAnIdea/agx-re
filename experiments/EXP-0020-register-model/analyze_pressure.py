#!/usr/bin/env python3
# Analyze the pressure dump: tokenize each _agc.main, count memory ops, and find
# the maximum register index used across register operand fields. Detects spill
# onset (jump in memory-op count / total length).
import sys, os, importlib.util
# --- portable repo root (repo was relocated; anchor to a sentinel, not a hardcoded path) ---
import os
def _repo_root(start):
    d = os.path.abspath(start)
    while d != os.path.dirname(d):
        if os.path.isfile(os.path.join(d, 'CLAUDE.md')) and os.path.isdir(os.path.join(d, 'tools', 'agx-isa')):
            return d
        d = os.path.dirname(d)
    raise RuntimeError('repo root not found from ' + start)
_REPO = _repo_root(os.path.dirname(os.path.abspath(__file__)))
# --- end portable repo root ---
ISA = os.path.join(_REPO, 'tools', 'agx-isa')
sys.path.insert(0, ISA)
import isadb

# Register-operand field names per mnemonic whose value is (reg<<1)|size or a raw
# reg byte; we recover reg = value>>1 for byte-typed operand fields.
REG_BYTE_FIELDS = {
    "falu2":  [("srcA_reg", False), ("srcB_reg", False), ("dst", True)],  # dst is 4-bit nibble (reg direct)
    "falu2i": [("srcA_reg", False), ("dst", True)],
    "falu3":  [("dst", False), ("srcA", False), ("srcB", False), ("srcC", False)],
    "fminmax":[("dst", False), ("srcA", False)],
    "iadd2":  [("dst", False)],
    "imad":   [("dst", False)],
    "iminmax":[("dst", False), ("srcA", False), ("srcB", False)],
}

def maxreg_from_bytes(hexs):
    """Heuristic: scan all instructions; for byte-typed reg operands compute
    reg=byte>>1; also scan every raw operand byte>>1 as a candidate (upper bound).
    Return (maxreg_decoded, maxreg_anybyte, nmem, ninstr, clean)."""
    buf = bytes.fromhex(hexs)
    recs, leftover = isadb.disassemble(buf)
    nmem = 0; ninstr = 0; maxreg = -1
    for r in recs:
        if r.get("error"):
            break
        ninstr += 1
        mn = r["mnemonic"]
        if mn in ("device_load", "device_store", "atomic_rmw", "atomic_mem"):
            nmem += 1
        f = r.get("fields", {})
        for name, is_direct in REG_BYTE_FIELDS.get(mn, []):
            if name in f:
                v = f[name]
                reg = v if is_direct else (v >> 1)
                if reg > maxreg:
                    maxreg = reg
    return maxreg, nmem, ninstr, (leftover == b"")

def main():
    path = sys.argv[1]
    lines = open(path).read().splitlines()
    print("%-6s %-8s %-6s %-6s %-6s %-8s" % ("K","MAINLEN","NINSTR","NMEM","MAXREG","CLEAN"))
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("K=") and i+1 < len(lines) and lines[i+1].startswith("HEX "):
            K = int(ln.split()[0][2:])
            mainlen = int(ln.split("LEN=")[1])
            hexs = lines[i+1][4:].strip()
            maxreg, nmem, ninstr, clean = maxreg_from_bytes(hexs)
            print("%-6d %-8d %-6d %-6d %-6d %-8s" % (K, mainlen, ninstr, nmem, maxreg, clean))
            i += 2
        else:
            i += 1

if __name__ == "__main__":
    main()
