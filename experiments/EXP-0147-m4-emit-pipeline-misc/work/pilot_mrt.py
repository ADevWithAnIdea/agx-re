import sys,shutil,subprocess,json
sys.path.insert(0,'.')
from rsdrv import RenderRunner
K='../kernels/pipe_render.metal'
def build(vs,fs,nrt=1,samples=1,out=None):
    out=out or f'b_{vs}_{fs}.bin'
    subprocess.run(['./shdump2','-o',out,'--render','--vertex',vs,'--fragment',fs,
                    '--color-format','125','--nrt',str(nrt),'--samples',str(samples),
                    '--no-fast-math',K],check=True,capture_output=True)
    return out
def loc(arc,stage):
    o=subprocess.run(['python3','agxparse.py',arc,'--stage',stage,'--locate','_agc.main'],capture_output=True,text=True).stdout.split()
    return int(o[0])
def hx(arc,stage):
    return subprocess.run(['python3','agxparse.py',arc,'--stage',stage,'--extract-hex'],capture_output=True,text=True).stdout.strip()
r=RenderRunner(K, exe='./rendersweep')
def run(arc,vs,fs,**kw):
    req={'id':'x','archive':arc,'vs':vs,'fs':fs,'w':1,'h':1,'nrt':1,'clear':[[0.25,0.5,-1.0,2.0]],
         'fbuf':[1.0,-2.0,3.0,0.5],'vbuf':[0.5,0.25,0.125,1.0]}
    req.update(kw); return r.request(req)
def probe(label,vs,fs,stage,pat,offs,nrt=1,samples=1,**kw):
    arc=build(vs,fs,nrt,samples)
    h=hx(arc,stage); i=h.find(pat)
    if i<0: print(label,'PATTERN NOT FOUND'); return
    base_off=loc(arc,stage)+i//2
    b=run(arc,vs,fs,nrt=nrt,samples=samples,**kw)
    print(f'--- {label} instr@{i//2} bytes={h[i:i+24]}')
    print('   baseline', b.get('pixels'), b.get('tex'), b['status'])
    for off in offs:
        shutil.copyfile(arc,'p.bin')
        with open('p.bin','r+b') as f: f.seek(base_off+off); f.write(bytes([0x55]))
        rr=run('p.bin',vs,fs,nrt=nrt,samples=samples,**kw)
        px=rr.get('pixels'); diff = px!=b.get('pixels') or rr.get('tex')!=b.get('tex')
        print(f'   +{off}=0x55 {rr["status"]:12s} {(px or [None])[0]} rt1={(px or [None,None])[-1] if px else None} {rr.get("tex","")} {"CHANGED" if diff else "same"}')
probe('tile_read_mrt','v_arr','f_mrt','fragment','670654',range(1,12),nrt=2,clear=[[0.25,0.5,-1.0,2.0],[3.0,-4.0,5.0,6.0]])
r.close()
