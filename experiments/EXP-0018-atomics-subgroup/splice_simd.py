#!/usr/bin/env python3
# EXP-0018 splice validation of the SIMD-reduce op-select field. Runs on device.
# s_sum op bytes = bf 01 56 00 02 00 14 03. We splice the op-select fields and
# check the operation actually changes on hardware. CLEAN-ROOM: OWN-SHADER.
import sys, os
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
from hwval import H, find

hs=H("kernels/simd.metal")
N=32; IN=[i+1 for i in range(N)]
fails=0
def show(n,g,e):
    global fails; ok=g==e; print(f"[{'PASS' if ok else 'FAIL'}] {n}"+("" if ok else f"\n   got={g}\n   exp={e}"))
    fails+= not ok

# locate the SIMD reduce op (bf..) inside s_sum
mh,off,length=hs.main_hex("s_sum")
i=find(mh,"bf01560002001403")
print(f"s_sum SIMD-reduce op at main-offset {i}: {mh[i*2:i*2+16]}")
#  bf 01 56 00 02 00 14 03   (byte0=bf,b1=01,b6=14,b7=03)
# --- splice op-select to MAX (b1 01->02, b7 03->07) : expect max ---
r=hs.run("s_sum",N,N,{1:('i',IN)},{2:('i',N)},splices={i+1:0x02, i+7:0x07})
show("s_sum spliced (b1->02,b7->07) == simd_max",r[2],[max(IN)]*N)
# --- splice byte0 bf->3f on s_or to get AND (or->and) ---
mh2,off2,_=hs.main_hex("s_or")
j=find(mh2,"bf00560002001403")
print(f"s_or SIMD-reduce op at main-offset {j}: {mh2[j*2:j*2+16]}")
AND=IN[0]
for v in IN: AND&=v
r=hs.run("s_or",N,N,{1:('i',IN)},{2:('i',N)},splices={j:0x3f})
show("s_or spliced byte0 bf->3f == simd_and",r[2],[AND]*N)
# --- splice s_prefix_exc (bf..140b) b7 0b->03 : exclusive-scan -> full reduce(sum) ---
mh3,off3,_=hs.main_hex("s_prefix_exc")
k=find(mh3,"bf0156000200140b")
print(f"s_prefix_exc op: {mh3[k*2:k*2+16]}")
r=hs.run("s_prefix_exc",N,N,{1:('i',IN)},{2:('i',N)},splices={k+7:0x03})
show("s_prefix_exc spliced b7 0b->03 == full sum (broadcast)",r[2],[sum(IN)]*N)

print(f"\n==== {'ALL PASS' if fails==0 else str(fails)+' FAIL' } ====")
sys.exit(1 if fails else 0)
