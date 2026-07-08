#!/usr/bin/env python3
# cdmraw.py — dump ALL 11 u32 words of each 0x2c-byte CDM record (full record).
import sys,re
def load(path):
    data=bytearray()
    for line in open(path):
        m=re.match(r'^([0-9a-f]{8}):\s+(.*)$',line)
        if not m: continue
        off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(' ',''))
        if len(data)<off+len(b): data.extend(b'\0'*(off+len(b)-len(data)))
        data[off:off+len(b)]=b
    return bytes(data)
def u32(d,o): return int.from_bytes(d[o:o+4],'little')
d=load(sys.argv[1])
off=0; rec=0
while off+0x2c<=len(d):
    cfg=u32(d,off)
    if cfg==0x40000000 or cfg==0: break
    words=[u32(d,off+4*i) for i in range(11)]
    print(f"rec{rec} @+{off:#x}: "+" ".join(f"+{4*i:02x}={w:#010x}" for i,w in enumerate(words)))
    off+=0x2c; rec+=1
