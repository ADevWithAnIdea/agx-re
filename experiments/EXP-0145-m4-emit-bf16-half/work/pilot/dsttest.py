import sys,os,struct,json
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import *
wd=os.path.join(EXP,'work','pilot')
buf,off,main=load_base(os.path.join(wd,'p_bfadd.bin'))
print('main len',len(main)); show(main)
A,B=3.0,5.0
ia=wf(os.path.join(wd,'ta.bin'),[A]*8); ib=wf(os.path.join(wd,'tb.bin'),[B]*8)
r=PersistRunner(source=os.path.join(EXP,'kernels','p_bfadd.metal'),function='k',fast_math=False,
                agxrun_persist=os.path.join(EXP,'work','bin','agxrun_persist'))
arch=os.path.join(wd,'sp.bin')
def run(mut):
    sp=bytearray(buf)
    for o,v in mut.items(): sp[off+o]=v
    open(arch,'wb').write(bytes(sp))
    resp=r.request(archive=arch,grid=1,tg=1,ins={1:ia,2:ib},outs={0:4},timeout=8)
    o=resp['outs'].get(0,b'')
    return resp['status'], o.hex(), (struct.unpack('<f',o)[0] if len(o)==4 else None)
# n3_mov is at +0x38: byte0 = 0x03|(dst<<4); byte1 = srcA_reg (7 bits) | uni<<7
print("--- dst sweep: bf byte0 hi nibble = D, n3_mov srcA_reg = D")
for D in range(16):
    st,h,f=run({0x30:(D<<4)|0x01, 0x39:D})
    print("  D=%2d  %-6s %-8s %s"%(D,st,h,f))
print("--- control: bf dst=D but n3_mov srcA_reg left at 0")
for D in (0,1,2,3):
    st,h,f=run({0x30:(D<<4)|0x01})
    print("  D=%2d  %-6s %-8s %s"%(D,st,h,f))
r.close()
