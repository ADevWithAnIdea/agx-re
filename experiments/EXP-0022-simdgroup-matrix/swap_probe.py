import os, struct, subprocess, importlib.util
HERE=os.path.dirname(os.path.abspath(__file__))
def lm(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
agxparse=lm("agxparse",os.path.join(HERE,"agxparse.py"))
PR=lm("persistrun",os.path.join(HERE,"persistrun.py")).PersistRunner
def pf(v): return b"".join(struct.pack('<f',float(x)) for x in v)
def uf(r,n): return [struct.unpack_from('<f',r,k*4)[0] for k in range(n)]
def mm(A,B,C,N=8):
    R=[0.0]*(N*N)
    for i in range(N):
        for j in range(N):
            s=C[i*N+j]
            for k in range(N): s+=A[i*N+k]*B[k*N+j]
            R[i*N+j]=s
    return R
def cl(R,E,t=1e-2): return len(R)==len(E) and all(abs(a-b)<=t*(1+abs(b)) for a,b in zip(R,E))
src=os.path.join(HERE,"kernels","mat.metal");N=8
A=[float((i*8+j)%7-3) for i in range(N) for j in range(N)]
B=[float(((i*3+j*5)%9)-4) for i in range(N) for j in range(N)]
C=[float(10+i*8+j) for i in range(N) for j in range(N)]
Z=[0.0]*(N*N)
base=os.path.join(HERE,"work","mad_f32.bin")
subprocess.run(["./shdump","-o",base,"-f","mad_f32","--no-fast-math",src],check=True,capture_output=True,text=True)
buf=open(base,"rb").read();off,length=agxparse.locate_region(buf,"_agc.main")
main=buf[off:off+length];cf=main.find(bytes.fromhex("cf0256"))
def run(sp):
    b=bytearray(buf)
    for mo,v in sp.items(): b[off+mo]=v
    arch=os.path.join(HERE,"work","mad_sw.bin");open(arch,"wb").write(b)
    ip={}
    for idx,v in {0:A,1:B,2:C}.items():
        p=os.path.join(HERE,"work",f"sw_{idx}.bin");open(p,"wb").write(pf(v));ip[idx]=p
    r=PR(source=src,function="mad_f32",fast_math=False,agxrun_persist="./agxrun_persist")
    try: resp=r.request(archive=arch,grid=32,tg=32,ins=ip,outs={3:N*N*4},timeout=10)
    finally: r.close()
    return uf(resp["outs"][3],N*N) if resp["status"]=="OK" else ([],resp["status"])
ABc=mm(A,B,C);BAc=mm(B,A,C)
print("cf =",main[cf:cf+12].hex(),"@",cf)
R=run({}); print(f"baseline          AB+C:{cl(R,ABc)} BA+C:{cl(R,BAc)}")
R=run({cf+3:0x04,cf+5:0x02}); print(f"swap +3<->+5      AB+C:{cl(R,ABc)} BA+C:{cl(R,BAc)}  (if BA+C: +3=A,+5=B)")
R=run({cf+3:0x00}); print(f"+3 ->0x00         AB+C:{cl(R,ABc)} BA+C:{cl(R,BAc)}  R[0:4]={[round(x,1) for x in (R[:4] if isinstance(R,list) and R and not isinstance(R[0],str) else [])]}")
R=run({cf+5:0x00}); print(f"+5 ->0x00         AB+C:{cl(R,ABc)} BA+C:{cl(R,BAc)}")
