import sys,os,struct
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import *
wd=os.path.join(EXP,'work','pilot')
buf,off,main=load_base(os.path.join(wd,'p_bfadd.bin'))
NOP2=isadb.assemble('mov_imm',{'dst':13,'imm7':0,'imm_top':0})
A,B=3.0,5.0
ia=wf(os.path.join(wd,'ta.bin'),[A]*8); ib=wf(os.path.join(wd,'tb.bin'),[B]*8)
r=PersistRunner(source=os.path.join(EXP,'kernels','p_bfadd.metal'),function='k',fast_math=False,
                agxrun_persist=os.path.join(EXP,'work','bin','agxrun_persist'))
arch=os.path.join(wd,'sp.bin')
ST=0x3c
def run(mut):
    sp=bytearray(buf)
    for o,v in mut.items():
        if isinstance(v,int): sp[off+o]=v
        else:
            for i,bb in enumerate(v): sp[off+o+i]=bb
    open(arch,'wb').write(bytes(sp))
    resp=r.request(archive=arch,grid=1,tg=1,ins={1:ia,2:ib},outs={0:4},timeout=8)
    o=resp['outs'].get(0,b'')
    return resp['status'], o.hex()
print("=== S: read back each register via device_store extmode=2R (byte+3), baseline program")
for R in range(10):
    print("   r%-2d"%R, run({ST+3:(2*R)&0xFF}))
print("=== S2: same but n3_mov at +0x38 nopped")
for R in range(6):
    print("   r%-2d"%R, run({0x38:NOP2*2, ST+3:(2*R)&0xFF}))
print("=== D: bf dst nibble = D, store reads rD (extmode=2D)")
for D in range(8):
    print("   D=%d"%D, run({0x30:(D<<4)|0x01, ST+3:(2*D)&0xFF}))
print("=== D2: bf dst nibble = D, store reads rD, n3_mov nopped")
for D in range(8):
    print("   D=%d"%D, run({0x30:(D<<4)|0x01, 0x38:NOP2*2, ST+3:(2*D)&0xFF}))
r.close()
