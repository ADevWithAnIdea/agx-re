#!/usr/bin/env python3
# cdmread.py — extract every 0x2c-byte CDM record's fields from a CDM BO hex dump.
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
    shptr=u32(d,off+8)
    gx,gy,gz=u32(d,off+0x10),u32(d,off+0x14),u32(d,off+0x18)
    tx,ty,tz=u32(d,off+0x1c),u32(d,off+0x20),u32(d,off+0x24)
    print(f"rec{rec} @+{off:#x}: cfg={cfg:#010x} shptr={shptr:#x} grid=({gx},{gy},{gz}) tg=({tx},{ty},{tz}) w28={u32(d,off+0x28):#x}")
    off+=0x2c; rec+=1
