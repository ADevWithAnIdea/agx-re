import re,glob,struct,sys
def load(p):
    b=bytearray()
    for line in open(p):
        m=re.match(r'^\s*([0-9a-fA-F]+):\s+(.*)$',line.strip())
        if not m: continue
        b+=bytes.fromhex(re.sub(r'[^0-9a-fA-F]','',m.group(2)))
    return bytes(b)
def bo(tag,va):
    g=glob.glob(f'{tag}.maps/bo_*va{va}_*.hex')
    return load(g[0]) if g else None
def u32(b,o): return struct.unpack_from('<I',b,o)[0] if b and o+4<=len(b) else None
def f32(b,o): return struct.unpack_from('<f',b,o)[0] if b and o+4<=len(b) else None
tag=sys.argv[1]; what=sys.argv[2] if len(sys.argv)>2 else 'all'
if what in ('tile','all'):
    b=bo(tag,'68000')
    if b: print(f"[{tag}] TILING 0x68000: +0x900=0x{u32(b,0x900):08x} +0x904=0x{u32(b,0x904):08x} +0x908=0x{u32(b,0x908):08x}  vp@+0x910: {f32(b,0x910):.1f},{f32(b,0x914):.1f},{f32(b,0x918):.1f},{f32(b,0x91c):.1f} depth@+0x920:{f32(b,0x920):.3f},{f32(b,0x924):.3f}")
if what in ('att','all'):
    for va in ['10000110000','10000018200']:
        b=bo(tag,va)
        if b and any(b):
            print(f"[{tag}] ATT {va}: +0x20=0x{u32(b,0x20):08x} +0x22byte=0x{b[0x22]:02x} +0x24=0x{u32(b,0x24):08x}  seg0 head: "+' '.join(f'{b[o]:02x}' for o in range(0,4)))
if what in ('sampos','all'):
    for va in ['100000e8000','100000e0000','100000f0000']:
        b=bo(tag,va)
        if b and any(b[0x40:0x80]):
            print(f"[{tag}] SAMPOS {va} +0x40: "+' '.join(f'{f32(b,0x40+j*4):.4f}' for j in range(8)))
if what in ('ds','all'):
    b=bo(tag,'58000')
    if b: print(f"[{tag}] STATE 0x58000: +0x08=0x{u32(b,0x08):08x} +0x14=0x{u32(b,0x14):08x} +0x18=0x{u32(b,0x18):08x} +0x20=0x{u32(b,0x20):08x} +0x2c=0x{u32(b,0x2c):08x} +0x34=0x{u32(b,0x34):08x} +0x38=0x{u32(b,0x38):08x} +0x3c=0x{u32(b,0x3c):08x} +0x40=0x{u32(b,0x40):08x} +0x44=0x{u32(b,0x44):08x} +0x70=0x{u32(b,0x70):08x} +0x8c=0x{u32(b,0x8c):08x} +0xa0=0x{u32(b,0xa0):08x}")
