#!/usr/bin/env python3
# analyze2.py -- EXP-M5-02 disambiguation pass.
# For each undecoded byte0 leader, record the histogram of the NAMED mnemonic that
# immediately PRECEDES it, and the length distribution of the undecoded region.
# A dominant predecessor => the "unknown byte0" is really the mis-parsed TAIL of a
# length-changed named op (length delta), not a brand-new leader. A flat/absent
# predecessor distribution => candidate genuinely-new leader.
# CLEAN-ROOM: operates only on hex of our own compiled shaders + the G17P DB.
import sys, os, glob, hashlib, collections
sys.path.insert(0, os.path.expanduser('~/cleanroom_work/tools/agx-isa'))
import isadb
HEXDIR = os.path.expanduser('~/cleanroom_work/EXP-M5-02/hex')

def trim_padding(b):
    end = len(b)
    while end >= 2 and b[end-2:end] == b'\x06\x00':
        end -= 2
    return b[:end]

def _named_at(buf, off, n):
    L = isadb.instr_length(buf, off)
    if L is None or off + L > n:
        return None, None
    try:
        rec, _ = isadb.decode_one(buf, off)
        return L, rec['mnemonic']
    except ValueError:
        return L, None

def walk(buf):
    recs = []; off = 0; n = len(buf)
    while off < n:
        b0 = buf[off]
        L, mn = _named_at(buf, off, n)
        if L is not None:
            recs.append((off, b0, L, mn, 'named' if mn else 'length_only')); off += L; continue
        start = off; off += 2
        while off < n:
            L2, mn2 = _named_at(buf, off, n)
            if mn2 is not None: break
            off += 2
        recs.append((start, b0, off - start, None, 'undecoded'))
    return recs

pred = collections.defaultdict(collections.Counter)   # undec byte0 -> Counter(prev_mnemonic)
lens = collections.defaultdict(collections.Counter)    # undec byte0 -> Counter(region_len)
seen = set()
for f in sorted(glob.glob(os.path.join(HEXDIR, '*.hex'))):
    h = open(f).read().strip()
    if not h: continue
    b = trim_padding(bytes.fromhex(h))
    if not b: continue
    hh = hashlib.sha256(b).hexdigest()
    if hh in seen: continue
    seen.add(hh)
    recs = walk(b)
    for i, (off, b0, L, mn, st) in enumerate(recs):
        if st == 'undecoded':
            prev = recs[i-1] if i > 0 else None
            pm = (prev[3] or ('lenonly:0x%02x'%prev[1])) if prev else '<start>'
            pred[b0][pm] += 1
            lens[b0][L] += 1

TARGETS = [0x3e,0xb7,0x01,0x32,0xa0,0xfe,0x20,0x5e,0xbe,0x02,0x42,0x9e,0xa8,0x07,0xe0,0x38,0x1e,0x3f,0xa1,0x30]
for g in TARGETS:
    tot = sum(pred[g].values())
    print("byte0=0x%02x  undec_regions=%d" % (g, tot))
    print("   top preceding NAMED op: " + ", ".join("%s=%d"%(m,c) for m,c in pred[g].most_common(4)))
    print("   region-length dist:     " + ", ".join("%dB:%d"%(l,c) for l,c in lens[g].most_common(5)))
