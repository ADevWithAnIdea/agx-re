#!/usr/bin/env python3
# EXP-O2C structural analyzer. Tokenizes each _agc.main with the validated G17P
# length rule (tools/agx-isa/isadb, READ-ONLY) plus the EXP-0023 RT length
# extensions, then counts the RT / matrix opcode groups, detects traversal
# back-edges, and reports coverage. CLEAN-ROOM: OUR OWN compiled bytes only.
import sys, importlib.util
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
spec = importlib.util.spec_from_file_location(
    "isadb", os.path.join(_REPO, 'tools', 'agx-isa', 'isadb.py'))
isadb = importlib.util.module_from_spec(spec); spec.loader.exec_module(isadb)

def B(b, o): return b[o] if 0 <= o < len(b) else -1

# EXP-0023 RT length extensions layered on the validated isadb.instr_length.
def L(b, o):
    b0 = b[o]; lo = b0 & 0x0f
    if lo == 0x0b:
        return 10 if B(b, o+2) in (0x0e, 0x1e, 0x1f) else 4
    if lo == 0x4 and B(b, o+1) == 0xea: return 8          # rt_intersect
    if lo == 0x4: return 8                                 # RT setup/move (X4)
    if b0 == 0xdf: return 14                               # rt_as_load
    if b0 == 0x5f and B(b, o+2) in (0x54, 0x56): return 14 # RT 0x5f mem sibling
    if lo == 0xf and b0 not in (0x0f, 0x8f, 0x6f, 0xdf, 0xcf) and B(b, o+2) in (0x54, 0x56):
        return 14                                          # other lo-f mem siblings
    if b0 == 0x10: return 8 if (B(b, o+2) & 0x02) else 6
    if b0 in (0x07, 0x87, 0x97) and B(b, o+2) != 0x56: return 6
    v = isadb.instr_length(b, o)
    if v is not None: return v
    if lo == 0x2 and B(b, o+2) == 0x27: return 10          # RT transform/test
    return None

def tok(b):
    o = 0; recs = []; resync = 0; uncov = 0
    while o < len(b):
        Lv = L(b, o)
        if Lv is not None and o+Lv <= len(b):
            recs.append((o, b[o], Lv)); o += Lv; continue
        # resync: scan forward to a position that tokenizes >=4 in a row
        start = o; oo = o+2
        while oo < len(b):
            if L(b, oo) is not None:
                c = 0; p = oo
                while p < len(b) and c < 4:
                    q = L(b, p)
                    if q is None or p+q > len(b): break
                    p += q; c += 1
                if c >= min(4, (len(b)-oo)//2 or 1): break
            oo += 2
        resync += 1; uncov += oo-start
        recs.append((-1, b[start], oo-start)); o = oo
    return recs, resync, uncov

def analyze(fn, h):
    b = bytes.fromhex(h)
    recs, resync, uncov = tok(b)
    counts = {}
    rt4 = df = f5 = tr2 = movb = 0
    backj = []
    for (o, b0, Lv) in recs:
        if o < 0: continue
        counts[b0] = counts.get(b0, 0)+1
        if (b0 & 0x0f) == 0x4 and B(b, o+1) == 0xea: rt4 += 1
        if b0 == 0xdf: df += 1
        if b0 == 0x5f: f5 += 1
        if (b0 & 0x0f) == 0x2 and B(b, o+2) == 0x27: tr2 += 1
        if (b0 & 0x0f) == 0xb and B(b, o+2) in (0x80, 0x81): movb += 1
        if b0 == 0x0f and Lv == 10 and B(b, o+1) == 0x00 and B(b, o+2) == 0x54:
            off = int.from_bytes(b[o+3:o+8], 'little', signed=True)
            if off < 0: backj.append(off)
    cf = counts.get(0xcf, 0)
    cov = 100*(len(b)-uncov)/len(b)
    return dict(bytes=len(b), cf=cf, rt4=rt4, df=df, f5=f5, tr2=tr2, movb=movb,
                backj=backj, cov=cov, resync=resync, counts=counts)

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "raw/mains.txt"
    want = [a for a in sys.argv[2:] if not a.startswith('-')]
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'): continue
        p = line.split()
        if len(p) < 3: continue
        grp, fn, h = p[0], p[1], p[-1]
        if want and grp not in want and fn not in want: continue
        if not all(c in '0123456789abcdef' for c in h.lower()):
            print(f"{grp:8s} {fn:16s} {h}"); continue
        a = analyze(fn, h)
        print(f"{grp:7s} {fn:16s} {a['bytes']:6d}B cov={a['cov']:5.1f}% rs={a['resync']:2d} | "
              f"0xcf={a['cf']:4d} RT(x4/ea)={a['rt4']:2d} 0xdf={a['df']:2d} 0x5f={a['f5']:2d} "
              f"rt2/27={a['tr2']:2d} raymov={a['movb']:2d} backj={len(a['backj'])} {a['backj'][:3]}")

if __name__ == "__main__":
    main()
