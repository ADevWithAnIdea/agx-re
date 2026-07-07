import sys, re, glob, os
HEXLINE=re.compile(r"^([0-9a-f]{8}):\s+(.*)$")
def load(path):
    data=bytearray()
    for line in open(path):
        m=HEXLINE.match(line)
        if not m: continue
        off=int(m.group(1),16); b=bytes.fromhex(m.group(2).replace(" ",""))
        if len(data)<off+len(b): data.extend(b"\x00"*(off+len(b)-len(data)))
        data[off:off+len(b)]=b
    return bytes(data)
def find_bo(d, va):
    g=glob.glob(os.path.join(d, f"bo_*_va{va}_*.hex"))
    return g[0] if g else None
d=sys.argv[1]; va=sys.argv[2]; start=int(sys.argv[3],16); end=int(sys.argv[4],16)
p=find_bo(d,va)
if not p: print("NO BO",va,"in",d); sys.exit(1)
data=load(p)
for off in range(start,end,4):
    w=data[off:off+4]
    le=int.from_bytes(w,"little")
    print(f"  +0x{off:03x}: bytes={w.hex()} le32=0x{le:08x}")
