import os,sys,struct
sys.path.insert(0,'../../harness')
from texrunner import TexRunner
from renderrunner import RenderRunner
K='../../kernels'
print("=== A: tex_sample8 (compute+texture sample) ===")
r=TexRunner(source=K+'/tex_sample8.metal',function='k_sample',exe='./texpersist',samp_w=16,samp_h=16)
print("device",r.device)
resp=r.request(archive=os.path.abspath('cA_sample8.bin'),grid=1,tg=1,
               ins={0:os.path.abspath('inA.bin')},outs={1:132},timeout=15)
print("status",resp['status'],resp.get('error'))
if resp['status']=='OK':
    o=struct.unpack('<33f',resp['outs'][1])
    for j in range(8): print("  q%d ="%j,[round(x,3) for x in o[4*j:4*j+4]])
    print("  sentinel out[32] =",o[32])
r.close()
print("=== B: tex_write3 (compute+texture write) ===")
r=TexRunner(source=K+'/tex_write3.metal',function='k_write',exe='./texpersist',write_w=8,write_h=8)
resp=r.request(archive=os.path.abspath('cB_write3.bin'),grid=1,tg=1,
               ins={0:os.path.abspath('inB.bin')},outs={1:4},texread=True,timeout=15)
print("status",resp['status'],resp.get('error'))
if resp['status']=='OK':
    print("  sentinel out[0] =",struct.unpack('<f',resp['outs'][1])[0])
    t=struct.unpack('<%df'%(8*8*4),resp['tex'])
    for (x,y) in [(1,0),(3,2),(5,4),(0,0),(7,7)]:
        i=(y*8+x)*4; print("  texel(%d,%d) ="%(x,y),[round(v,3) for v in t[i:i+4]])
r.close()
print("=== C: frag_deriv (render) ===")
r=RenderRunner(source=K+'/frag_deriv.metal',vertex='v_main',fragment='f_main',
               exe='./renderpersist',width=4,height=4)
print("device",r.device)
resp=r.request(archive=os.path.abspath('cC_deriv.bin'),ins={0:os.path.abspath('inC.bin')},timeout=15)
print("status",resp['status'],resp.get('error'))
if resp['status']=='OK':
    p=struct.unpack('<%df'%(4*4*4),resp['pixels'])
    for i in range(0,16,5): print("  px%d ="%i,[round(v,3) for v in p[4*i:4*i+4]])
r.close()
