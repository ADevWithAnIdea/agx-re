#!/usr/bin/env python3
# Pair post-submit bo_sigusr1 snapshots by gpu_va between two iotrace dump dirs and
# report which BO carries the tile-dispatch delta (small, localized diffs = control stream).
import sys, os, re, glob

def load(d):
    m = {}
    for f in glob.glob(os.path.join(d, 'bo_sigusr1_*.hex')):
        mm = re.search(r'_va([0-9a-f]+)_cpu[0-9a-f]+_sz([0-9a-f]+)\.hex', f)
        if not mm: continue
        va = int(mm.group(1), 16)
        words = bytearray()
        for line in open(f):
            if line.startswith('#'): continue
            if ':' not in line: continue
            for w in line.split(':', 1)[1].split():
                words += int(w, 16).to_bytes(4, 'little')
        m[va] = (f, bytes(words))
    return m

A = load(sys.argv[1]); B = load(sys.argv[2])
common = sorted(set(A) & set(B))
print(f'{len(A)} A BOs, {len(B)} B BOs, {len(common)} common vas\n')
for va in common:
    fa, da = A[va]; fb, db = B[va]
    n = min(len(da), len(db))
    diffs = []
    for off in range(0, n, 4):
        wa = da[off:off+4]; wb = db[off:off+4]
        if wa != wb:
            diffs.append((off, int.from_bytes(wa,'little'), int.from_bytes(wb,'little')))
    tag = ''
    if len(da) != len(db): tag = f' [size A={len(da):#x} B={len(db):#x}]'
    if 0 < len(diffs) <= 80:
        print(f'== va={va:#x} sz={len(da):#x}  {len(diffs)} word-diffs{tag} ==')
        for off, wa, wb in diffs:
            print(f'  +{off:#06x}: {wa:#010x} -> {wb:#010x}')
    elif len(diffs) > 80:
        print(f'== va={va:#x} sz={len(da):#x}  {len(diffs)} word-diffs (BULK, likely data){tag} ==')
