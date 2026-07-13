import sys,re
# shex.py FILE OFF LEN  -> prints bytes[OFF:OFF+LEN] hex + LE int
path,off,ln=sys.argv[1],int(sys.argv[2],0),int(sys.argv[3],0)
data=bytearray()
for line in open(path):
    m=re.match(r'^([0-9a-f]{8}): (.*)',line)
    if not m: continue
    base=int(m.group(1),16)
    hexs=m.group(2).replace(' ','')
    b=bytes.fromhex(hexs[:len(hexs)-(len(hexs)%2)])
    if base+len(b)>len(data): data.extend(b'\x00'*(base+len(b)-len(data)))
    data[base:base+len(b)]=b
seg=bytes(data[off:off+ln])
print("%s +0x%02x: %s  LE=0x%x" % (path.split('/')[-1][:28], off, seg.hex(), int.from_bytes(seg,'little')))
