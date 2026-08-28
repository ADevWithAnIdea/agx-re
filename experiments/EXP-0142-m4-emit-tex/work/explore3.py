import os,sys,struct,subprocess,json
sys.path.insert(0,'../harness')
from texrunner import TexRunner
REPO=os.path.abspath('../../..')
AGXPARSE=os.path.join(REPO,'tools','shdump','agxparse.py')
src='probe_sample3.metal'; arch='probe_sample3.bin'
loc=subprocess.check_output(['python3',AGXPARSE,arch,'--locate','_agc.main']).decode().split()
ABS,LEN=int(loc[0]),int(loc[1])
base=open(arch,'rb').read(); main=base[ABS:ABS+LEN]
BUNDLE=main.find(bytes.fromhex('05800cb8b0000900000010000100'))
NOUT=52*4
def mkin(name,vals):
    p=os.path.abspath(name); open(p,'wb').write(b''.join(struct.pack('<f',v) for v in vals)); return p
IN_A=mkin('inA.bin',[i+0.5 for i in range(32)])
IN_B=mkin('inB.bin',[(31-i)+0.5 for i in range(32)])
r=TexRunner(source=src,function='k_sample',exe='./texpersist',samp_w=16,samp_h=16)
def run(off,val,inb):
    b=bytearray(base); b[ABS+BUNDLE+off]=val
    p=os.path.abspath('spl.bin'); open(p,'wb').write(bytes(b))
    resp=r.request(archive=p,grid=1,tg=1,ins={0:inb},outs={1:NOUT},timeout=10)
    if resp['status']!='OK': return resp['status'],None
    return 'OK',struct.unpack('<52f',resp['outs'][1])
for off,name in ((4,'op+0 result_sel'),(5,'op+1 coord')):
    print("=== %s ==="%name)
    rows=[]
    for v in range(256):
        sa,oa=run(off,v,IN_A); sb,ob=run(off,v,IN_B)
        a = oa[0] if sa=='OK' else sa
        b_ = ob[0] if sb=='OK' else sb
        da=[i for i in range(24) if sa=='OK' and oa[25+i]!=oa[1+i]]
        rows.append((v,a,b_,da))
    for v,a,b_,da in rows:
        print("  %02x  A=%-10s B=%-10s clob=%s"%(v,a,b_,da))
r.close()
