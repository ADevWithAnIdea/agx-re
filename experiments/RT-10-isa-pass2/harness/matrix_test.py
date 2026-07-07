#!/usr/bin/env python3
# RT-10 Part3: re-confirm the 0xcf matrix_mac operand map (A=+5 B=+6 C=+7 dst=+8 accum=+11)
# with a DIFFERENT kernel (p3_matmul_f32: D=buf0, A=buf1, B=buf2, C=buf3) and DIFFERENT values
# than RT-5.  A[i][j]=i+1, B[i][j]=j+1, C=500:
#   A*B = 8(i+1)(j+1)          (varies i AND j)
#   B*A = sum_k (k+1)^2 = 204  (constant everywhere)
#   A*A = 36(i+1)              (varies row i only)
#   B*B = 36(j+1)              (varies col j only)
#   +C adds 500.
import sys, os, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from persistrun import PersistRunner

SRC = "k/p3_matmul_f32.metal"; ARCH = "m32.bin"

def f32(vals): return b"".join(struct.pack("<f", float(v)) for v in vals)
def locate(a):
    o = subprocess.check_output(["python3","agxparse.py",a,"--stage","compute","--locate","_agc.main"],text=True)
    return int(o.split()[0])
def build():
    A=[float(i+1) for i in range(8) for j in range(8)]   # A[i][j]=i+1
    B=[float(j+1) for i in range(8) for j in range(8)]    # B[i][j]=j+1
    C=[500.0]*64
    open("mA.bin","wb").write(f32(A)); open("mB.bin","wb").write(f32(B)); open("mC.bin","wb").write(f32(C))
def show(name, resp):
    b = resp["outs"].get(0, b"")
    if resp["status"]!="OK" or len(b)<256:
        print(f"[{name}] STATUS {resp['status']} {resp.get('error','')}"); return
    d=[struct.unpack("<f",b[i*4:i*4+4])[0] for i in range(64)]
    print(f"[{name}] D[0][0..3]={d[0]:.0f},{d[1]:.0f},{d[2]:.0f},{d[3]:.0f}  D[1][0]={d[8]:.0f}  D[7][7]={d[63]:.0f}")

def main():
    subprocess.check_call(["./shdump","-o",ARCH,"--no-fast-math","-f","k",SRC])
    moff=locate(ARCH); base=bytearray(open(ARCH,"rb").read()); build()
    ins={1:"mA.bin",2:"mB.bin",3:"mC.bin"}; outs={0:256}
    OP=0xba
    print("baseline op bytes:", bytes(base[moff+OP:moff+OP+12]).hex())
    r=PersistRunner(source=SRC,function="k",fast_math=False,agxrun_persist="./agxrun_persist")
    def run(name,patches):
        buf=bytearray(base)
        for rel,v in patches: buf[moff+OP+rel]=v
        open("mspl.bin","wb").write(buf)
        show(name, r.request(archive="mspl.bin",grid=32,tg=32,ins=ins,outs=outs,timeout=10))
    try:
        run("baseline A*B+C  expect D00=508 D01=516 D10=516 D77=1012", [])
        run("+5 (A reg) 0x04->0x08 = B reg  expect B*B+C=36(j+1)+500: D00=536 D01=572 D10=536(row-indep)", [(5,0x08)])
        run("+6 (B reg) 0x08->0x04 = A reg  expect A*A+C=36(i+1)+500: D00=536 D01=536(col-indep) D10=572", [(6,0x04)])
        run("swap +5=0x08 +6=0x04           expect B*A+C=204+500=704 everywhere", [(5,0x08),(6,0x04)])
        run("+11 accum 0x01->0x00           expect A*B only=8(i+1)(j+1): D00=8 D77=512", [(11,0x00)])
        run("+7 (C reg) 0x09->0x00          probe C accumulator source", [(7,0x00)])
        run("+8 (dst)  0xd4->0xd6           probe dst reg", [(8,0xd6)])
    finally:
        r.close()

if __name__=="__main__": main()
