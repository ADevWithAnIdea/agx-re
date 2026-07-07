#!/usr/bin/env python3
# rt_test.py -- falsify rt_intersect fields by splicing the compute _agc.main and
# tracing one ray against a built primitive AS (triangle at z=3) via rtrun.
# Baseline hit = [1, 3, 0, 0.2].
import subprocess, os
SRC="kernels/rt_query.metal"; ARCH="rtq.bin"
def locate():
    o=subprocess.check_output(["python3","agxparse.py",ARCH,"--stage","compute","--locate","_agc.main"],text=True)
    return int(o.split()[0])
def rtrun(archive, ray="0.2,0.2,0,0,0,1"):
    try:
        out=subprocess.check_output(["./rtrun","--archive",archive,"--source",SRC,"--function","k",
            "--no-fast-math","--ray",ray,"--out","4"],text=True,stderr=subprocess.STDOUT,timeout=20)
    except subprocess.CalledProcessError as e: return "FAULT:"+ (e.output.strip().splitlines()[-1] if e.output else "?")
    except subprocess.TimeoutExpired: return "HANG"
    for ln in out.splitlines():
        if ln.startswith("OUT "): return ln[4:]
    for ln in out.splitlines():
        if ln.startswith("STATUS") and "OK" not in ln: return ln
    return "?"
def main():
    subprocess.check_call(["./shdump","-o",ARCH,"--no-fast-math","-f","k",SRC])
    moff=locate(); base=bytearray(open(ARCH,"rb").read())
    OP=0x54  # traverse rt_intersect
    print(f"# _agc.main abs {moff}; traverse op@+0x{OP:02x} = {bytes(base[moff+OP:moff+OP+8]).hex()}")
    print("baseline (hit expect [1 3 0 0.2]):", rtrun(ARCH))
    def spl(name, patches, ray="0.2,0.2,0,0,0,1"):
        buf=bytearray(base)
        for rel,v in patches: buf[moff+OP+rel]=v
        open("rtspl.bin","wb").write(buf)
        print(f"  {name:44s} -> {rtrun('rtspl.bin',ray)}")
    print("-- byte+4 AS-select (baseline 0x8b primitive) --")
    spl("byte+4 0x8b->0x1b (instance AS)", [(4,0x1b)])
    spl("byte+4 0x8b->0xbb (motion AS)",   [(4,0xbb)])
    spl("byte+4 0x8b->0x00",               [(4,0x00)])
    print("-- byte0 result reg (baseline 0xe4, hi-nibble=reg) --")
    spl("byte0 0xe4->0x04 (result reg 0)",  [(0,0x04)])
    spl("byte0 0xe4->0x14 (result reg 1)",  [(0,0x14)])
    print("-- byte+2 mode (baseline 0x90 const-origin) --")
    spl("byte+2 0x90->0x10 (dyn-origin)",   [(2,0x10)])
    spl("byte+2 0x90->0xd0 (+fn-table)",    [(2,0xd0)])
    print("-- byte+3 ray/param reg (baseline 0xa6) --")
    spl("byte+3 0xa6->0x00", [(3,0x00)])
if __name__=="__main__": main()
