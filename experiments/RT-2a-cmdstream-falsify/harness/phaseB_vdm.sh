#!/bin/sh
# RT-2a Phase B — falsify VDM draw record (tiler stream 0x18000).
# Claims: primitive @+0x65, vertexCount @+0x68, instanceCount @+0x6c,
#         indexed opcode 0x61c4->0x61f2 + index-buf VA @+0x70.
# Adversarial: all prims, instanced, indexed u16/u32, 0-vertex, huge counts,
#              base-vertex/base-instance/vertexStart (fields NOT in the doc).
set -e
cd "$(dirname "$0")"
DYL=./iotrace.dylib; CAP=0x400
rm -rf capsB analysisB hexB; mkdir -p capsB analysisB hexB
# dvar-based (prim/verts/inst/indexed)
rd(){ label="$1"; shift; d="capsB/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$CAP IOTRACE_LOG="capsB/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./dvar "$@" --dump > "capsB/$label.out" 2>&1 || true
  echo "  [$label] $(grep -E '^CONFIG' capsB/$label.out|head -1|cut -c1-90)"; }
# dvar2-based (base-vertex/instance/start)
rd2(){ label="$1"; shift; d="capsB/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$CAP IOTRACE_LOG="capsB/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./dvar2 "$@" --dump > "capsB/$label.out" 2>&1 || true
  echo "  [$label] $(grep -E '^CONFIG' capsB/$label.out|head -1|cut -c1-90)"; }

rd base   --prim tri --verts 3 --inst 1
rd base2  --prim tri --verts 3 --inst 1
# primitive types
rd p_point --prim point --verts 3
rd p_line  --prim line  --verts 4
rd p_lstrip --prim linestrip --verts 4
rd p_strip --prim strip --verts 4
rd p_tri   --prim tri   --verts 3
# vertexCount
rd v6      --prim tri --verts 6
rd v99     --prim tri --verts 99
rd vhuge   --prim tri --verts 0x123456
rd v0      --prim tri --verts 0
# instanceCount
rd i7      --prim tri --verts 3 --inst 7
rd i256    --prim tri --verts 3 --inst 0x100
rd ihuge   --prim tri --verts 3 --inst 0x123456
# indexed (opcode + index buf)
rd idx     --prim tri --verts 3 --indexed
rd idx6    --prim tri --verts 6 --indexed
# dvar2: indexed u16/u32, base-vertex, base-instance, vertexStart
rd2 d2base  --prim tri --verts 3 --inst 1
rd2 d2start --prim tri --verts 3 --start 5
rd2 d2inst  --prim tri --verts 3 --inst 7 --baseinst 0
rd2 d2binst --prim tri --verts 3 --inst 7 --baseinst 4
rd2 d2ix16  --prim tri --verts 3 --indexed --itype u16
rd2 d2ix32  --prim tri --verts 3 --indexed --itype u32
rd2 d2bvert --prim tri --verts 3 --indexed --itype u16 --basevert 9
rd2 d2ixbi  --prim tri --verts 3 --indexed --itype u16 --baseinst 4
rd2 d2ixoff --prim tri --verts 3 --indexed --itype u16 --idxoff 4

echo "=== diffs (VDM stream 0x18000) ==="
D(){ python3 bodiff.py "capsB/$1" "capsB/$2" --va 0x18000 --maxlen 0x120 > "analysisB/$3.txt" 2>&1 || true; }
D base base2 det
D p_tri p_point prim_point
D p_tri p_line  prim_line
D p_tri p_lstrip prim_lstrip
D p_tri p_strip prim_strip
D base v6   vc6
D base v99  vc99
D base vhuge vchuge
D base v0   vc0
D base i7   inst7
D base i256 inst256
D base ihuge insthuge
D base idx  indexed
D idx idx6  indexed_vc
D d2base d2start  start
D d2base d2binst  baseinst
D d2ix16 d2ix32   itype
D d2ix16 d2bvert  basevert
D d2ix16 d2ixbi   idx_baseinst
D d2ix16 d2ixoff  idx_offset
D d2base d2ix16   d2_indexed

echo "=== curated hex of VDM record region (+0x40..+0x100) ==="
kb(){ f=$(ls capsB/$1/*va18000_*.hex 2>/dev/null|head -1); [ -n "$f" ] && sed -n '1p;/^00000040:/,/^00000100:/p' "$f" > "hexB/$2.hex" || echo "no $1"; }
kb base base
kb p_point point
kb p_line line
kb p_strip strip
kb idx indexed
kb d2ix32 idx32
kb d2bvert basevert
kb d2binst baseinst
kb vhuge vhuge
kb ihuge ihuge
echo "=== VA lines (idx buffers) ==="
grep -h 'idxBuf\|vtxBuf' capsB/idx.out capsB/d2ix16.out capsB/d2ix32.out capsB/d2ixoff.out 2>/dev/null
echo DONE_PHASE_B