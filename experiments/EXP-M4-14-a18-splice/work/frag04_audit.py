#!/usr/bin/env python3
# Audit the b0==0x04 & byte+1!=0xea -> 8 length rule (isadb.py ~1403) for
# OVER-CONSUMPTION. For every position where that rule fires (token decodes as
# frag_pos_read / op04_len8), record byte+2 and whether the current length-8
# boundary AND candidate shorter boundaries (2/4/6) land on a descriptor-NAMED
# leader (a clean resync). A shorter length is "clean" if off+L names a leader.
import sys, os, glob, collections
sys.path.insert(0, '/Users/user/asahi_re/public/gpu/tools/agx-isa')
import importlib, isadb
importlib.reload(isadb)

OWN = '/Users/user/asahi_re/public/gpu/experiments/EXP-M4-13-full-corpus/hex'
TP  = '/Users/user/asahi_re/public/gpu/experiments/EXP-M4-13-full-corpus/thirdparty_hex'

def named_at(buf, off, n):
    L = isadb.instr_length(buf, off)
    if L is None or off + L > n:
        return None, None
    try:
        rec, _ = isadb.decode_one(buf, off)
        return L, rec['mnemonic']
    except ValueError:
        return L, None

def lands_named(buf, off, n):
    if off >= n: return 'EOF'
    L, mn = named_at(buf, off, n)
    return mn if mn is not None else ('LENONLY' if L is not None else 'DESYNC')

def audit(hexdir, label):
    files = sorted(glob.glob(os.path.join(hexdir, '*.hex')))
    n_fire = 0
    b2_hist = collections.Counter()
    land8 = collections.Counter()   # what off+8 lands on
    shorter_clean = collections.Counter()  # for L in 2/4/6: how many land named
    both68 = collections.Counter()
    examples = []
    for fp in files:
        try:
            h = open(fp).read().strip()
            if not h: continue
            buf = bytes.fromhex(h)
        except Exception:
            continue
        n = len(buf)
        off = 0
        while off < n:
            L, mn = named_at(buf, off, n)
            if L is not None:
                if mn == 'frag_pos_read':
                    n_fire += 1
                    b2 = buf[off+2] if off+2 < n else -1
                    b1 = buf[off+1] if off+1 < n else -1
                    b2_hist[b2] += 1
                    land8[lands_named(buf, off+8, n)] += 1
                    for Lc in (2,4,6):
                        tgt = lands_named(buf, off+Lc, n)
                        if isinstance(tgt,str) and tgt not in ('DESYNC','LENONLY','EOF'):
                            shorter_clean[Lc] += 1
                    if len(examples) < 25:
                        examples.append((os.path.basename(fp)[:40], off,
                                         buf[off:off+10].hex(' '),
                                         lands_named(buf,off+2,n), lands_named(buf,off+4,n),
                                         lands_named(buf,off+6,n), lands_named(buf,off+8,n)))
                off += L
                continue
            off += 2
            while off < n:
                L2, mn2 = named_at(buf, off, n)
                if mn2 is not None: break
                off += 2
    print(f"\n===== {label}: frag_pos_read fires {n_fire} times =====")
    print("  byte+2 histogram (potential swallowed leader):")
    for b2,c in b2_hist.most_common(20):
        # is b2 itself a plausible op-leader?
        leader = 'op-leader?' if isadb.instr_length(bytes([b2,0,0,0,0,0,0,0,0,0]),0) else ''
        print(f"    b2=0x{b2:02x}  x{c}   {leader}")
    print(f"  current off+8 lands on: {dict(land8)}")
    print(f"  shorter-length clean-resync counts (off+L lands NAMED): {dict(shorter_clean)}  of {n_fire}")
    print("  examples (file, off, bytes[:10], land@+2, +4, +6, +8):")
    for e in examples[:15]:
        print(f"    {e[0]:40s} @0x{e[1]:04x} {e[2]}  +2={e[3]} +4={e[4]} +6={e[5]} +8={e[6]}")

if __name__ == '__main__':
    audit(OWN, 'OWN')
    audit(TP, 'THIRDPARTY')
