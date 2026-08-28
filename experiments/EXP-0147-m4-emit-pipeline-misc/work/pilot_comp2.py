import sys,struct,shutil,subprocess
sys.path.insert(0,'.')
from persistrun import PersistRunner
K='pilot_f2.metal'
def hx(a): return subprocess.run(['python3','agxparse.py',a,'--extract-hex'],capture_output=True,text=True).stdout.strip()
def loc(a): return int(subprocess.run(['python3','agxparse.py',a,'--locate','_agc.main'],capture_output=True,text=True).stdout.split()[0])
A=[float(i)*1.5-7.0 for i in range(256)]
open('a256.bin','wb').write(struct.pack('<256f',*A))
arc='f2_k_tgrw.bin'; h=hx(arc); i=h.find('87008004'); base=loc(arc)+i//2
print('compute_fence_scoped @',i//2)
r=PersistRunner(source=K,function='k_tgrw',fast_math=False,agxrun_persist='./agxrun_persist')
b=r.request(archive=arc,grid=256,tg=256,ins={1:'a256.bin'},outs={0:1024},timeout=10)
bv=struct.unpack('<256f',b['outs'][0]) if 0 in b['outs'] else None
print('baseline',b['status'],[round(x,2) for x in bv[:6]])
exp=[A[(i+1)%256]+A[i] for i in range(256)]
print('oracle  ',[round(x,2) for x in exp[:6]],'match',all(abs(x-y)<1e-3 for x,y in zip(bv,exp)))
for off in range(0,4):
    shutil.copyfile(arc,'pc2.bin')
    with open('pc2.bin','r+b') as f: f.seek(base+off); f.write(bytes([0x55]))
    rr=r.request(archive='pc2.bin',grid=256,tg=256,ins={1:'a256.bin'},outs={0:1024},timeout=10)
    v=struct.unpack('<256f',rr['outs'][0]) if 0 in rr['outs'] else None
    print(f'+{off}=0x55 {rr["status"]:12s}',[round(x,2) for x in v[:6]] if v else rr.get('error'),'CHANGED' if v!=bv else 'same')
r.close()
