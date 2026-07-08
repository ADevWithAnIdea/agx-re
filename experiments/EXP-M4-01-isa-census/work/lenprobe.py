#!/usr/bin/env python3
# lenprobe.py -- for a given kernel + start offset, try each candidate length L
# for the (unknown) op at that offset and show how cleanly the REMAINDER
# tokenizes. The correct L is the one where the following bytes decode into a
# long clean run of known ops (anchored-segmentation).
# CLEAN-ROOM: our own compiled shader bytes only.
import sys, os
sys.path.insert(0, '/Users/user/cleanroom_gpu/tools/agx-isa')
import isadb

HEXDIRS = {
    'M4':  '/Users/user/cleanroom_gpu/experiments/EXP-M4-01-isa-census/census/hex',
    'A18': '/Users/user/cleanroom_gpu/experiments/EXP-0036-consolidation-census/hex',
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
