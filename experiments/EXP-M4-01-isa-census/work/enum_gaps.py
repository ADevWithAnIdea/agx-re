#!/usr/bin/env python3
# enum_gaps.py -- across the whole census corpus, enumerate every UNDECODED region's
# leading-op signature (byte0..byte+5). Because the previous op was cleanly lengthed,
# the region start IS a real instruction boundary, so these bytes are the true head of
# an op instr_length() returns None for. Group by signature to batch the fixes.
# CLEAN-ROOM: our own compiled shader bytes only.
import sys, os, glob, collections
sys.path.insert(0, '/Users/user/cleanroom_gpu/tools/agx-isa')
import isadb

HEXDIR = '/Users/user/cleanroom_gpu/experiments/EXP-M4-01-isa-census/census/hex'

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

sig_count = collections.Counter()
sig_where = collections.defaultdict(list)
sig_sample = {}
for f in sorted(glob.glob(os.path.join(HEXDIR, '*.hex'))):
    name = os.path.basename(f)[:-4]
    h = open(f).read().strip()
    if not h: continue
    b = trim_padding(bytes.fromhex(h)); n = len(b); off = 0
    while off < n:
        L = isadb.instr_length(b, off)
        if L is not None and off + L <= n:
            off += L; continue
        start = off; b0 = b[off]; off += 2
        while off < n:
            L2, mn2 = named_at(b, off, n)
            if mn2 is not None: break
            off += 2
        # signature = first 3 bytes of the region (the true op head)
        sig = tuple(b[start:start+3])
        sig_count[sig] += 1
        sig_where[sig].append(name)
        sig_sample.setdefault(sig, b[start:start+16].hex(' '))
        # also record region length for the FIRST region of a sig
        if sig not in sig_sample or True:
            pass

print("=== undecoded-region leading-op signatures (byte0 byte1 byte2), by frequency ===")
for sig, c in sig_count.most_common():
    kernels = collections.Counter(sig_where[sig])
    kl = ",".join(f"{k}x{v}" if v>1 else k for k,v in kernels.most_common(4))
    print(f"  {sig[0]:02x} {sig[1]:02x} {sig[2]:02x}  n={c:3d}  [{kl}]  sample: {sig_sample[sig]}")
