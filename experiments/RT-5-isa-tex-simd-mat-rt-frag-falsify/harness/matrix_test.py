#!/usr/bin/env python3
# matrix_test.py -- falsify the 0xcf matrix_mac operand map (A=+5 B=+6 C=+7 dst=+8 accum=+11).
# Baseline D = A*B + C with A[i][j]=i, B[i][j]=j, C=1000:
#   A*B = 8ij, B*A = 140 (const), A*A = 28i, B*B = 28j; +C adds 1000.
# Runs named splices on the real GPU and prints the 8x8 result so we can see which
# operand each byte selects.
import sys, os, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from persistrun import PersistRunner

SRC = "kernels/matmul.metal"
ARCH = "matmul.bin"

def f32(vals): return b"".join(struct.pack("<f", float(v)) for v in vals)

def locate(archive):
    out = subprocess.check_output(["python3", "agxparse.py", archive, "--locate", "_agc.main"], text=True)
    off, ln = out.split(); return int(off), int(ln)

def build_inputs():
    A = [ (i) for i in range(8) for j in range(8) ]      # A[i][j]=i
    B = [ (j) for i in range(8) for j in range(8) ]      # B[i][j]=j
    C = [ 1000.0 for _ in range(64) ]
    open("mA.bin","wb").write(f32(A))
    open("mB.bin","wb").write(f32(B))
    open("mC.bin","wb").write(f32(C))

def show(name, resp):
    b = resp["outs"].get(3, b"")
    if resp["status"] != "OK" or len(b) < 256:
        print(f"[{name}] STATUS {resp['status']} {resp.get('error','')}")
        return None
    d = [struct.unpack("<f", b[i*4:i*4+4])[0] for i in range(64)]
    print(f"[{name}] STATUS OK  D=")
    for i in range(8):
        print("   " + " ".join(f"{d[i*8+j]:8.1f}" for j in range(8)))
    return d

def main():
    subprocess.check_call(["./shdump","-o",ARCH,"--no-fast-math","-f","k",SRC])
    moff,_ = locate(ARCH)
    print(f"# _agc.main at abs {moff}")
    base = bytearray(open(ARCH,"rb").read())
    build_inputs()
    ins = {0:"mA.bin",1:"mB.bin",2:"mC.bin"}
    outs = {3:256}   # 64 floats * 4 bytes
    OP = 0xba  # matrix op offset within _agc.main
    runner = PersistRunner(source=SRC, function="k", fast_math=False, agxrun_persist="./agxrun_persist")
    def run(name, patches):
        buf = bytearray(base)
        for rel,val in patches:
            buf[moff+OP+rel] = val
        open("mspl.bin","wb").write(buf)
        resp = runner.request(archive="mspl.bin", grid=32, tg=32, ins=ins, outs=outs, timeout=10)
        return show(name, resp)
    try:
        print("baseline op bytes:", bytes(base[moff+OP:moff+OP+12]).hex())
        run("baseline A*B+C  (expect 8ij+1000)", [])
        run("a_reg(+5)=b_reg 0x08  (expect B*B+C = 28j+1000)", [(5,0x08)])
        run("b_reg(+6)=a_reg 0x04  (expect A*A+C = 28i+1000)", [(6,0x04)])
        run("swap +5<->+6          (expect B*A+C = 140+1000=1140)", [(5,0x08),(6,0x04)])
        run("accum(+11) 0x01->0x00 (expect A*B only = 8ij)", [(11,0x00)])
        run("c_src(+7)=a_reg 0x04  (probe: C sourced from A's reg?)", [(7,0x04)])
        run("dst(+8) 0xd4->0xd6    (probe: store reads stale reg?)", [(8,0xd6)])
    finally:
        runner.close()

if __name__ == "__main__":
    main()
