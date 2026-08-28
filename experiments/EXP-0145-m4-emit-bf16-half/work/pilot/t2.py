import sys,os,struct,json
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import *
wd=os.path.join(EXP,'work','pilot')
buf,off,main=load_base(os.path.join(wd,'p_bfadd.bin'))
NOP2=isadb.assemble('mov_imm',{'dst':13,'imm7':0,'imm_top':0})
print('NOP2',NOP2.hex())
A,B=3.0,5.0
ia=wf(os.path.join(wd,'ta.bin'),[A]*8); ib=wf(os.path.join(wd,'tb.bin'),[B]*8)
r=PersistRunner(source=os.path.join(EXP,'kernels','p_bfadd.metal'),function='k',fast_math=False,
                agxrun_persist=os.path.join(EXP,'work','bin','agxrun_persist'))
arch=os.path.join(wd,'sp.bin')
def run(mut,ia=ia,ib=ib):
    sp=bytearray(buf)
    for o,v in mut.items():
        if isinstance(v,int): sp[off+o]=v
        else:
            for i,bb in enumerate(v): sp[off+o+i]=bb
    open(arch,'wb').write(bytes(sp))
    resp=r.request(archive=arch,grid=1,tg=1,ins={1:ia,2:ib},outs={0:4},timeout=8)
    o=resp['outs'].get(0,b'')
    return resp['status'], o.hex()
print("=== T1: nop the n3_mov at +0x38 (4B), store r0 raw")
print("   base      ", run({}))
print("   n3_mov nop", run({0x38:NOP2+NOP2}))
print("=== T2: nop the cvt_bf16 at +0x20 (8B) so r2 keeps the RAW f32 a; sweep bf byte+1")
for v in (0x04,0x05,0x00,0x01):
    print("   byte+1=%02x"%v, run({0x20:NOP2*4, 0x31:v}))
print("=== T2b: same but also nop cvt_f2h_dst+pad at +0x28 (8B) so r0 keeps RAW f32 b")
for v in (0x04,0x05,0x00,0x01):
    print("   byte+1=%02x"%v, run({0x20:NOP2*4, 0x28:NOP2*4, 0x31:v}))
print("=== T3: dst nibble D + store reads rD (device_store extmode=2D at store byte+2), n3_mov nopped")
storeoff=0x3c
for D in range(6):
    sp_mut={0x30:(D<<4)|0x01, 0x38:NOP2+NOP2, storeoff+2:(2*D)&0xFF}
    print("   D=%d"%D, run(sp_mut))
print("=== T3b: same, but n3_mov kept as widen with srcA_reg=D, store reads r0")
for D in range(6):
    print("   D=%d"%D, run({0x30:(D<<4)|0x01, 0x39:D}))
r.close()
