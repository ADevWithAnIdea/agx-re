#!/bin/sh
# RT-2a Phase E — consolidation: true 0-vertex (dvar2), 16-viewport count word,
# clean baseInstance isolation, indexed+instanced+basevert combo.
set -e
cd "$(dirname "$0")"
DYL=./iotrace.dylib; S=0x800
rm -rf capsE; mkdir -p capsE
r2(){ label="$1"; shift; d="capsE/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$S IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./dvar2 "$@" --dump > "capsE/$label.out" 2>&1 || true; }
ro(){ label="$1"; shift; d="capsE/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$S IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./ovar "$@" --dump > "capsE/$label.out" 2>&1 || true; }
# true 0-vertex vs 3-vertex (dvar2, no guard)
r2 v3 --prim tri --verts 3
r2 v0 --prim tri --verts 0
# clean baseInstance isolation (non-indexed): only baseInstance changes
r2 bi0 --prim tri --verts 3 --inst 4 --baseinst 0
r2 bi9 --prim tri --verts 3 --inst 4 --baseinst 9
# indexed + instanced + basevert combo (stress record)
r2 combo --prim tri --verts 6 --indexed --itype u16 --inst 3 --basevert 4 --baseinst 2
# viewports
ro vp1  --prim tri
ro vp16 --prim tri --nvp 16 --vpidx 3

echo "=== true 0-vertex: v3 vs v0 @0x18000 +0x60 region ==="
for l in v3 v0; do echo "-- $l --"; f=$(ls capsE/$l/*va18000_*.hex|head -1); sed -n '/^00000060:/,/^00000070:/p' "$f"; done
python3 bodiff.py capsE/v3 capsE/v0 --va 0x18000 --maxlen 0x90 2>&1 | grep -E '\+0x|differing'
echo "=== baseInstance clean (bi0 vs bi9), ALL BOs (find where 9 lands) ==="
python3 bodiff.py capsE/bi0 capsE/bi9 --maxlen 0x400 2>&1 | grep -E 'gpu_va|\+0x' | grep -v 'va=0x0 ' | grep -A3 '10000100000\|10000018\|differing' | head -20
python3 bodiff.py capsE/bi0 capsE/bi9 --va 0x10000100000 --maxlen 0x100 2>&1 | grep -E '\+0x|differing'
echo "=== combo record @0x18000 +0x60..+0x90 ==="
f=$(ls capsE/combo/*va18000_*.hex|head -1); sed -n '/^00000060:/,/^00000090:/p' "$f"
echo "=== 16-viewport count word 0x68000+0x900 (vp1 vs vp16) ==="
for l in vp1 vp16; do echo "-- $l --"; f=$(ls capsE/$l/*va68000_*.hex|head -1); sed -n '/^00000900:/,/^00000920:/p' "$f"; done
python3 bodiff.py capsE/vp1 capsE/vp16 --va 0x68000 --maxlen 0xa00 2>&1 | grep -E '\+0x0900|\+0x0904|\+0x0908|differing' | head
echo DONE_PHASE_E