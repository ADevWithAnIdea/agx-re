import struct, sys, os, subprocess, json
sys.path.insert(0,'.')
from persistrun import PersistRunner

def mk(vals, path):
    with open(path,'wb') as f: f.write(struct.pack('<%df'%len(vals), *vals))

# asymmetric 8x8 matrices
A=[ (i*8+j+1)*0.5 for i in range(8) for j in range(8)]
B=[ ((i*8+j)%7 - 3)*1.25 for i in range(8) for j in range(8)]
C=[ (i*8+j)*0.25 - 8.0 for i in range(8) for j in range(8)]
mk(A,'a.bin'); mk(B,'b.bin'); mk(C,'c.bin')
def matmul_acc(A,B,C):
    R=[0.0]*64
    for i in range(8):
        for j in range(8):
            s=0.0
            for k in range(8): s+= A[i*8+k]*B[k*8+j]
            R[i*8+j]=s+C[i*8+j]
    return R
oracle=matmul_acc(A,B,C)
r=PersistRunner(source='pilot_mm.metal', function='k_mad_f32', fast_math=False, agxrun_persist='./agxrun_persist')
resp=r.request(archive='pilot_mm.bin', grid=32, tg=32, ins={1:'a.bin',2:'b.bin',3:'c.bin'}, outs={0:256}, timeout=10)
print(resp['status'], resp.get('error'))
if 0 in resp['outs']:
    got=struct.unpack('<64f', resp['outs'][0])
    ok=all(abs(g-o)<1e-2*max(1,abs(o)) for g,o in zip(got,oracle))
    print("MATCH" if ok else "MISMATCH")
    print("got[:8] ", [round(x,3) for x in got[:8]])
    print("orac[:8]", [round(x,3) for x in oracle[:8]])
r.close()
