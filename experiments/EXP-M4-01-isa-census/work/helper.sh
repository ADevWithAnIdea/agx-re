#!/bin/bash
# helper.sh <metal_file> <kernel_name> — compile, extract, and walk one kernel.
# Prints the instruction walk. CLEAN-ROOM: our own shader only.
set -e
MF="$1"; KN="$2"
BASE=$(basename "$MF" .metal)
./shdump -f "$KN" -o "/tmp/${BASE}_${KN}.bin" "$MF" 2>/dev/null
python3 - "$MF" "$KN" "$BASE" <<'PY'
import sys, os
sys.path.insert(0, '/Users/user/cleanroom_gpu/experiments/EXP-M4-01-isa-census/census')
sys.path.insert(0, '/Users/user/cleanroom_gpu/tools/agx-isa')
import agxparse, isadb
mf, kn, base = sys.argv[1], sys.argv[2], sys.argv[3]
with open(f"/tmp/{base}_{kn}.bin","rb") as f: buf=f.read()
report, stages = agxparse.extract_all_stages(buf)
data = stages['compute']['_agc.main']
# trim padding
end=len(data)
while end>=2 and data[end-2:end]==b'\x06\x00': end-=2
b=data[:end]; n=len(b); off=0; idx=0
print(f"=== {kn}  ({n} bytes) ===")
def named_at(off):
    L=isadb.instr_length(b,off)
    if L is None or off+L>n: return None,None
    try:
        rec,_=isadb.decode_one(b,off); return L,rec['mnemonic']
    except ValueError: return L,None
while off<n:
    b0=b[off]; L=isadb.instr_length(b,off)
    if L is not None and off+L<=n:
        try: rec,_=isadb.decode_one(b,off); mn=rec['mnemonic']; st='named'
        except ValueError: mn='?'; st='lenonly'
        print(f"  [{idx:3d}] @{off:4d} L={L:2d} {st:8s} {mn:22s} {b[off:off+L].hex(' ')}")
        off+=L; idx+=1; continue
    start=off; off+=2
    while off<n:
        L2,mn2=named_at(off)
        if mn2 is not None: break
        off+=2
    print(f"  [{idx:3d}] @{start:4d} L={off-start:2d} UNDECODED byte0=0x{b0:02x}   {b[start:start+min(off-start,24)].hex(' ')}")
    idx+=1
PY
