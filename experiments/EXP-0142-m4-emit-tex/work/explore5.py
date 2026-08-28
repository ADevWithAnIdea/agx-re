import os,sys,struct,subprocess,json,time
sys.path.insert(0,'../harness')
from texrunner import TexRunner
REPO=os.path.abspath('../../..')
AGXPARSE=os.path.join(REPO,'tools','shdump','agxparse.py')
sys.path.insert(0,os.path.join(REPO,'tools','agx-isa')); import isadb
src='m_k8.metal'; arch='m_k8.bin'
loc=subprocess.check_output(['python3',AGXPARSE,arch,'--locate','_agc.main']).decode().split()
ABS,LEN=int(loc[0]),int(loc[1])
base=open(arch,'rb').read(); main=base[ABS:ABS+LEN]
offs=[];off=0
while off<len(main):
    L=isadb.instr_length(main,off)
    if not L: break
    try:
        d,_=isadb.decode_one(main,off)
        if d['mnemonic']=='tex_sample': offs.append(off)
    except Exception: pass
    off+=L
p=os.path.abspath('in64.bin')
r=TexRunner(source=src,function='k_sample',exe='./texpersist',samp_w=16,samp_h=16)
def run(sp):
    b=bytearray(base)
    for (o,v) in sp: b[ABS+o]=v
    q=os.path.abspath('spl.bin'); open(q,'wb').write(bytes(b))
    resp=r.request(archive=q,grid=1,tg=1,ins={0:p},outs={1:128},timeout=10)
    if resp['status']!='OK': return resp['status'],None
    return 'OK',struct.unpack('<32f',resp['outs'][1])
t0=time.time()
st,o=run([]); print("baseline quad0",o[0:4],"quad7",o[28:32])
# quads for representative byte4 values on bundle 0
for v in (0x00,0x10,0x20,0x21,0x30,0x40,0x80,0xb0,0xb1,0xc0,0xf0,0xff):
    st,o=run([(offs[0]+4,v)])
    print("byte4=%02x quad0=%s"%(v,[round(x,3) for x in o[0:4]]))
# exact zero-sets for byte5 on bundle 0 and 7
for bi in (0,7):
    zs=[]
    for v in range(256):
        st,o=run([(offs[bi]+5,v)])
        if st=='OK' and o[4*bi]==0.0: zs.append(v)
    print("bundle%d byte5 zero-set n=%d: %s"%(bi,len(zs),[hex(x) for x in zs]))
print("elapsed",time.time()-t0)
r.close()
