import sys,struct,shutil,subprocess,os
sys.path.insert(0,'.')
from persistrun import PersistRunner
K='../kernels/pipe_compute.metal'
def build(fn,out): subprocess.run(['./shdump','-o',out,'-f',fn,'--no-fast-math',K],check=True,capture_output=True); return out
def loc(a): 
    o=subprocess.run(['python3','agxparse.py',a,'--locate','_agc.main'],capture_output=True,text=True).stdout.split(); return int(o[0])
def hx(a): return subprocess.run(['python3','agxparse.py',a,'--extract-hex'],capture_output=True,text=True).stdout.strip()
A=[float(i%13)-4.0 for i in range(64)]
with open('ain.bin','wb') as f: f.write(struct.pack('<64f',*A))
with open('ac.bin','wb') as f: f.write(struct.pack('<I',0))
for fn,pat,ins,outs,grid,tg in [('k_atomic','07220200',{1:'ain.bin',2:'ac.bin'},{0:256},32,32),
                                ('k_sgred','87860282',{1:'ain.bin'},{0:256},32,32)]:
    arc=build(fn,f'cc_{fn}.bin'); h=hx(arc); i=h.find(pat)
    print(f'=== {fn} pat@{i//2 if i>=0 else -1}', 'bytes',h[i:i+8] if i>=0 else 'NOT FOUND')
    if i<0: continue
    base=loc(arc)+i//2
    r=PersistRunner(source=K,function=fn,fast_math=False,agxrun_persist='./agxrun_persist')
    b=r.request(archive=arc,grid=grid,tg=tg,ins=ins,outs=outs,timeout=10)
    bv=struct.unpack('<64f',b['outs'][0])[:6] if 0 in b['outs'] else None
    print('  baseline',b['status'],[round(x,3) for x in bv] if bv else None)
    for off in range(0,4):
        shutil.copyfile(arc,'pc.bin')
        with open('pc.bin','r+b') as f: f.seek(base+off); f.write(bytes([0x55]))
        rr=r.request(archive='pc.bin',grid=grid,tg=tg,ins=ins,outs=outs,timeout=10)
        v=struct.unpack('<64f',rr['outs'][0])[:6] if 0 in rr['outs'] else None
        print(f'  +{off}=0x55 {rr["status"]:12s}',[round(x,3) for x in v] if v else rr.get('error'),
              'CHANGED' if v!=bv else 'same')
    r.close()
