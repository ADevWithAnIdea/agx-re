import os,struct,sys,time,importlib.util
HERE=os.path.dirname(os.path.abspath(__file__)); EXP=os.path.dirname(os.path.dirname(HERE)); REPO='/Users/user/asahi_re/public/agx-re'
EXP=os.path.join(REPO,'experiments','EXP-0145-m4-emit-bf16-half')
def lm(n,p):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse=lm('agxparse',os.path.join(REPO,'tools','shdump','agxparse.py'))
PR=lm('persistrun',os.path.join(REPO,'tools','agxtest','persistrun.py')).PersistRunner
base=os.path.join(EXP,'work','pilot','p_bfadd.bin')
buf=open(base,'rb').read()
off,ln=agxparse.locate_region(buf,'_agc.main')
_,pieces=agxparse.extract_agx(buf); main=pieces['_agc.main']
print('region',off,ln,'mainlen',len(main))
wd=os.path.join(EXP,'work','pilot'); 
for nm,vals in (('in_a',[3.0]*8),('in_b',[5.0]*8)):
    open(os.path.join(wd,nm+'.bin'),'wb').write(b''.join(struct.pack('<f',v) for v in vals))
r=PR(source=os.path.join(EXP,'kernels','p_bfadd.metal'),function='k',fast_math=False,
     agxrun_persist=os.path.join(EXP,'work','bin','agxrun_persist'))
print('READY',r.device)
arch=os.path.join(wd,'sp.bin')
t0=time.time(); n=0
for v in range(32):
    sp=bytearray(buf); sp[off+0x33]=v
    open(arch,'wb').write(bytes(sp))
    resp=r.request(archive=arch,grid=1,tg=1,ins={1:os.path.join(wd,'in_a.bin'),2:os.path.join(wd,'in_b.bin')},outs={0:4},timeout=8)
    n+=1
    if v<8 or resp['status']!='OK':
        o=resp['outs'].get(0,b'')
        f=struct.unpack('<f',o)[0] if len(o)==4 else None
        print('%02x %-12s %s %s'%(v,resp['status'],o.hex(),f))
dt=time.time()-t0
print('rate %.1f req/s (%d in %.1fs)'%(n/dt,n,dt))
r.close()
