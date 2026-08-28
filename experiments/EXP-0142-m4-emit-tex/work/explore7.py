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
r=TexRunner(source='m_k8.metal',function='k_sample',exe='./texpersist',samp_w=16,samp_h=16)
def run(sp):
    b=bytearray(base)
    for (o,v) in sp: b[ABS+o]=v
    q=os.path.abspath('spl.bin'); open(q,'wb').write(bytes(b))
    resp=r.request(archive=q,grid=1,tg=1,ins={0:p},outs={1:128},timeout=10)
    if resp['status']!='OK': return resp['status'],None
    return 'OK',struct.unpack('<32f',resp['outs'][1])
st,B=run([])
t0=time.time(); n=1
J=7
print("baseline q7",B[28:32])
for bi in range(14):
    agg={}
    for v in range(256):
        st,o=run([(offs[J]+bi,v)]); n+=1
        if st!='OK': k=('ST',st)
        else:
            k=(tuple(round(x,2) for x in o[28:32]), tuple(j for j in range(8) if o[4*j:4*j+4]!=B[4*j:4*j+4]))
        agg.setdefault(k,[]).append(v)
    print("byte+%-2d base=%02x  distinct=%d"%(bi,main[offs[J]+bi],len(agg)))
    for k,vs in sorted(agg.items(),key=lambda kv:-len(kv[1]))[:8]:
        print("     n=%3d %s  ex=%s"%(len(vs),k,[hex(x) for x in vs[:6]]))
print("elapsed %.2f n=%d"%(time.time()-t0,n))
r.close()
