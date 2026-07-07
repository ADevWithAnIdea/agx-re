#!/usr/bin/env python3
# analyze.py — EXP-G1a analysis over the captured BO hexdumps in raw/pick/.
#   G1-a: diff the USC program 0x10000130000 across resource-count sweeps -> bind-word tags.
#   G1-c: correlate sysval variations to USC uniform-preamble words.
#   G1-e: decode the varying-linkage BO 0x10000120000 vs varying count.
# CLEAN-ROOM: operates on captured DATA only. No Apple code inspected.
import glob, os, re, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
# search pick2 (fixed-harness re-run) first, then pick (original sweep)
PICK_DIRS = [os.path.join(HERE, 'raw', 'pick2'), os.path.join(HERE, 'raw', 'pick')]
HEXLINE = re.compile(r'^([0-9a-f]{8}):\s+(.*)$')

def load(path):
    data = bytearray()
    with open(path) as f:
        for line in f:
            if line.startswith('#'):
                continue
            m = HEXLINE.match(line)
            if not m: continue
            off = int(m.group(1), 16)
            b = bytes.fromhex(m.group(2).replace(' ', ''))
            if len(data) < off + len(b):
                data.extend(b'\x00' * (off + len(b) - len(data)))
            data[off:off+len(b)] = b
    return bytes(data)

def pick(tag, va):
    """Return the non-empty capture of BO `va` for `tag` (prefer pick2, then most content)."""
    for pdir in PICK_DIRS:
        best, bestnz = None, -1
        for p in sorted(glob.glob(os.path.join(pdir, f'{tag}__{va}__*.hex'))):
            d = load(p)
            nz = sum(1 for x in d if x)
            if nz > bestnz:
                best, bestnz = d, nz
        if best is not None:
            return best
    return None

def words(d):
    return [int.from_bytes(d[o:o+4], 'little') for o in range(0, len(d)-3, 4)]

def wdiff(a, b, base=0, limit=None, label=('A','B')):
    """Print changed 32-bit words between two byte strings."""
    n = min(len(a), len(b))
    if limit: n = min(n, limit)
    out = []
    for o in range(0, n, 4):
        wa = int.from_bytes(a[o:o+4], 'little')
        wb = int.from_bytes(b[o:o+4], 'little')
        if wa != wb:
            out.append((base+o, wa, wb))
    return out

def hexdump_region(d, start, length, label=''):
    print(f'  --- {label} +{start:#06x}..+{start+length:#06x} ---')
    for o in range(start, min(start+length, len(d)), 16):
        row = d[o:o+16]
        ws = ' '.join(f'{int.from_bytes(row[i:i+4],"little"):08x}' for i in range(0, len(row), 4))
        print(f'    +{o:#06x}: {ws}')

# ---------------------------------------------------------------------------
def cmd_diff(tagA, tagB, va):
    a = pick(tagA, va); b = pick(tagB, va)
    if a is None or b is None:
        print(f'  MISSING {va} for {tagA if a is None else tagB}'); return
    dd = wdiff(a, b)
    print(f'=== USC/BO 0x{va} diff  {tagA} -> {tagB}   ({len(dd)} changed words, sizes {len(a):#x}/{len(b):#x}) ===')
    for off, wa, wb in dd:
        print(f'   +{off:#06x}: {wa:#010x} -> {wb:#010x}   d={wb-wa:+#x}')

def cmd_dump(tag, va, start=0, length=0x260):
    d = pick(tag, va)
    if d is None: print('missing'); return
    hexdump_region(d, start, length, f'{tag} 0x{va}')

def cmd_multidiff(va, tags):
    """Show, for each tag, the words that differ from the first tag (baseline)."""
    base = pick(tags[0], va)
    print(f'=== BO 0x{va}: multidiff vs {tags[0]} ===')
    for t in tags[1:]:
        d = pick(t, va)
        if d is None: print(f'  {t}: MISSING'); continue
        dd = wdiff(base, d)
        print(f'  -- {t}: {len(dd)} changed words, size {len(d):#x} (base {len(base):#x}) --')
        for off, wa, wb in dd[:80]:
            print(f'     +{off:#06x}: {wa:#010x} -> {wb:#010x}')

if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'help'
    if cmd == 'diff':
        cmd_diff(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == 'dump':
        start = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0
        length = int(sys.argv[5], 0) if len(sys.argv) > 5 else 0x260
        cmd_dump(sys.argv[2], sys.argv[3], start, length)
    elif cmd == 'multidiff':
        cmd_multidiff(sys.argv[2], sys.argv[3:])
    else:
        print('usage: analyze.py diff <tagA> <tagB> <va> | dump <tag> <va> [start] [len] | multidiff <va> <tag...>')

def cmd_whichbo(tagA, tagB):
    """For each target BO, report how many 32-bit words changed A->B."""
    vas = ['18000','58000','68000','10000000000','10000100000','10000110000',
           '10000120000','10000130000','10000248000','10000258000','10000268000',
           '10000278000','10000288000']
    print(f'=== which BO changed {tagA} -> {tagB} ===')
    for va in vas:
        a = pick(tagA, va); b = pick(tagB, va)
        if a is None or b is None:
            print(f'  0x{va:<12}: (missing)'); continue
        dd = wdiff(a, b)
        nzA = sum(1 for x in a if x); nzB = sum(1 for x in b if x)
        print(f'  0x{va:<12}: {len(dd):3d} words changed   (nz {nzA:5d}->{nzB:5d}, sz {len(a):#x})')
