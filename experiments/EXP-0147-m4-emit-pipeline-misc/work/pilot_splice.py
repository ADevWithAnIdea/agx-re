import struct, sys, shutil, time
sys.path.insert(0,'.')
from persistrun import PersistRunner
ABS=7872; MMOFF=186
A=[ (i*8+j+1)*0.5 for i in range(8) for j in range(8)]
B=[ ((i*8+j)%7 - 3)*1.25 for i in range(8) for j in range(8)]
C=[ (i*8+j)*0.25 - 8.0 for i in range(8) for j in range(8)]
def matmul_acc():
    R=[0.0]*64
    for i in range(8):
        for j in range(8):
            s=sum(A[i*8+k]*B[k*8+j] for k in range(8)); R[i*8+j]=s+C[i*8+j]
    return R
oracle=matmul_acc()
def splice(off_in_instr, val, out):
    shutil.copyfile('pilot_mm.bin', out)
    with open(out,'r+b') as f:
        f.seek(ABS+MMOFF+off_in_instr); f.write(bytes([val]))
r=PersistRunner(source='pilot_mm.metal', function='k_mad_f32', fast_math=False, agxrun_persist='./agxrun_persist')
t0=time.monotonic()
for name,off,val in [("baseline",None,None),("mode54",2,0x54),("dstdesc00",9,0x00),("dstdescFF",9,0xff),("b11_03",11,0x03),("b11_FF",11,0xff),("acc00",11,0x00)]:
    arc='pilot_mm.bin'
    if off is not None:
        arc='sp.bin'; splice(off,val,arc)
    resp=r.request(archive=arc, grid=32, tg=32, ins={1:'a.bin',2:'b.bin',3:'c.bin'}, outs={0:256}, timeout=10)
    got=struct.unpack('<64f', resp['outs'][0]) if 0 in resp['outs'] else None
    if got is None: print(name, resp['status'], resp.get('error')); continue
    allzero=all(g==0.0 for g in got)
    m=all(abs(g-o)<1e-3 for g,o in zip(got,oracle))
    print(f"{name:12s} {resp['status']:6s} match={m} allzero={allzero} first4={[round(x,3) for x in got[:4]]}")
print("elapsed", round(time.monotonic()-t0,2), "for 7 reqs")
r.close()
