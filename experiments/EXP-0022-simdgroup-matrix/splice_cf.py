#!/usr/bin/env python3
# EXP-0022 splice-validation of the 0xcf matrix-MAC instruction (runs ON DEVICE).
# Locates the single 0xcf op in mad_f32 and splices the candidate accumulate bits
# to prove that simdgroup_multiply_accumulate(r,a,b,c) => r=a*b+c and that
# clearing those bits turns it into a pure multiply r=a*b (C ignored).
# CLEAN-ROOM: only OUR OWN compiled+spliced bytes run.
import os, struct, subprocess, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
def load_mod(n,p):
    s=importlib.util.spec_from_file_location(n,p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
agxparse=load_mod("agxparse",os.path.join(HERE,"agxparse.py"))
PersistRunner=load_mod("persistrun",os.path.join(HERE,"persistrun.py")).PersistRunner

def packf(v): return b"".join(struct.pack('<f',float(x)) for x in v)
def unpackf(r,n): return [struct.unpack_from('<f',r,k*4)[0] for k in range(n)]
def matmul(A,B,C,N=8):
    R=[0.0]*(N*N)
    for i in range(N):
        for j in range(N):
            s=C[i*N+j]
            for k in range(N): s+=A[i*N+k]*B[k*N+j]
            R[i*N+j]=s
    return R
def close(R,E,tol=1e-2): return len(R)==len(E) and all(abs(a-b)<=tol*(1+abs(b)) for a,b in zip(R,E))

src=os.path.join(HERE,"kernels","mat.metal"); N=8
A=[float((i*8+j)%7-3) for i in range(N) for j in range(N)]
B=[float(((i*3+j*5)%9)-4) for i in range(N) for j in range(N)]
C=[float(10+i*8+j) for i in range(N) for j in range(N)]   # large, distinct from A*B
Z=[0.0]*(N*N)
AB=matmul(A,B,Z); ABC=matmul(A,B,C)

# build mad_f32, find the cf op offset in _agc.main
base=os.path.join(HERE,"work","mad_f32.bin"); os.makedirs(os.path.join(HERE,"work"),exist_ok=True)
subprocess.run(["./shdump","-o",base,"-f","mad_f32","--no-fast-math",src],check=True,capture_output=True,text=True)
buf=open(base,"rb").read(); off,length=agxparse.locate_region(buf,"_agc.main")
main=buf[off:off+length]
cfpos=main.find(bytes.fromhex("cf0256"))
print(f"cf op at main offset {cfpos}: {main[cfpos:cfpos+12].hex()}")

def run(splices,ins):
    b=bytearray(buf)
    for mo,val in splices.items(): b[off+mo]=val
    arch=os.path.join(HERE,"work","mad_sp.bin"); open(arch,"wb").write(b)
    ip={}
    for idx,v in ins.items():
        p=os.path.join(HERE,"work",f"sp_{idx}.bin"); open(p,"wb").write(packf(v)); ip[idx]=p
    r=PersistRunner(source=src,function="mad_f32",fast_math=False,agxrun_persist="./agxrun_persist")
    try: resp=r.request(archive=arch,grid=32,tg=32,ins=ip,outs={3:N*N*4},timeout=10)
    finally: r.close()
    return resp

ins={0:A,1:B,2:C}
# baseline (no splice)
r=run({},ins); R=unpackf(r["outs"][3],N*N) if r["status"]=="OK" else []
print(f"baseline           status={r['status']}  ==A*B+C:{close(R,ABC)}  ==A*B:{close(R,AB)}")
# splice +11 (01->00)
r=run({cfpos+11:0x00},ins); R=unpackf(r["outs"][3],N*N) if r["status"]=="OK" else []
print(f"splice +11 01->00  status={r['status']}  ==A*B+C:{close(R,ABC)}  ==A*B:{close(R,AB)}")
# splice +9 (43->41, clear bit1)
r=run({cfpos+9:0x41},ins); R=unpackf(r["outs"][3],N*N) if r["status"]=="OK" else []
print(f"splice +9  43->41  status={r['status']}  ==A*B+C:{close(R,ABC)}  ==A*B:{close(R,AB)}")
# splice +7 (09->00, C operand reg)
r=run({cfpos+7:0x00},ins); R=unpackf(r["outs"][3],N*N) if r["status"]=="OK" else []
print(f"splice +7  09->00  status={r['status']}  ==A*B+C:{close(R,ABC)}  ==A*B:{close(R,AB)}")
# splice all three to match mul_f32 exactly
r=run({cfpos+7:0x00,cfpos+9:0x41,cfpos+11:0x00},ins); R=unpackf(r["outs"][3],N*N) if r["status"]=="OK" else []
print(f"splice +7/+9/+11   status={r['status']}  ==A*B+C:{close(R,ABC)}  ==A*B:{close(R,AB)}")
