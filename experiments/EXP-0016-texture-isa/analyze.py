#!/usr/bin/env python3
# EXP-0016 texture-ISA byte-diff analyzer (host-side, operates on OUR OWN
# compiled shader hex only). Aligns/ diffs the _agc.main hex of the texture
# battery and tokenizes with the agx-isa DB where it reaches.
import sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools", "agx-isa"))

def load():
    d = {}
    for line in open(os.path.join(HERE, "raw", "mains.txt")):
        line = line.strip()
        if not line or line.startswith("#"): continue
        p = line.split()
        if p[0] in ("FRAG", "COMP") and len(p) >= 3:
            d[p[0].lower() + ":" + p[1]] = p[2]
    return d

def hx(s): return bytes.fromhex(s)

def col_diff(a, b, name_a="A", name_b="B", width=None):
    """Byte-align two hex strings, print differing byte columns."""
    A, B = hx(a), hx(b)
    n = max(len(A), len(B))
    print(f"  len {name_a}={len(A)}  len {name_b}={len(B)}")
    diffs = []
    for i in range(n):
        x = A[i] if i < len(A) else None
        y = B[i] if i < len(B) else None
        if x != y:
            diffs.append((i, x, y))
    for (i, x, y) in diffs:
        sx = f"{x:02x}" if x is not None else "--"
        sy = f"{y:02x}" if y is not None else "--"
        print(f"    @{i:3d} (0x{i:02x}): {sx} -> {sy}")
    if not diffs:
        print("    (identical)")
    return diffs

def show(a, per=1, label=""):
    A = hx(a)
    print(f"  {label} [{len(A)}B]: " + " ".join(f"{c:02x}" for c in A))

def tokenize(a):
    try:
        import isadb
        toks = isadb.tokenize(hx(a)) if hasattr(isadb, "tokenize") else None
        return toks
    except Exception as e:
        return f"(tokenize err: {e})"

if __name__ == "__main__":
    d = load()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "list":
        for k in sorted(d): print(f"{k:24s} {len(hx(d[k]))}B")
    elif cmd == "diff":
        a, b = sys.argv[2], sys.argv[3]
        col_diff(d[a], d[b], a, b)
    elif cmd == "show":
        show(d[sys.argv[2]], label=sys.argv[2])
    elif cmd == "multi":
        # show a set aligned
        keys = sys.argv[2:]
        maxn = max(len(hx(d[k])) for k in keys)
        for k in keys:
            show(d[k], label=k)
