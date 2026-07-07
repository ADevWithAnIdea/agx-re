#!/usr/bin/env python3
# scan_test.py -- pin the inclusive/exclusive-scan discriminator.
# incl-scan compiled: bf 11 54 00 03 04 14 09  (byte+3=0x03, byte+7=0x09)
# excl-scan compiled: bf 11 54 00 02 04 14 09  (byte+3=0x02, byte+7=0x09)
# Doc claims byte+7 0x09=incl / 0x0b=excl. Test whether byte+3 is the real toggle.
import sys, os, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from persistrun import PersistRunner

def locate(a):
    o=subprocess.check_output(["python3","agxparse.py",a,"--locate","_agc.main"],text=True); return int(o.split()[0])
def u32(b): return [struct.unpack("<I",b[i*4:i*4+4])[0] for i in range(len(b)//4)]

def go(src, op_off, tests):
    arch=os.path.basename(src).replace(".metal",".bin")
    subprocess.check_call(["./shdump","-o",arch,"--no-fast-math","-f","k",src])
    moff=locate(arch); base=bytearray(open(arch,"rb").read())
    print(f"\n== {src} op@+0x{op_off:02x}: {bytes(base[moff+op_off:moff+op_off+8]).hex()}")
    r=PersistRunner(source=src,function="k",fast_math=False,agxrun_persist="./agxrun_persist")
    try:
        for name,patches in tests:
            buf=bytearray(base)
            for rel,val in patches: buf[moff+op_off+rel]=val
            open("scspl.bin","wb").write(buf)
            resp=r.request(archive="scspl.bin",grid=32,tg=32,ins={},outs={0:32*4},timeout=8)
            vals=u32(resp["outs"].get(0,b"")) if resp["status"]=="OK" else []
            print(f"  {name:44s} {resp['status']:6s} {' '.join(str(v) for v in vals[:10])}")
    finally: r.close()

# inclusive baseline 0,1,3,6,10,...  ; exclusive 0,0,1,3,6,...
go("kernels/simd_scan.metal", 0x08, [
    ("incl baseline (0,1,3,6,10)", []),
    ("byte+3 0x03->0x02 (=excl encoding?)", [(3,0x02)]),
])
go("kernels/simd_exclscan.metal", 0x08, [
    ("excl baseline (0,0,1,3,6)", []),
    ("byte+3 0x02->0x03 (=incl encoding?)", [(3,0x03)]),
])
