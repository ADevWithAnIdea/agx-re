#!/usr/bin/env python3
# EXP-0038: verify the PROPOSED length-rule / gating fixes cleanly tokenize the
# previously-undecoded streams, WITHOUT editing tools/agx-isa. We wrap the real
# isadb.instr_length with the proposed additions and re-walk the problem streams.
# CLEAN-ROOM: operates only on our own compiled shader bytes + the read-only DB.
import sys, os
sys.path.insert(0, '/Users/user/cleanroom_gpu/tools/agx-isa')
import isadb

_orig_len = isadb.instr_length

def patched_len(buf, off=0):
    b0 = buf[off]
    b1 = buf[off+1] if off+1 < len(buf) else -1
    b2 = buf[off+2] if off+2 < len(buf) else -1
    # FIX A: 0x07 link save/restore (non-leaf frame) is an 8-byte op (byte+1==0x00,
    # byte+4==0x81), distinct from the 6-byte threadgroup_barrier/pixel_order
    # (byte+1 in {0x04,0x14}). The current rule lengths BOTH as 6 -> mis-tokenizes.
    if b0 == 0x07 and b2 == 0x54:
        if b1 == 0x00:
            return 8            # link register save/restore to scratch (EXP-0038)
        return 6                # threadgroup_barrier / pixel_order
    # FIX B: 0x6f non-leaf frame prologue = 6 bytes.
    if b0 == 0x6f:
        return 6
    # FIX C: 0x32 u64 carry-generate = 6 bytes (compare-family carry op; byte+2==0x35).
    if b0 == 0x32:
        return 6
    # FIX D: simd/quad reduce cache-bit -- accept byte+2 in {0x54,0x56} (bit17 = the
    # cache/last-use hint). Current rule gates on ==0x56 only, so min/max/logical
    # reductions (which come out 0x54) fall through with no length.
    if b0 in (0xbf, 0x3f, 0xb7) and (b2 & ~0x02) == 0x54:
        return 8
    # FIX E: 0x18 half-lane pack (compute) = 4 bytes. (half2 assemble before store.)
    if b0 == 0x18:
        return 4
    return _orig_len(buf, off)

isadb.instr_length = patched_len

# --- FIX D2 (descriptor MATCH): let the cache bit (instr bit17 = byte+2 bit1) be
# a don't-care for the byte+2-gated ops, so BOTH the 0x54 and 0x56 variants NAME.
# Replace the exact `(16,8,0x56)` match with `(16,1,0)+(18,6,0x15)` (bit17 free).
def _relax_cache_bit(mnem):
    for d in isadb.DB:
        if d['mnemonic'] == mnem:
            newm = []
            for (s, w, v) in d['match']:
                if s == 16 and w == 8 and v == 0x56:
                    newm.append((16, 1, 0)); newm.append((18, 6, 0x15))
                else:
                    newm.append((s, w, v))
            d['match'] = newm
for _m in ('simd_reduce', 'unpack_convert', 'pack_convert'):
    _relax_cache_bit(_m)

def named_at(buf, off, n):
    L = isadb.instr_length(buf, off)
    if L is None or off + L > n: return None, None
    try:
        rec, _ = isadb.decode_one(buf, off); return L, rec['mnemonic']
    except ValueError: return L, None

def tok(name, hexs):
    buf = bytes.fromhex(hexs.replace(' ', ''))
    while len(buf) >= 2 and buf[-2:] == b'\x06\x00': buf = buf[:-2]
    off, n, leftover = 0, len(buf), False
    print(f'\n== {name} ({n} bytes) ==')
    while off < n:
        L, mn = named_at(buf, off, n)
        if L is None:
            print(f'  +{off:#05x} UNDECODED (byte0={buf[off]:#04x}) {buf[off:].hex()}'); leftover = True; break
        print(f'  +{off:#05x} b0={buf[off]:#04x} b2={(buf[off+2] if off+2<n else 0):#04x} len={L:2d} {mn or "<length-only>"}  {buf[off:off+L].hex()}')
        off += L
    print('  RESULT:', 'CLEAN (0 leftover)' if (off == n and not leftover) else 'LEFTOVER')

# problem streams captured from OUR OWN compiled kernels (EXP-0038 raw dumps):
tok('u64add _agc.main (0x32 carry chain)',
    '5ca01006671054060005200059010040480067004402010520005901004048009f01560003041aa815053201350322810500'
    '20809f015402030820a817059f015402020c08881705e7005400020521001900001012000e000000')
# non-leaf mid() region, truncated just before the final 10-byte extended-falu
# (`a9 15 18 01 ef 02 54 00 00 50` -- the pre-existing unsolved 10B falu form, NOT
# an EXP-0038 target) + the 8f12 non-leaf ret, to show the FRAME ops tokenize clean.
tok('non-leaf mid() frame ops (0x6f prologue + 0x07 link save/restore x2 + calls)',
    '6f03040000201b94210007005400810000000f05541a8f10546affffffffff000f06040200000700540081ff1f000b142900'
    'ab02210007005400810000000f05541a8f00547effffffffff000f06040200000700540081ff1f00')
# and confirm the 8-byte 0x07 link save + restore + 4-byte 8f12 non-leaf ret:
tok('0x07 link save (8B) + link restore (8B) + non-leaf ret 8f12 (4B)',
    '0700540081000000' + '0700540081ff1f00' + '8f125400')
tok('reduce_two region (simd_sum 0x56 + simd_max 0x54 cache-bit)',
    'bf01560003081601bf035404030814039f015400020800a81705')
# real k_unpack1 op is `17 04 56 00 00 00 1c ca ..`; flip byte+2 0x56->0x54 (the
# cache/last-use hint) to make the census 0x54 variant and show it still NAMES.
# real k_unpack1 op = 17 04 56 00 00 00 1c ca e7 00 (10B); flip byte+2 0x56->0x54:
tok('unpack cache-bit variant: real unpack op byte+2 0x56->0x54 + stop',
    '1704540000001ccae700' + '0e000000')
tok('h2add _agc.main (0x18 half-pack)',
    '0ca010066710540200002000490100404600670044040100200049010040460010041c0200c018051803'
    'e7005402020021000900009011000e000000')
