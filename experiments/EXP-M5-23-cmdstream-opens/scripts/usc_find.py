#!/usr/bin/env python3
# usc_find.py DUMPDIR -> locate the fragment Tier-2 argument buffer (the BO whose +0x600
# region is a run of 8-byte LE GPU-VA slots with high32==0x00000100) and print the
# header slots +0x600..+0x638 as 8-byte LE values, so we can read the +0x610+k*8 buffer list.
import sys,re,glob,os,struct
def load(path):
    d=bytearray()
    for line in open(path):
        m=re.match(r'^([0-9a-f]{8}): (.*)',line)
        if not m:continue
        b=int(m.group(1),16);by=bytes.fromhex(m.group(2).replace(' ',''))
        if b+len(by)>len(d):d.extend(b'\x00'*(b+len(by)-len(d)))
        d[b:b+len(by)]=by
    return bytes(d)
D=sys.argv[1]
best=None
for f in sorted(glob.glob(os.path.join(D,'bo_*'))):
    data=load(f)
    if len(data)<0x640: continue
    # slot at +0x600: 8-byte LE, high32 == 0x00000100 (GPU VA high bits used by these arg bufs)
    s600=int.from_bytes(data[0x600:0x608],'little')
    s608=int.from_bytes(data[0x608:0x610],'little')
    if (s600>>32)==0x00000100 and (s608>>32)==0x00000100:
        best=(f,data); break
if not best:
    print("no USC arg buffer found in",D); sys.exit(1)
f,data=best
m=re.search(r'_va([0-9a-f]+)_',os.path.basename(f)); va=m.group(1) if m else '?'
print("USC arg buffer BO va=%s (%s)"%(va,os.path.basename(f)[:40]))
for off in range(0x600,0x640,8):
    v=int.from_bytes(data[off:off+8],'little')
    print("  +0x%03x: %016x"%(off,v))
