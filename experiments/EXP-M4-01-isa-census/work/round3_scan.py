#!/usr/bin/env python3
# round3_scan.py -- census residue round-3 driver. For every kernel, walk the
# stream and print each UNDECODED region together with the instruction that
# precedes it (the likely mis-lengthed culprit) and the residue bytes.
# CLEAN-ROOM: operates only on our own compiled shader bytes.
import sys, os, glob, collections
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
sys.path.insert(0, os.path.join(_REPO, 'tools', 'agx-isa'))
import importlib, isadb

HEXDIRS = {
    'M4':  os.path.join(_REPO, 'experiments', 'EXP-M4-01-isa-census', 'census', 'hex'),
    'A18': os.path.join(_REPO, 'experiments', 'EXP-0036-consolidation-census', 'hex'),
}

def trim_padding(b):
    end = len(b)
    while end >= 2 and b[end-2:end] == b'\x06\x00':
        end -= 2
    return b[:end]

def named_at(buf, off, n):
    L = isadb.instr_length(buf, off)
    if L is None or off + L > n:
        return None, None
    try:
        rec, _ = isadb.decode_one(buf, off)
        return L, rec['mnemonic']
    except ValueError:
        return L, None

def walk(b):
    """Return list of (off, b0, L, mn, status)."""
    recs = []
    off = 0; n = len(b)
    while off < n:
        b0 = b[off]
        L, mn = named_at(b, off, n)
        if L is not None:
            recs.append((off, b0, L, mn, 'named' if mn else 'lenonly'))
            off += L
            continue
        start = off; off += 2
        while off < n:
            L2, mn2 = named_at(b, off, n)
            if mn2 is not None:
                break
            off += 2
        recs.append((start, b0, off-start, None, 'undec'))
    return recs

def main():
    which = sys.argv[1] if len(sys.argv) > 1 else 'M4'
    only = sys.argv[2] if len(sys.argv) > 2 else None
    hexdir = HEXDIRS[which]
    files = sorted(glob.glob(os.path.join(hexdir, '*.hex')))
    total_undec = 0
    culprit_counter = collections.Counter()
    for f in files:
        name = os.path.basename(f)[:-4]
        if only and only not in name:
            continue
        b = trim_padding(bytes.fromhex(open(f).read().strip()))
        recs = walk(b)
        undecs = [r for r in recs if r[4] == 'undec']
        if not undecs:
            continue
        total_undec += len(undecs)
        print(f"\n=== {name} ({len(b)}B)  undec_regions={len(undecs)} ===")
        for i, r in enumerate(recs):
            if r[4] != 'undec':
                continue
            off = r[0]
            # find preceding rec
            prev = recs[recs.index(r)-1] if recs.index(r) > 0 else None
            pv = ''
            if prev:
                pv = f"prev[{prev[4]}] @{prev[0]} L={prev[2]} {prev[3] or '?'} : {b[prev[0]:prev[0]+prev[2]].hex(' ')}"
                culprit_counter[(prev[3] or f'0x{prev[1]:02x}?', prev[1])] += 1
            resid = b[off:off+r[2]]
            print(f"  UNDEC @{off:4d} len={r[2]:2d} b0=0x{r[0] and b[off]:02x}")
            print(f"       {pv}")
            print(f"       RESID: {resid.hex(' ')}")
    print(f"\n### total undec regions ({which}{'/'+only if only else ''}): {total_undec}")
    print("### culprit (op just before an undec region) frequency:")
    for (mn, b0), c in culprit_counter.most_common(20):
        print(f"    {c:3d}x  {mn:24s} (b0=0x{b0:02x})")

if __name__ == '__main__':
    main()
