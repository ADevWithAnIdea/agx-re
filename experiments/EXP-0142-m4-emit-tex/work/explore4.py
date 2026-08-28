import os,sys,struct,subprocess,json
sys.path.insert(0,'../harness')
from texrunner import TexRunner
REPO=os.path.abspath('../../..')
AGXPARSE=os.path.join(REPO,'tools','shdump','agxparse.py')
sys.path.insert(0,os.path.join(REPO,'tools','agx-isa')); import isadb
src='m_k8.metal'; arch='m_k8.bin'
loc=subprocess.check_output(['python3',AGXPARSE,arch,'--locate','_agc.main']).decode().split()
ABS,LEN=int(loc[0]),int(loc[1])
base=open(arch,'rb').read(); main=base[ABS:ABS+LEN]
# find all tex_sample offsets
offs=[]; off=0
while off<len(main):
    L=isadb.instr_length(main,off)
    if not L: break
    try:
        d,_=isadb.decode_one(main,off)
        if d['mnemonic']=='tex_sample': offs.append((off,main[off:off+L].hex()))
    except Exception: pass
    off+=L
print("bundles:",offs)
p=os.path.abspath('in64.bin')
open(p,'wb').write(b''.join(struct.pack('<f',(i%16)+0.5) for i in range(64)))
NOUT=32*4
r=TexRunner(source=src,function='k_sample',exe='./texpersist',samp_w=16,samp_h=16)
def run(splices):
    b=bytearray(base)
    for (o,v) in splices: b[ABS+o]=v
    q=os.path.abspath('spl.bin'); open(q,'wb').write(bytes(b))
    resp=r.request(archive=q,grid=1,tg=1,ins={0:p},outs={1:NOUT},timeout=10)
    if resp['status']!='OK': return resp['status'],None
    return 'OK',struct.unpack('<32f',resp['outs'][1])
st,o=run([])
print("baseline",st,[o[4*j] for j in range(8)])
for bi in (0,7):
    boff=offs[bi][0]
    for bb,nm in ((5,'coord op+1'),(4,'result_sel op+0')):
        print("=== bundle %d %s (base=%02x) ==="%(bi,nm,main[boff+bb]))
        agg={}
        for v in range(256):
            st,o2=run([(boff+bb,v)])
            if st!='OK': k=('ST',st)
            else: k=tuple(round(o2[4*j],2) for j in range(8))
            agg.setdefault(k,[]).append(v)
        for k,vs in sorted(agg.items(),key=lambda kv:kv[1][0]):
            print("   n=%3d %s  first=%s"%(len(vs),k,[hex(x) for x in vs[:8]]))
r.close()
