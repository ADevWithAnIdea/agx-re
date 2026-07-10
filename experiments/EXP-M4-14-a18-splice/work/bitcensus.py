#!/usr/bin/env python3
# Bit-level "not-fully-named" census over a hex corpus, using the merged
# tools/agx-isa length rule + descriptor DB. For each resync token, split its
# bits into:
#   named       : match bits + non-raw typed field bits (fully specified)
#   raw         : bits covered by a field typed "raw"
#   length_only : a token whose length is known but NO descriptor matched
#   desync      : an undecoded resync span (no length)
# not-fully-named % = (raw + length_only + desync) / total bits.
#
# Usage: bitcensus.py <hexdir> [--trim]
import sys, os, glob
sys.path.insert(0, '/Users/user/asahi_re/public/gpu/tools/agx-isa')
import importlib, isadb
importlib.reload(isadb)

def trim_padding(b):
    end = len(b)
    while end >= 2 and b[end-2:end] == b'\x06\x00':
        end -= 2
    return b[:end]

def named_at(buf, off, n):
    L = isadb.instr_length(buf, off)
    if L is None or off + L > n:
        return None, None, None
    try:
        rec, _ = isadb.decode_one(buf, off)
        return L, rec['mnemonic'], rec
    except ValueError:
        return L, None, None

def desc_bit_class(mnem, L):
    """Return per-bit class array for a NAMED token: 'named' or 'raw'."""
    d = isadb._BY_MNEM[mnem]
    nbits = L * 8
    cls = ['raw'] * nbits   # default: any bit not otherwise covered = raw (undocumented)
    for (start, width, _v) in d['match']:
        for i in range(start, start + width):
            if i < nbits: cls[i] = 'named'
    for f in d['fields']:
        c = 'named' if f['type'] != 'raw' else 'raw'
        for i in range(f['start'], f['start'] + f['width']):
            if i < nbits:
                # match already-named wins; a raw field over a match bit stays named
                if cls[i] == 'named' and c == 'raw':
                    continue
                cls[i] = c
    return cls

def census(hexdir, trim):
    files = sorted(glob.glob(os.path.join(hexdir, '*.hex')))
    tot = named = raw = lenonly = desync = 0
    nfiles = 0
    for fp in files:
        try:
            h = open(fp).read().strip()
            if not h: continue
            b = bytes.fromhex(h)
        except Exception:
            continue
        if trim: b = trim_padding(b)
        n = len(b)
        if n == 0: continue
        nfiles += 1
        off = 0
        while off < n:
            L, mn, rec = named_at(b, off, n)
            if L is not None:
                bits = L * 8
                tot += bits
                if mn is not None:
                    cls = desc_bit_class(mn, L)
                    nnamed = cls.count('named'); nraw = bits - nnamed
                    named += nnamed; raw += nraw
                else:
                    lenonly += bits
                off += L
                continue
            # desync span: skip 2-byte parcels to next named boundary
            start = off
            off += 2
            while off < n:
                L2, mn2, _ = named_at(b, off, n)
                if mn2 is not None: break
                off += 2
            span = (off - start) * 8
            tot += span; desync += span
    nfn = raw + lenonly + desync
    return dict(files=nfiles, tot=tot, named=named, raw=raw, lenonly=lenonly,
                desync=desync, nfn=nfn, pct=(100.0*nfn/tot if tot else 0.0))

def report(label, r):
    print(f"[{label}] files={r['files']} total_bits={r['tot']}")
    print(f"    named={r['named']} raw={r['raw']} length_only={r['lenonly']} desync={r['desync']}")
    print(f"    NOT-FULLY-NAMED = {r['nfn']}/{r['tot']} = {r['pct']:.4f}%")

if __name__ == '__main__':
    OWN = '/Users/user/asahi_re/public/gpu/experiments/EXP-M4-13-full-corpus/hex'
    TP  = '/Users/user/asahi_re/public/gpu/experiments/EXP-M4-13-full-corpus/thirdparty_hex'
    trim = '--trim' in sys.argv
    print("=== bit-level not-fully-named census (trim=%s) ===" % trim)
    report('own', census(OWN, trim))
    report('thirdparty', census(TP, trim))
