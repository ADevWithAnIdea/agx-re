#!/usr/bin/env python3
# residue_dump.py -- dump every UNDECODED resync region with full context so each
# can be reverse-engineered by hand. For each region: stage, offset, the decoded
# instruction immediately BEFORE, the raw region bytes (full), and the decoded
# instruction at the resync point AFTER. CLEAN-ROOM: all bytes OWN-SHADER.
import sys, os, glob, hashlib, collections
sys.path.insert(0, '/Users/user/cleanroom_gpu/tools/agx-isa')
import isadb
from census import trim_padding, _named_at, walk, HEXDIR

def main():
    files = sorted(glob.glob(os.path.join(HEXDIR, '*.hex')))
    seen = {}
    regions = []
    for f in files:
        name = os.path.basename(f)[:-4]
        h = open(f).read().strip()
        if not h: continue
        b = trim_padding(bytes.fromhex(h))
        hh = hashlib.sha256(b).hexdigest()
        if hh in seen: continue
        seen[hh] = name
        recs = walk(b)
        for i,(off,b0,L,mn,status) in enumerate(recs):
            if status != 'undecoded': continue
            before = recs[i-1] if i>0 else None
            after  = recs[i+1] if i+1<len(recs) else None
            regions.append((name, off, b0, L, b[off:off+L], before, after, b))
    # group by leading byte0
    regions.sort(key=lambda r:(r[2], r[0], r[1]))
    print(f"TOTAL undecoded regions: {len(regions)}   "
          f"total bytes: {sum(r[3] for r in regions)}")
    print("="*78)
    for (name, off, b0, L, raw, before, after, b) in regions:
        print(f"\n[{name} @ 0x{off:x}]  byte0=0x{b0:02x}  len={L}B")
        if before:
            bo,bb0,bL,bmn,bst = before
            print(f"  BEFORE  0x{bo:x} {bmn or ('<len%d>'%bL)}: {b[bo:bo+bL].hex(' ')}")
        print(f"  UNDEC   {raw.hex(' ')}")
        if after:
            ao,ab0,aL,amn,ast = after
            print(f"  AFTER   0x{ao:x} {amn or ('<len%d>'%aL)}: {b[ao:ao+aL].hex(' ')}")

if __name__ == "__main__":
    main()
