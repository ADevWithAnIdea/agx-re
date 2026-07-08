#!/bin/sh
# CMD-4 — primitive x index-type x instancing matrix. Actually RUNS the u32-index path.
# Captures the VDM draw record (0x18000) and diffs to map opcode + field positions.
# CLEAN-ROOM: DATA-TRACE + OWN-SHADER. Runs on LOCAL M4.
cd "$(dirname "$0")"
DYL=./iotrace.dylib; CAP=0x800
rm -rf d_caps d_an; mkdir -p d_caps d_an
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o dvar4 dvar4.m || { echo BUILD_FAIL; exit 1; }

cap(){ label="$1"; shift; d="d_caps/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$CAP IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./dvar4 "$@" --dump > "$d.out" 2>&1
  grep -qE 'status=4' "$d.out" && echo "  [$label] ok" || echo "  [$label] FAIL: $(grep -iE 'fail|exc|error|status' $d.out|head -1)"; }

echo "=== primitive x index-type (non-indexed / u16 / u32) ==="
for p in point line linestrip tri tristrip; do
  cap ni_$p   --prim $p
  cap u16_$p  --prim $p --itype u16
  cap u32_$p  --prim $p --itype u32
done
echo "=== instancing paths (tri) ==="
cap tri_inst4     --prim tri --inst 4
cap tri_basev5    --prim tri --itype u16 --basevertex 5
cap tri_basei3    --prim tri --baseinstance 3
cap tri_u32_inst4 --prim tri --itype u32 --inst 4
cap tri_u32_bv5   --prim tri --itype u32 --basevertex 5
cap tri_u32_bi3   --prim tri --itype u32 --baseinstance 3
cap u16_inst4     --prim tri --itype u16 --inst 4
cap u16_bv_bi     --prim tri --itype u16 --basevertex 5 --baseinstance 3 --inst 4

echo "=== raw VDM record 0x18000 +0x60..+0x88 for each key config ==="
vdm(){ f=$(ls d_caps/$1/*va18000_*.hex 2>/dev/null|head -1)
  [ -n "$f" ] && { printf "## %-14s " "$1"; sed -n '/^00000060:/p;/^00000070:/p;/^00000080:/p' "$f" | tr '\n' ' '; echo; }; }
{
for p in point line linestrip tri tristrip; do vdm ni_$p; vdm u16_$p; vdm u32_$p; done
echo "--- instancing ---"
for c in tri_inst4 tri_basev5 tri_basei3 tri_u32_inst4 tri_u32_bv5 tri_u32_bi3 u16_inst4 u16_bv_bi; do vdm $c; done
} > d_an/vdm_records.txt 2>&1

echo "=== diffs: prim/index/instancing field isolation ==="
D(){ python3 bodiff.py "d_caps/$1" "d_caps/$2" --va 0x18000 --maxlen 0x90 > "d_an/$3.txt" 2>&1; }
# non-indexed -> u16 -> u32 (record shift + opcode)
D ni_tri u16_tri  ni_to_u16
D u16_tri u32_tri u16_to_u32
# prim opcode differences (non-indexed)
D ni_tri ni_point   prim_tri_v_point
D ni_tri ni_line    prim_tri_v_line
D ni_tri ni_linestrip prim_tri_v_lstrip
D ni_tri ni_tristrip  prim_tri_v_tstrip
# instancing fields
D u16_tri tri_inst4    inst_count
D u16_tri tri_basev5   base_vertex
D ni_tri  tri_basei3   base_instance_ni
D u16_tri u16_bv_bi    all_instancing
# u32 instancing (confirm same field positions as u16 but u32 opcode)
D u32_tri tri_u32_inst4 u32_inst_count
D u32_tri tri_u32_bv5   u32_base_vertex
echo "=== DONE ==="
ls d_an/
