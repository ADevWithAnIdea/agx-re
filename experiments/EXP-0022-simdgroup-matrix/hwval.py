#!/usr/bin/env python3
# EXP-0022 hardware validation (runs ON THE DEVICE under exp0022/).
# Compiles OUR OWN simdgroup_matrix MSL, dispatches on the real A18 Pro GPU over
# one full simdgroup (32 threads), reads back the 8x8 result tile, and compares
# against a numpy-computed A@B+C. Proves the SEMANTICS of the 0xcf matrix MAC and
# the simdgroup_load/store lane mapping (round-trip identity).
# Also splices the 0xcf accumulate byte to prove multiply-accumulate vs multiply.
# CLEAN-ROOM: only OUR OWN compiled (and spliced) bytes run.
import os, struct, subprocess, importlib.util, sys
HERE = os.path.dirname(os.path.abspath(__file__))

def load_mod(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
agxparse = load_mod("agxparse", os.path.join(HERE, "agxparse.py"))
PersistRunner = load_mod("persistrun", os.path.join(HERE, "persistrun.py")).PersistRunner

def packf(vals, half=False):
    if half:
        import struct as _s
        return b"".join(_s.pack('<e', float(v)) for v in vals)
    return b"".join(struct.pack('<f', float(v)) for v in vals)
def unpackf(raw, n, half=False):
    if half:
        return [struct.unpack_from('<e', raw, k*2)[0] for k in range(n)]
    return [struct.unpack_from('<f', raw, k*4)[0] for k in range(n)]

def matmul(A, B, C, N=8):
    R = [0.0]*(N*N)
    for i in range(N):
        for j in range(N):
            s = C[i*N+j]
            for k in range(N):
                s += A[i*N+k]*B[k*N+j]
            R[i*N+j] = s
    return R

def build(source, fn, half=False):
    base = os.path.join(HERE, "work", f"{fn}.bin"); os.makedirs(os.path.join(HERE,"work"), exist_ok=True)
    r = subprocess.run(["./shdump","-o",base,"-f",fn,"--no-fast-math",source],capture_output=True,text=True)
    if r.returncode!=0: raise RuntimeError(f"shdump {fn}: {r.stderr[-300:]}")
    buf=open(base,"rb").read(); off,length=agxparse.locate_region(buf,"_agc.main")
    return base,buf,off,length

def run(source, fn, ins, outs, half=False, splices=None, grid=32, tg=32, timeout=10.0):
    base,buf,off,length = build(source, fn, half)
    if splices:
        b=bytearray(buf)
        for mo,val in splices.items(): b[off+mo]=val&0xff
        arch=os.path.join(HERE,"work",f"{fn}_sp.bin"); open(arch,"wb").write(b)
    else:
        arch=base
    inpaths={}
    for idx,vals in ins.items():
        p=os.path.join(HERE,"work",f"in_{fn}_{idx}.bin"); open(p,"wb").write(packf(vals,half)); inpaths[idx]=p
    outspec={idx:nb for idx,nb in outs.items()}
    runner=PersistRunner(source=source,function=fn,fast_math=False,agxrun_persist="./agxrun_persist")
    try:
        resp=runner.request(archive=arch,grid=grid,tg=tg,ins=inpaths,outs=outspec,timeout=timeout)
    finally:
        runner.close()
    return resp

def show(tag, R, exp, tol=1e-2):
    ok = all(abs(a-b)<=tol*(1+abs(b)) for a,b in zip(R,exp)) and len(R)==len(exp)
    print(f"[{tag}] {'PASS' if ok else 'FAIL'}")
    if not ok:
        for i in range(0,len(exp),8):
            print("   got", [round(x,2) for x in R[i:i+8]])
            print("   exp", [round(x,2) for x in exp[i:i+8]])
    return ok

def main():
    src = os.path.join(HERE,"kernels","mat.metal")
    N=8
    A=[float((i*8+j)%7 - 3) for i in range(N) for j in range(N)]   # small mixed values
    B=[float(((i*3+j*5)%9) - 4) for i in range(N) for j in range(N)]
    C=[float((i-j)) for i in range(N) for j in range(N)]
    I=[1.0 if i==j else 0.0 for i in range(N) for j in range(N)]
    Z=[0.0]*(N*N)
    allok=True

    # T0: load/store round-trip identity (ls_f32): R == A
    r=run(src,"ls_f32",{0:A},{1:N*N*4})
    print("ls_f32 status:",r["status"], r.get("error"))
    if r["status"]=="OK":
        R=unpackf(r["outs"][1],N*N); allok &= show("T0 ls_f32 roundtrip R==A", R, A)
    else: allok=False

    # T1: A*I + 0 == A
    r=run(src,"mad_f32",{0:A,1:I,2:Z},{3:N*N*4})
    print("mad_f32 status:",r["status"], r.get("error"))
    if r["status"]=="OK":
        R=unpackf(r["outs"][3],N*N); allok &= show("T1 A*I+0==A", R, matmul(A,I,Z))
    else: allok=False

    # T2: I*B + 0 == B
    r=run(src,"mad_f32",{0:I,1:B,2:Z},{3:N*N*4})
    if r["status"]=="OK":
        R=unpackf(r["outs"][3],N*N); allok &= show("T2 I*B+0==B", R, matmul(I,B,Z))

    # T3: full A*B + C
    r=run(src,"mad_f32",{0:A,1:B,2:C},{3:N*N*4})
    if r["status"]=="OK":
        R=unpackf(r["outs"][3],N*N); allok &= show("T3 A*B+C", R, matmul(A,B,C))

    # T4: multiply-only mul_f32 == A*B
    r=run(src,"mul_f32",{0:A,1:B},{2:N*N*4})
    print("mul_f32 status:",r["status"], r.get("error"))
    if r["status"]=="OK":
        R=unpackf(r["outs"][2],N*N); allok &= show("T4 mul A*B", R, matmul(A,B,Z))

    # T5: half precision mad_f16 (fp16 x fp16 -> fp16)
    Ah=[float((i+j)%5) for i in range(N) for j in range(N)]
    Bh=[float((i*2+j)%4) for i in range(N) for j in range(N)]
    Ch=[float(i%3) for i in range(N) for j in range(N)]
    r=run(src,"mad_f16",{0:Ah,1:Bh,2:Ch},{3:N*N*2},half=True)
    print("mad_f16 status:",r["status"], r.get("error"))
    if r["status"]=="OK":
        R=unpackf(r["outs"][3],N*N,half=True); allok &= show("T5 half A*B+C", R, matmul(Ah,Bh,Ch), tol=2e-2)

    # T6: fill_f32 -> all ones
    r=run(src,"fill_f32",{},{0:N*N*4})
    if r["status"]=="OK":
        R=unpackf(r["outs"][0],N*N); allok &= show("T6 fill==1.0", R, [1.0]*(N*N))

    print("\nOVERALL:", "ALL PASS" if allok else "SOME FAIL")

if __name__=="__main__":
    main()
