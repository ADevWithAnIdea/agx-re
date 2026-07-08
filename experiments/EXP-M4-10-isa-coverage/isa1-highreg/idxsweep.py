#!/usr/bin/env python3
# ISA-1 high-register READ instrument via device_load index_reg (byte+5).
# A fold-resistant pressure kernel parks K distinct small index values in K live
# registers (n=1 -> a_k = in[k] = k). One indexed load `out = in[a0]` reads the
# index from the register named by device_load byte+5. Splicing that byte to
# (N<<1)|1 makes the load read the index parked in physical register N; since
# in[j]=j, the observed out == content(register N). Sweeping N over the whole file
# yields the physical-register->value map, proving the operand byte encoding
# (reg<<1)|size addresses r0..r95 distinctly (no mod-64), and what r96+ does.
# CLEAN-ROOM: our own MSL only.
import subprocess, os, struct, importlib.util, sys

ROOT="/Users/user/cleanroom_gpu"; AGXTEST=os.path.join(ROOT,"tools/agxtest/agxtest.py")
HERE=os.path.dirname(os.path.abspath(__file__)); WORK=os.path.join(HERE,"work")
os.makedirs(WORK,exist_ok=True); os.makedirs(os.path.join(HERE,"kernels"),exist_ok=True)
sys.path.insert(0,'/Users/user/cleanroom_gpu/tools/agx-isa'); import isadb
spec=importlib.util.spec_from_file_location("compdump",os.path.join(HERE,"../isa2-saturate/compdump.py"))
cd=importlib.util.module_from_spec(spec); spec.loader.exec_module(cd)

K=88
def gen(K):
    L=["#include <metal_stdlib>","using namespace metal;",
       "kernel void k(device uint* out [[buffer(0)]],",
       "              device const uint* in [[buffer(1)]],",
       "              constant uint& n [[buffer(2)]],",
       "              uint gid [[thread_position_in_grid]]) {"]
    for k in range(K): L.append(f"  uint a{k}=in[{k}];")
    L.append("  for(uint i=1;i<n;i++){ uint t=in[i];")
    for k in range(K): L.append(f"    a{k}=a{k}*t+a{(k+1)%K};")
    L.append("  }")
    L.append("  out[gid]=in[a0];")   # indexed load: index register = reg(a0)
    L.append("}")
    return "\n".join(L)+"\n"
SRC=os.path.join(HERE,"kernels/idxprobe.metal"); open(SRC,"w").write(gen(K))

# in[j]=j so out==index value==content(rN). n=1 raw file.
NFILE=os.path.join(WORK,"n1.bin"); open(NFILE,"wb").write(struct.pack("<I",1))
INVALS=list(range(K))

# find the FINAL device_load (the indexed out=in[a0]) and its byte+5 offset in _agc.main
mb=cd.compile_main(SRC,"k",True)
off=0; last_load=None
while off<len(mb):
    L=isadb.instr_length(mb,off)
    if L is None: off+=2; continue
    if mb[off]==0x67 and L==14: last_load=off
    off+=L
assert last_load is not None
IDX_OFF=last_load+5
print(f"K={K} main_len={len(mb)} final device_load @0x{last_load:x} index_reg byte @0x{IDX_OFF:x} baseline=0x{mb[IDX_OFF]:02x} (r{mb[IDX_OFF]>>1})")

def run(byteval):
    cmd=["python3",AGXTEST,"--source",SRC,"--function","k","--grid","1","--tg","1","--int",
         "--buf","1="+",".join(map(str,INVALS)),"--buf",f"2=@{NFILE}","--out","0=1"]
    if byteval is not None: cmd+=["--splice",f"_agc.main@0x{IDX_OFF:x}={byteval:02x}"]
    r=subprocess.run(cmd,capture_output=True,text=True)
    st=res=None
    for line in r.stdout.splitlines():
        if line.startswith("STATUS"): st=line.split()[1]
        if line.startswith("RESULT"): res=line.split()[2:]
    return st,(res[0] if res else None)

print("baseline (no splice):",run(None))
print("\n physreg | (reg<<1)|1 -> observed content")
themap={}
for N in range(0,128):
    st,v=run((N<<1)|1)
    themap[N]=(st,v)
# print concise: only N in target set + any that returned a valid distinct index
targets=[0,1,15,16,31,32,47,48,63,64,65,79,80,95,96,97,127]
for N in targets:
    st,v=themap[N]
    print(f"  r{N:<3d} 0x{(N<<1)|1:02x}: STATUS={st:12s} content={v}")
# summarize distinctness / mod-64
def val(N):
    st,v=themap[N]; return v if st=='OK' else f'[{st}]'
print("\n mod-64 pairs (rX vs rX+64), both should differ if no aliasing:")
for X in [0,1,15,16,31]:
    print(f"  r{X}={val(X)}  r{X+64}={val(X+64)}   {'DIFFER' if val(X)!=val(X+64) else 'ALIAS!'}")
# count distinct valid small indices in 0..95
valid=[N for N in range(96) if themap[N][0]=='OK' and themap[N][1] is not None and themap[N][1].isdigit() and int(themap[N][1])<K]
print(f"\n physical regs in r0..r95 returning a valid parked index (0..{K-1}): {len(valid)}")
print(" distinct index values seen:", sorted(set(int(themap[N][1]) for N in valid)))
print(" r96..r127 statuses:", sorted(set(themap[N][0] for N in range(96,128))))
