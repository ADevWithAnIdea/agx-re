#!/usr/bin/env python3
# resid_inventory.py -- deduplicated inventory of residue regions across BOTH
# corpora: key = (byte0, first 4 bytes, region length), value = list of (corpus,
# kernel, offset). Helps target the highest-frequency residue ops.
import sys, os, glob, collections
sys.path.insert(0, '/Users/user/cleanroom_gpu/tools/agx-isa')
import isadb

HEXDIRS = {
    'M4':  '/Users/user/cleanroom_gpu/experiments/EXP-M4-01-isa-census/census/hex',
    'A18': '/Users/user/cleanroom_gpu/experiments/EXP-0036-consolidation-census/hex',
}
def trim(b):
    e=len(b)
    while e>=2 and b[e-2:e]==b'\x06\x00': e-=2
    return b[:e]
def named_at(b,o,n):
    L=isadb.instr_length(b,o)
    if L is None or o+L>n: return None,None
    try: return L, isadb.decode_one(b,o)[0]['mnemonic']
    except ValueError: return L,None
def walk(b):
    recs=[];o=0;n=len(b)
    while o<n:
        L,mn=named_at(b,o,n)
        if L is not None:
            recs.append((o,b[o],L,mn,'named' if mn else 'len')); o+=L; continue
        s=o;o+=2
        while o<n:
            L2,mn2=named_at(b,o,n)
            if mn2 is not None: break
            o+=2
        recs.append((s,b[s],o-s,None,'undec'))
    return recs

inv=collections.defaultdict(list)
for corp,d in HEXDIRS.items():
    for f in sorted(glob.glob(os.path.join(d,'*.hex'))):
        name=os.path.basename(f)[:-4]
        b=trim(bytes.fromhex(open(f).read().strip()))
        for r in walk(b):
            if r[4]!='undec': continue
            key=(b[r[0]:r[0]+4].hex(' '), r[2])
            inv[key].append((corp,name,r[0]))

for (sig,ln),locs in sorted(inv.items(), key=lambda kv:-len(kv[1])):
    kl=', '.join(f'{c}:{n}@{o}' for c,n,o in locs[:4])
    more='' if len(locs)<=4 else f' +{len(locs)-4}'
    print(f'{len(locs):3d}x  len={ln:2d}  [{sig}]   {kl}{more}')
