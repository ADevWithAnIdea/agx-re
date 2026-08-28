import os,sys,struct,subprocess,time
sys.path.insert(0,'../harness')
from texrunner import TexRunner
REPO=os.path.abspath('../../..')
AGXPARSE=os.path.join(REPO,'tools','shdump','agxparse.py')
sys.path.insert(0,os.path.join(REPO,'tools','agx-isa')); import isadb
arch='m_k8.bin'
loc=subprocess.check_output(['python3',AGXPARSE,arch,'--locate','_agc.main']).decode().split()
ABS,LEN=int(loc[0]),int(loc[1])
base=open(arch,'rb').read(); main=base[ABS:ABS+LEN]
tcs=[];ts=[];off=0
while off<len(main):
    L=isadb.instr_length(main,off)
    if not L: break
    try:
        d,_=isadb.decode_one(main,off)
        if d['mnemonic']=='tex_coord_setup': tcs.append(off)
        if d['mnemonic']=='tex_sample': ts.append(off)
    except Exception: pass
    off+=L
print("coord_setups",[(o,main[o:o+10].hex()) for o in tcs])
p=os.path.abspath('in64.bin')
r=TexRunner(source='m_k8.metal',function='k_sample',exe='./texpersist',samp_w=16,samp_h=16)
def run(sp):
    b=bytearray(base)
    for (o,v) in sp: b[ABS+o]=v
    q=os.path.abspath('spl.bin'); open(q,'wb').write(bytes(b))
    resp=r.request(archive=q,grid=1,tg=1,ins={0:p},outs={1:128},timeout=10)
    if resp['status']!='OK': return resp['status'],None
    return 'OK',struct.unpack('<32f',resp['outs'][1])
st,B=run([]); print("baseline",[B[4*j] for j in range(8)])
# setup #12 (byte0hi=12) is claimed dst r12 <- in[0]; sample0 coords (r12,r13)
for idx in range(len(tcs)):
    o=tcs[idx]
    cur=main[o]
    for nib in (0x0, 0x5, 0xa):
        if (cur>>4)==nib: continue
        st,ob=run([(o,(cur&0x0f)|(nib<<4))])
        if st!='OK': print("  setup%d byte0hi=%x -> %s"%(idx,nib,st)); continue
        ch=[(j,round(ob[4*j],2)) for j in range(8) if ob[4*j:4*j+4]!=B[4*j:4*j+4]]
        print("  setup%d (base %02x) byte0hi=%x changed=%s"%(idx,cur,nib,ch))
    break
# sweep byte0hi of setup that we believe feeds sample 0 -- find which setup affects sample0
print("--- which setup affects which sample (byte0hi -> 0x0) ---")
for idx,o in enumerate(tcs):
    cur=main[o]
    nib = 0x5 if (cur>>4)!=0x5 else 0x0
    st,ob=run([(o,(cur&0x0f)|(nib<<4))])
    if st!='OK': print("  setup%d %s"%(idx,st)); continue
    ch=[(j,round(ob[4*j],2)) for j in range(8) if ob[4*j:4*j+4]!=B[4*j:4*j+4]]
    print("  setup%d base=%02x b1=%02x -> nib %x : changed=%s"%(idx,cur,main[o+1],nib,ch))
print("--- b1 (source) sweep on setup0 ---")
o=tcs[0]
for v in (0x01,0x03,0x05,0x07,0x09,0x0b,0x0d,0x0f,0x11,0x13,0x15,0x17,0x19,0x1b,0x1d,0x1f):
    st,ob=run([(o+1,v)])
    if st!='OK': print("   b1=%02x %s"%(v,st)); continue
    ch=[(j,round(ob[4*j],2)) for j in range(8) if ob[4*j:4*j+4]!=B[4*j:4*j+4]]
    print("   b1=%02x changed=%s"%(v,ch))
r.close()
