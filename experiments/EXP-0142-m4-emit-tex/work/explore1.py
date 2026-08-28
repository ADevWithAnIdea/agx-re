import os,sys,struct,subprocess,shutil,json
sys.path.insert(0,'../harness')
from texrunner import TexRunner
REPO=os.path.abspath('../../..')
AGXPARSE=os.path.join(REPO,'tools','shdump','agxparse.py')
src='probe_sample3.metal'; arch='probe_sample3.bin'
loc=subprocess.check_output(['python3',AGXPARSE,arch,'--locate','_agc.main']).decode().split()
ABS,LEN=int(loc[0]),int(loc[1]); print("main at",ABS,LEN)
base=open(arch,'rb').read()
main=base[ABS:ABS+LEN]
BUNDLE=main.find(bytes.fromhex('05800cb8b0000900000010000100'))
print("bundle rel offset",BUNDLE, main[BUNDLE:BUNDLE+14].hex())
inbuf='in32.bin'
with open(inbuf,'wb') as f:
    f.write(b''.join(struct.pack('<f', i+0.5) for i in range(32)))
NOUT=52*4
r=TexRunner(source=src,function='k_sample',exe='./texpersist',samp_w=16,samp_h=16)
print("device",r.device)
def run(splices,tag):
    b=bytearray(base)
    for (off,val) in splices: b[ABS+BUNDLE+off]=val
    p='spl.bin'; open(p,'wb').write(bytes(b))
    resp=r.request(archive=os.path.abspath(p),grid=1,tg=1,ins={0:os.path.abspath(inbuf)},outs={1:NOUT},timeout=10)
    if resp['status']!='OK': return resp['status'],None
    o=struct.unpack('<52f',resp['outs'][1])
    return 'OK',o
st,o=run([],'baseline')
print("baseline",st)
print(" out0=",o[0]," out1..8=",o[1:9], " out25..32=",o[25:33], " out49..51=",o[49:52])
