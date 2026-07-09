#!/usr/bin/env python3
# decode_all.py — EXP-M4-03: decode every M4 cmdstream/pipeline field probed and
# print it next to the documented A18 (G17P) baseline for confirm-or-delta.
# Reads the .maps/ BO hex snapshots captured by tools/iotrace on THIS M4 host.
# Clean-room: operates only on our-own-program BO byte captures (DATA-TRACE).
import re, glob, struct, sys

def load(p):
    b = bytearray()
    for line in open(p):
        m = re.match(r'^\s*([0-9a-fA-F]+):\s+(.*)$', line.strip())
        if not m:
            continue
        b += bytes.fromhex(re.sub(r'[^0-9a-fA-F]', '', m.group(2)))
    return bytes(b)

def bo(tag, va):
    g = glob.glob(f'{tag}.maps/bo_*va{va}_*.hex')
    return load(g[0]) if g else None

def u32(b, o): return struct.unpack_from('<I', b, o)[0]
def u16(b, o): return struct.unpack_from('<H', b, o)[0]
def f32(b, o): return struct.unpack_from('<f', b, o)[0]

print("############ ITEM 1 — CDM compute launch (0x100000b0000) ############")
b = bo('step0_compute', '100000b0000')
print(f"  +0x00 config    = 0x{u32(b,0x00):08x}   [A18: 0x00080000, bit19]")
print(f"  +0x08 shaderptr = 0x{u32(b,0x08):08x}   [A18: shaderVA>>6; 0x90000>>6=0x2400]")
print(f"  +0x10 grid.xyz  = {u32(b,0x10)},{u32(b,0x14)},{u32(b,0x18)}   [A18: threads; 64,1,1]")
print(f"  +0x1c tg.xyz    = {u32(b,0x1c)},{u32(b,0x20)},{u32(b,0x24)}   [A18: effective tg; 32,1,1]")
print(f"  +0x2c term      = 0x{u32(b,0x2c):08x}   [A18: 0x40000000]")

print("\n############ ITEM 2 — VDM draw record (0x18000) ############")
for tag in ['draw_tri', 'draw_line', 'draw_inst5', 'draw_idx']:
    b = bo(tag, '18000')
    win = ' '.join(f'{b[j]:02x}' for j in range(0x60, 0x80))
    print(f"  [{tag}] +0x60..0x80: {win}")
b = bo('draw_tri', '18000')
print(f"    tri:  prim@+0x65=0x{b[0x65]:02x} op@+0x66=0x{u16(b,0x66):04x} vcnt@+0x68={u32(b,0x68)} icnt@+0x6c={u32(b,0x6c)}  [A18: prim tri=0x06, op 0x61c4, +0x68/+0x6c]")
b = bo('draw_inst5', '18000')
print(f"    inst5: icnt@+0x6c={u32(b,0x6c)}  [A18: instanceCount @+0x6c non-indexed]")
b = bo('draw_line', '18000')
print(f"    line: prim@+0x65=0x{b[0x65]:02x}  [A18: line=0x01]")
b = bo('draw_idx', '18000')
print(f"    idx:  restart@+0x68=0x{u16(b,0x68):04x} prim@+0x6d=0x{b[0x6d]:02x} op@+0x6e=0x{u16(b,0x6e):04x} idxcnt@+0x74={u32(b,0x74)} icnt@+0x78={u32(b,0x78)}  [A18: op 0x61f2(u16), restart 0xffff@+0x68, idxcnt+0x74, icnt+0x78]")

print("\n############ ITEM 3 — USC sampler stride (arg buf 0x10000248000, hdr +0x600) ############")
for tag, ft, fs in [('usc_t1s1', 1, 1), ('usc_t2s3', 2, 3), ('usc_t3s1', 3, 1)]:
    b = bo(tag, '10000248000')
    o = 0x600
    tp = struct.unpack_from('<Q', b, o)[0]
    sp = struct.unpack_from('<Q', b, o + 8)[0]
    base = 0x10000248000
    term = None
    for oo in range((sp - base), min(len(b), (sp - base) + 0x400), 4):
        if u32(b, oo) == 0x60000000:
            term = base + oo
            break
    ntex = (sp - tp) // 0x20
    nsmp = (term - sp) // 0x20 if term else -1
    print(f"  [{tag}] tex_ptr=0x{tp:x} samp_ptr=0x{sp:x} term=0x{term:x}  num_tex=(samp-tex)/0x20={ntex} num_samp=(term-samp)/0x20={nsmp}  (expect {ft}/{fs})  [A18 RT-2a: samp stride 0x20]")

print("\n############ ITEM 4 — Fixed-function state packets (0x58000) ############")
for tag in ['tb_base', 'tb_ds']:
    b = bo(tag, '58000')
    print(f"  [{tag}] +0x14 len=0x{u32(b,0x14):08x} +0x20 PPPout=0x{u32(b,0x20):08x} +0x2c UVScnt=0x{u32(b,0x2c):08x} +0x34 flags=0x{u32(b,0x34):08x} +0x38 depth=0x{u32(b,0x38):08x} +0x3c stencil=0x{u32(b,0x3c):08x} +0x70 raster=0x{u32(b,0x70):08x}")
db = bo('tb_base', '58000'); dd = bo('tb_ds', '58000')
print(f"    PPP length bump on depth/stencil: 0x{u32(db,0x14):x} -> 0x{u32(dd,0x14):x}  (delta 0x{u32(dd,0x14)-u32(db,0x14):x})  [A18: +0x400]")

print("\n############ ITEM 5 — Indirect / occlusion / mesh / tessellation ############")
for tag, off in [('ind_draw', 0x66), ('ind_drawix', 0x6e)]:
    b = bo(tag, '18000')
    print(f"  [{tag}] opcode@+0x{off:x}=0x{u16(b,off):04x}  [A18: 0x6404 non-indexed / 0x6432 indexed]")
for tag in ['occ_bool', 'occ_count']:
    b = bo(tag, '58000')
    v = u32(b, 0x8c)
    print(f"  [{tag}] 0x58000+0x8c=0x{v:08x} bit14={(v>>14)&1}  [A18: Boolean=1/Counting=0]")
b = bo('mesh_base', '18000')
for o in range(0, len(b) - 4, 2):
    if u32(b, o) == 0x70000600:
        print(f"  [mesh_base] record 0x70000600 @+0x{o:x} grid={u32(b,o+4)},{u32(b,o+8)},{u32(b,o+12)}  [A18: 0x70000600]")
        break
for tag, dom in [('tess_tri', 1), ('tess_quad', 2)]:
    b = bo(tag, '18000')
    print(f"  [{tag}] VDM record hi-byte@+0x67=0x{b[0x67]:02x} domain@+0x8c={u32(b,0x8c)} cfg@+0x68=0x{u32(b,0x68):08x} factorptr@+0x74=0x{u32(b,0x74):08x}  [A18: hi 0x40, tri=1/quad=2]")

print("\n############ ITEM 6 — TBDR pipeline ############")
for tag, w in [('tb_base', 64), ('tb_big', 200)]:
    b = bo(tag, '68000')
    print(f"  [{tag} w={w}] tile +0x904=0x{u32(b,0x904):08x} +0x908=0x{u32(b,0x908):08x} vp@+0x910={f32(b,0x910):.0f},{f32(b,0x914):.0f},{f32(b,0x918):.0f},{f32(b,0x91c):.0f}  [A18: 0x80000000|ceil(W/32)-1 ; 32x32 fixed]")
for tag in ['tb_base', 'tb_msaa4']:
    b = bo(tag, '10000018200')
    print(f"  [{tag}] att +0x24=0x{u32(b,0x24):08x} (byte3=0x{(u32(b,0x24)>>24)&0xff:02x})  [A18: msaa4=0x09xxxxxx bit24/bit27]")
for tag in ['tb_msaa4', 'tb_sampos']:
    b = bo(tag, '100000e8000')
    pos = ', '.join(f'({f32(b,0x40+j*8):.4f},{f32(b,0x40+j*8+4):.4f})' for j in range(4))
    print(f"  [{tag}] sample pos @0x100000e8000+0x40: {pos}  [A18 RT-4: userspace-emittable, 1/16 grid]")
# memoryless poison
b = bo('tb_mlc', '10000018200')
found = [hex(o) for o in range(0, len(b) - 4, 4) if u32(b, o) == 0x0eeee000]
print(f"  [tb_mlc] memoryless poison 0x0eeee000 in 0x10000018200 at offsets {found[:4]}  [A18: 0x0eeee000]")
