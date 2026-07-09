#!/usr/bin/env python3
# lenprobe.py -- for a given kernel + start offset, try each candidate length L
# for the (unknown) op at that offset and show how cleanly the REMAINDER
# tokenizes. The correct L is the one where the following bytes decode into a
# long clean run of known ops (anchored-segmentation).
# CLEAN-ROOM: our own compiled shader bytes only.
import sys, os
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

HEXDIRS = {
    'M4':  os.path.join(_REPO, 'experiments', 'EXP-M4-01-isa-census', 'census', 'hex'),
    'A18': os.path.join(_REPO, 'experiments', 'EXP-0036-consolidation-census', 'hex'),
}

def trim_padding(b):
    end = len(b)
    while end >= 2 and b[end-2:end] == b'\x06\x00':
        end -= 2
    return b[:end]

def clean_run(b, off, maxn=8):
    """How many consecutive ops decode cleanly (named or length-only) from off,
    and where it lands."""
    n = len(b); cnt = 0; names = []
    while off < n and cnt < maxn:
        L = isadb.instr_length(b, off)
        if L is None or off + L > n:
            return cnt, off, names
        try:
            rec, _ = isadb.decode_one(b, off)
            names.append(rec['mnemonic'])
        except ValueError:
            names.append(f"len{L}?")
        off += L; cnt += 1
    return cnt, off, names

def main():
    which, kern, off = sys.argv[1], sys.argv[2], int(sys.argv[3], 0)
    path = os.path.join(HEXDIRS[which], kern + '.hex')
    b = trim_padding(bytes.fromhex(open(path).read().strip()))
    print(f"{kern} @{off}: bytes = {b[off:off+24].hex(' ')}")
    print(f"(context before @{off}: {b[max(0,off-8):off].hex(' ')})")
    for L in (2,4,6,8,10,12,14,16):
        if off+L > len(b):
            continue
        cnt, land, names = clean_run(b, off+L, maxn=8)
        print(f"  L={L:2d}: this={b[off:off+L].hex(' '):<48s} -> then {cnt} clean ops to @{land}: {names}")

if __name__ == '__main__':
    main()
