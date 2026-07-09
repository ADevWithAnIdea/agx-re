#!/usr/bin/env python3
# walk.py — instruction-by-instruction walker for a single hex stream, to locate
# the FIRST mis-lengthed instruction (the one right before the first <UNDECODED>).
# CLEAN-ROOM: operates only on our own compiled shader bytes.
import sys, os, glob
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
import isadb

HEXDIR = os.path.join(_REPO, 'experiments', 'EXP-M4-01-isa-census', 'census', 'hex')

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

def walk(name, stop_after_first_undec=False):
    path = os.path.join(HEXDIR, name + '.hex')
    b = trim_padding(bytes.fromhex(open(path).read().strip()))
    n = len(b)
    off = 0
    print(f"=== {name}  ({n} bytes) ===")
    idx = 0
    first_undec = None
    while off < n:
        b0 = b[off]
        L = isadb.instr_length(b, off)
        if L is not None and off + L <= n:
            try:
                rec, _ = isadb.decode_one(b, off)
                mn = rec['mnemonic']
                status = 'named'
            except ValueError:
                mn = '?'
                status = 'lenonly'
            hexb = b[off:off+L].hex(' ')
            print(f"  [{idx:3d}] @{off:4d} L={L:2d} {status:8s} {mn:22s} {hexb}")
            off += L
            idx += 1
            continue
        # undecoded
        if first_undec is None:
            first_undec = off
        # resync
        start = off
        off += 2
        while off < n:
            L2, mn2 = named_at(b, off, n)
            if mn2 is not None:
                break
            off += 2
        span = b[start:start+min(off-start,24)].hex(' ')
        print(f"  [{idx:3d}] @{start:4d} L={off-start:2d} UNDECODED byte0=0x{b0:02x}     {span}")
        idx += 1
        if stop_after_first_undec:
            print(f"  --> FIRST UNDECODED at @{start}, byte0=0x{b0:02x}")
            break
    return first_undec

if __name__ == '__main__':
    names = sys.argv[1:] or ['k_uint_arith']
    stop = False
    if names and names[0] == '--stop':
        stop = True; names = names[1:]
    for nm in names:
        walk(nm, stop_after_first_undec=stop)
        print()
