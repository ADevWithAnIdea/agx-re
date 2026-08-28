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
t0=time.time(); n=0
st,base_o=run([]); n+=1
print("baseline", [base_o[4*j] for j in range(8)])
# CHAIN (byte0 high nibble) sweep on bundle 7 (base chain=0 -> dest r0)
print("=== bundle7 chain (byte0 hi nibble) sweep ===")
for v in range(16):
    b0=(main[offs[7]] & 0x0f) | (v<<4)
    st,o=run([(offs[7],b0)]); n+=1
    if st!='OK': print("  chain=%x %s"%(v,st)); continue
    ch=[j for j in range(8) if o[4*j:4*j+4]!=base_o[4*j:4*j+4]]
    print("  chain=%x  changed_quads=%s  q7=%s  q_changed=%s"%(v,ch,[round(x,2) for x in o[28:32]],[[round(x,2) for x in o[4*j:4*j+4]] for j in ch]))
print("=== bundle0 chain sweep ===")
for v in range(16):
    b0=(main[offs[0]] & 0x0f) | (v<<4)
    st,o=run([(offs[0],b0)]); n+=1
    if st!='OK': print("  chain=%x %s"%(v,st)); continue
    ch=[j for j in range(8) if o[4*j:4*j+4]!=base_o[4*j:4*j+4]]
    print("  chain=%x  changed=%s q0=%s"%(v,ch,[round(x,2) for x in o[0:4]]))
print("elapsed %.2fs for %d dispatches (%.2f ms/case)"%(time.time()-t0,n,1000*(time.time()-t0)/n))
r.close()
