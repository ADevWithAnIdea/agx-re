import struct, sys
fn=sys.argv[1]
d=open(fn,"rb").read()
magic=struct.unpack(">I",d[:4])[0]
n=struct.unpack(">I",d[4:8])[0]
print(f"magic={magic:#x} nfat={n}")
stroff=d.find(b"AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
off=8
for i in range(n):
    cput,csub,foff,fsize,align=struct.unpack(">iiIII",d[off:off+20]); off+=20
    name={0x1000013:"AppleGPU/AGX",0x1000017:"AIR64"}.get(cput,hex(cput))
    inside = foff<=stroff<foff+fsize if stroff>=0 else False
    tag="  <-- FORMAT STRING HERE" if inside else ""
    print(f"  image {name}: fileoff={foff:#x} size={fsize:#x}{tag}")
print(f"format string @ {stroff:#x}")
