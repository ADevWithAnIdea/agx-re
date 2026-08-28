import sys,os,struct,json,collections
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from lib import *
wd=os.path.join(EXP,'work','pilot'); K=os.path.join(wd,'k')
def bf(x): return bf16_bits_rne(x)
name=sys.argv[1]; INSTR=int(sys.argv[2],0); LEN=int(sys.argv[3]); mode=sys.argv[4]
buf,off,main=load_base(os.path.join(K,name+'.bin'))
print(name,'instr at +0x%02x len %d :'%(INSTR,LEN), main[INSTR:INSTR+LEN].hex())
def w16(path,vals):
    open(path,'wb').write(b''.join(struct.pack('<H',v) for v in vals)); return path
SETS=[('S1',3.0,5.0),('S2',17.0,9.0)]
ins={}
for nm,a,b in SETS:
    if mode=='bf':
        ins[nm]={1:w16(os.path.join(wd,'na_%s.bin'%nm),[bf(a)]*8), 2:w16(os.path.join(wd,'nb_%s.bin'%nm),[bf(b)]*8)}
    elif mode=='f32':
        ins[nm]={1:wf(os.path.join(wd,'fa_%s.bin'%nm),[a]*8), 2:wf(os.path.join(wd,'fb_%s.bin'%nm),[b]*8)}
r=PersistRunner(source=os.path.join(K,name+'.metal'),function='k',fast_math=False,
                agxrun_persist=os.path.join(EXP,'work','bin','agxrun_persist'))
arch=os.path.join(wd,'sp2.bin')
groups=collections.OrderedDict()
for bi in range(LEN):
    g=collections.OrderedDict()
    for v in range(256):
        sp=bytearray(buf); sp[off+INSTR+bi]=v
        open(arch,'wb').write(bytes(sp))
        key=[]
        for nm,a,b in SETS:
            resp=r.request(archive=arch,grid=1,tg=1,ins=ins[nm],outs={0:4},timeout=8)
            key.append(resp['status']); key.append(resp['outs'].get(0,b'').hex())
        g.setdefault(tuple(key),[]).append(v)
    print('='*70); print('BYTE +%d  (baseline %02x)'%(bi,main[INSTR+bi]))
    for k,vs in g.items():
        def rng(vs):
            vs=sorted(vs); out=[];s=p=vs[0]
            for v in vs[1:]:
                if v==p+1: p=v
                else: out.append((s,p)); s=p=v
            out.append((s,p)); return ','.join('%02x'%a if a==b else '%02x-%02x'%(a,b) for a,b in out)
        def dec(h):
            if len(h)!=8: return '-'
            raw=bytes.fromhex(h); u=struct.unpack('<I',raw)[0]
            return 'u32=%08x lo16bf=%g hi16bf=%g f32=%g'%(u,bf2f(u&0xFFFF),bf2f(u>>16),struct.unpack('<f',raw)[0])
        print('  n=%3d %-6s %s | %-6s %s'%(len(vs),k[0],dec(k[1]),k[2],dec(k[3])))
        print('        vals=%s'%rng(vs)[:170])
r.close()
