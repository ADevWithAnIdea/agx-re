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
d=sys.argv[1]; va=sys.argv[2]
# opcodes as LE u32 to search (byte pattern). draw 0x61c4 opcode is at byte+0x66/67 within a word 0x61c4_PP00
data=load(find_bo(d,va))
# scan for 2-byte LE opcode 0xc461 (0x61c4) and 0x0070..0x70000600 word and mesh 0x70000600
pats={"draw_0x61c4":bytes([0xc4,0x61]),"idx_0x61f2":bytes([0xf2,0x61]),"mesh_word_0x70000600":bytes([0x00,0x06,0x00,0x70])}
for name,pat in pats.items():
    offs=[i for i in range(len(data)-len(pat)+1) if data[i:i+len(pat)]==pat]
    print(f"{name}: {len(offs)} hits at "+", ".join(f"0x{o:x}" for o in offs[:20]))
