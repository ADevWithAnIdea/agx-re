#!/usr/bin/env python3
# Dump the resync-walk tokenization of one or more hex files (named ops + UNDEC
# regions inline) so the multi-byte structure is directly visible.
import sys, os, glob
sys.path.insert(0, os.path.expanduser("~/cleanroom_work/tools/agx-isa-m5"))
import isadb

def trim_padding(b):
    end=len(b)
    while end>=2 and b[end-2:end]==b'\x06\x00': end-=2
    return b[:end]

def named_at(buf,off,n):
    L=isadb.instr_length(buf,off)
    if L is None or off+L>n: return None,None
    try:
        rec,_=isadb.decode_one(buf,off); return L,rec['mnemonic']
    except ValueError:
        return L,None

def walk(buf):
    recs=[]; off=0; n=len(buf)
    while off<n:
        L,mn=named_at(buf,off,n)
        if L is not None:
            recs.append((off,L,mn,'named' if mn else 'raw')); off+=L; continue
        start=off; off+=2
        while off<n:
            L2,mn2=named_at(buf,off,n)
            if mn2 is not None: break
            off+=2
        recs.append((start,off-start,None,'undec'))
    return recs

def main():
    pat=sys.argv[1]
    files=sorted(glob.glob(pat))
    for fp in files[:int(sys.argv[2]) if len(sys.argv)>2 else 4]:
        h=open(fp).read().strip()
        if not h: continue
        buf=trim_padding(bytes.fromhex(h))
        print("==== %s (%d bytes) ====" % (os.path.basename(fp), len(buf)))
        for off,L,mn,st in walk(buf):
            hx=bytes(buf[off:off+L]).hex(' ')
            tag = mn if st=='named' else ('[raw]' if st=='raw' else '******UNDEC******')
            print("  +%3d L=%2d  %-20s %s" % (off, L, tag, hx))
        print()

if __name__=='__main__': main()
