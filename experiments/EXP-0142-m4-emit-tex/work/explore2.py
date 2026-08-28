import os,sys,struct,subprocess,json
sys.path.insert(0,'../harness')
from texrunner import TexRunner
REPO=os.path.abspath('../../..')
AGXPARSE=os.path.join(REPO,'tools','shdump','agxparse.py')
src='probe_sample3.metal'; arch='probe_sample3.bin'
loc=subprocess.check_output(['python3',AGXPARSE,arch,'--locate','_agc.main']).decode().split()
ABS,LEN=int(loc[0]),int(loc[1])
base=open(arch,'rb').read(); main=base[ABS:ABS+LEN]
BUNDLE=main.find(bytes.fromhex('05800cb8b0000900000010000100'))
inbuf=os.path.abspath('in32.bin')
NOUT=52*4
r=TexRunner(source=src,function='k_sample',exe='./texpersist',samp_w=16,samp_h=16)
def run(off,val):
    b=bytearray(base); b[ABS+BUNDLE+off]=val
    p='spl.bin'; open(p,'wb').write(bytes(b))
    resp=r.request(archive=os.path.abspath(p),grid=1,tg=1,ins={0:inbuf},outs={1:NOUT},timeout=10)
    if resp['status']!='OK': return resp['status'],None
    return 'OK',struct.unpack('<52f',resp['outs'][1])
BASE={4:0xb0,5:0x00}
for off,name in ((5,'coord'),(4,'result_sel')):
    print("=== byte+%d (%s) ==="%(off-4,name))
    seen={}
    for v in range(0,256,1):
        st,o=run(off,v)
        if st!='OK': key=('S',st)
        else:
            # summarize: out0, and which of out[25..48] differs from out[1..24]
            diffs=[i for i in range(24) if o[25+i]!=o[1+i]]
            key=(round(o[0],4),tuple(diffs),tuple(round(o[25+i],3) for i in diffs))
        seen.setdefault(key,[]).append(v)
    for k,vs in sorted(seen.items(),key=lambda kv:kv[1][0]):
        rng=vs if len(vs)<=12 else [vs[0],vs[1],'...',vs[-1],'(n=%d)'%len(vs)]
        print("  ",k," <- ",rng)
r.close()
