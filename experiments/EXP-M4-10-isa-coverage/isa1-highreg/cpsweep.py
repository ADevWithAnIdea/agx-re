#!/usr/bin/env python3
# ISA-1 load/store register-field round-trip. Kernel: out[gid]=in[gid].
# load in[gid] -> dst reg (device_load +8); store that reg -> out (device_store +8).
# We COUPLE both operand bytes to (N<<1)|1 and confirm out==in for r0..r95, and a
# fault/miscompare at r96+. This is the exact assembler-correctness property for the
# 7-bit reg field in the memory forms. CLEAN-ROOM: own MSL only.
import subprocess, os, struct

# --- portable repo root (repo was relocated; anchor to a sentinel, not a hardcoded path) ---
import os
def _repo_root(start):
    d = os.path.abspath(start)
    while d != os.path.dirname(d):
        if os.path.isfile(os.path.join(d, 'CLAUDE.md')) and os.path.isdir(os.path.join(d, 'tools', 'agx-isa')):
            return d
        d = os.path.dirname(d)
    raise RuntimeError('repo root not found from ' + start)
_REPO = _repo_root(os.path.dirname(os.path.abspath(__file__)))
# --- end portable repo root ---
ROOT=_REPO; AGXTEST=os.path.join(ROOT,"tools/agxtest/agxtest.py")
HERE=os.path.dirname(os.path.abspath(__file__))
SRC=os.path.join(HERE,"kernels/cp.metal")
os.makedirs(os.path.join(HERE,"kernels"),exist_ok=True)
open(SRC,"w").write("""#include <metal_stdlib>
using namespace metal;
kernel void k(device int* out [[buffer(0)]],
              device const int* in [[buffer(1)]],
              uint gid [[thread_position_in_grid]]) {
    out[gid] = in[gid];
}
""")
# load @0x04 dst_width=+8 -> file off 0x0c ; store @0x12 data_width=+8 -> 0x1a
LOAD_DST=0x0c; STORE_SRC=0x1a
INVALS=[100+i for i in range(8)]

def run(splices):
    cmd=["python3",AGXTEST,"--source",SRC,"--function","k","--grid","8","--tg","8","--int",
         "--buf","1="+",".join(str(x) for x in INVALS),"--out","0=8"]
    for off,val in splices:
        cmd+=["--splice",f"_agc.main@0x{off:x}={val:02x}"]
    r=subprocess.run(cmd,capture_output=True,text=True)
    st=None;res=None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS"): st=line.split()[1]
        if line.startswith("RESULT"): res=line.split()[2:]
    return st,res

print("baseline:",run([]))
print("\n-- probe which byte is load-dst / store-src --")
print("splice store+8=0x51 (r40, match load):",run([(STORE_SRC,0x51)]))
print("splice load+8=0x11 (r8, match store): ",run([(LOAD_DST,0x11)]))
print("\n-- coupled round-trip: load-dst=store-src=(N<<1)|1 --")
for N in [0,1,7,8,15,16,31,32,40,63,64,65,79,95,96,100,127]:
    b=(N<<1)|1
    st,res=run([(LOAD_DST,b),(STORE_SRC,b)])
    ok = (res==[str(x) for x in INVALS]) if res else False
    print(f"  r{N:<3d} byte0x{b:02x}: STATUS={st:12s} out={res}  {'ROUNDTRIP-OK' if ok else 'DIFF/FAULT'}")
