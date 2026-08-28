import os,struct,sys,time,importlib.util,json
REPO='/Users/user/asahi_re/public/agx-re'
EXP=os.path.join(REPO,'experiments','EXP-0145-m4-emit-bf16-half')
def lm(n,p):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse=lm('agxparse',os.path.join(REPO,'tools','shdump','agxparse.py'))
PR=lm('persistrun',os.path.join(REPO,'tools','agxtest','persistrun.py')).PersistRunner
wd=os.path.join(EXP,'work','pilot')
base=os.path.join(wd,'p_bfadd.bin'); buf=open(base,'rb').read()
off,ln=agxparse.locate_region(buf,'_agc.main')
SETS=[('S1',3.0,5.0),('S2',17.0,9.0)]
for nm,a,b in SETS:
    open(os.path.join(wd,'a_%s.bin'%nm),'wb').write(struct.pack('<f',a)*8)
    open(os.path.join(wd,'b_%s.bin'%nm),'wb').write(struct.pack('<f',b)*8)
r=PR(source=os.path.join(EXP,'kernels','p_bfadd.metal'),function='k',fast_math=False,
     agxrun_persist=os.path.join(EXP,'work','bin','agxrun_persist'))
arch=os.path.join(wd,'sp.bin')
INSTR=0x30
out=open(os.path.join(wd,'explore_bfadd.jsonl'),'w')
t0=time.time()
for bi in range(8):
    for v in range(256):
        sp=bytearray(buf); sp[off+INSTR+bi]=v
        open(arch,'wb').write(bytes(sp))
        rec={'byte':bi,'value':v,'res':{}}
        for nm,a,b in SETS:
            resp=r.request(archive=arch,grid=1,tg=1,
                ins={1:os.path.join(wd,'a_%s.bin'%nm),2:os.path.join(wd,'b_%s.bin'%nm)},
                outs={0:4},timeout=8)
            o=resp['outs'].get(0,b'')
            rec['res'][nm]={'st':resp['status'],'hex':o.hex()}
        out.write(json.dumps(rec)+'\n'); out.flush()
    print('byte',bi,'done %.1fs'%(time.time()-t0))
r.close(); out.close()
