#!/usr/bin/env python3
# subgroup_test.py -- falsify simd_reduce (0xbf), simd_shuffle (0x47/0xc7),
# simd_ballot (0x17). Each kernel feeds distinct per-lane values; we splice the
# op-select bytes and read back all 32 lanes.
import sys, os, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from persistrun import PersistRunner

def locate(archive):
    out = subprocess.check_output(["python3","agxparse.py",archive,"--locate","_agc.main"], text=True)
    off, ln = out.split(); return int(off)

def u32(b):
    return [struct.unpack("<I", b[i*4:i*4+4])[0] for i in range(len(b)//4)]

def run_kernel(src, op_off, tests, grid=32, tg=32, nout=32):
    arch = os.path.basename(src).replace(".metal",".bin")
    subprocess.check_call(["./shdump","-o",arch,"--no-fast-math","-f","k",src])
    moff = locate(arch)
    base = bytearray(open(arch,"rb").read())
    print(f"\n===== {src}  (_agc.main abs {moff}, op@+0x{op_off:02x}) =====")
    print("op bytes:", bytes(base[moff+op_off:moff+op_off+10]).hex())
    r = PersistRunner(source=src, function="k", fast_math=False, agxrun_persist="./agxrun_persist")
    try:
        for name, patches in tests:
            buf = bytearray(base)
            for rel,val in patches:
                buf[moff+op_off+rel] = val
            open("sspl.bin","wb").write(buf)
            resp = r.request(archive="sspl.bin", grid=grid, tg=tg, ins={}, outs={0:nout*4}, timeout=8)
            if resp["status"]!="OK":
                print(f"  {name:52s} STATUS {resp['status']}")
                continue
            vals = u32(resp["outs"].get(0,b""))
            # compress: show first 8 + note if all-equal
            alleq = len(set(vals))==1
            shown = f"ALL={vals[0]}" if alleq else " ".join(str(v) for v in vals[:12])
            print(f"  {name:52s} {shown}")
    finally:
        r.close()

def main():
    # simd_reduce: baseline simd_sum(0..31)=496
    run_kernel("kernels/simd_reduce.metal", 0x08, [
        ("baseline simd_sum -> 496", []),
        ("byte0 0xbf->0x3f (bit7=0; doc: xor -> 0)", [(0,0x3f)]),
        ("byte+1 0x11->0x10", [(1,0x10)]),
        ("byte+1 0x11->0x12 (doc low-nib 2 = max/min)", [(1,0x12)]),
        ("byte+1 0x11->0x13 (doc low-nib 3 = umax)", [(1,0x13)]),
        ("byte+1 0x11->0x15", [(1,0x15)]),
        ("byte+1 0x11->0x17", [(1,0x17)]),
        ("byte+7 0x01->0x03 (doc int-reduce dtype)", [(7,0x03)]),
        ("byte+7 0x01->0x07 (doc int-minmax)", [(7,0x07)]),
    ])
    # simd_scan: inclusive prefix sum = lane*(lane+1)/2
    run_kernel("kernels/simd_scan.metal", 0x08, [
        ("baseline incl-scan -> 0,1,3,6,10,...", []),
        ("byte+7 0x09->0x0b (doc: exclusive-scan)", [(7,0x0b)]),
        ("byte0 0xbf->0x3f (bit7=0)", [(0,0x3f)]),
    ])
    # simd_bcast: broadcast lane3 (v=lane*10+5) -> 35
    run_kernel("kernels/simd_bcast.metal", 0x1c, [
        ("baseline broadcast(v,3) -> 35", []),
        ("byte+6 0x06->0x00 (lane0 -> 5)", [(6,0x00)]),
        ("byte+6 0x06->0x0a (lane5 -> 55)", [(6,0x0a)]),
        ("byte+6 0x06->0x0e (lane7 -> 75)", [(6,0x0e)]),
        ("byte0 0x47->0xc7 (dir bit flip)", [(0,0xc7)]),
        ("byte+1 0x04->0x00 (doc: quad mode)", [(1,0x00)]),
    ])
    # simd_xor: shuffle_xor(v,1) -> (lane^1)*10+5
    run_kernel("kernels/simd_xor.metal", 0x1c, [
        ("baseline shuffle_xor(v,1)", []),
        ("byte+6 0x02->0x04 (mask 2)", [(6,0x04)]),
        ("byte+6 0x02->0x08 (mask 4)", [(6,0x08)]),
        ("byte0 0xc7->0x47 (dir bit flip)", [(0,0x47)]),
    ])
    # simd_ballot: ballot(lane<5) -> 0x1F=31
    run_kernel("kernels/simd_ballot.metal", 0x08, [
        ("baseline ballot(lane<5) -> 31", []),
    ])

if __name__ == "__main__":
    main()
