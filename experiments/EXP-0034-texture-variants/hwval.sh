#!/bin/bash
# EXP-0034 HW-validation driver (runs on the A18 target under ~/cleanroom_work/exp0034).
# Reproduces every splice/observe + descriptor-linkage test and saves to raw/.
# CLEAN-ROOM: OWN-SHADER; our own compiled bytes only. No Apple binary disassembled.
set -u
cd "$(dirname "$0")"; mkdir -p raw out
CS=kernels/tv_comp.metal; AS=kernels/tv_atomic2.metal
{
echo "===== 1. SHADOW / sample_compare (depth[i]=i/16, const ref 0.5, nearest) ====="
for CMP in less lessequal greater greaterequal equal notequal always never; do
  printf "compare=%-13s : " "$CMP"
  ./tvcmp --archive out/comp_sc_lod.bin --source $CS --function sc_lod \
     --texfmt depth --compare $CMP --filter nearest --out float 2>&1 \
     | awk '/^OUT/{printf "%s",$3" "} /STATUS/{print $2}'
done

echo "===== 2. sample_compare DYNAMIC per-thread ref (ref[i]=i/16 == depth[i]) ====="
printf "compare=less (equal->fail) : "
./tvcmp --archive out/comp_sc_ref.bin --source $CS --function sc_ref --texfmt depth --compare less --filter nearest --out float 2>&1 | awk '/^OUT/{printf "%s",$3" "} /STATUS/{print $2}'
printf "compare=lessequal (equal->pass) : "
./tvcmp --archive out/comp_sc_ref.bin --source $CS --function sc_ref --texfmt depth --compare lessequal --filter nearest --out float 2>&1 | awk '/^OUT/{printf "%s",$3" "} /STATUS/{print $2}'

echo "===== 3. PCF: sample_compare LINEAR filter (fractional 2x2) ====="
printf "compare=lessequal filter=linear : "
./tvcmp --archive out/comp_sc_lod.bin --source $CS --function sc_lod --texfmt depth --compare lessequal --filter linear --out float 2>&1 | awk '/^OUT/{printf "%s",$3" "} /STATUS/{print $2}'

echo "===== 4. GATHER component (rgba grid; expect R/G/B/A of 2x2 footprint) ====="
for FN in b_gather g_y g_z g_w; do
  printf "%-9s : " "$FN"
  ./texcomp --archive out/comp_$FN.bin --source $CS --function $FN --mode read --sampler 2>&1 | awk '/^OUT [0-3] /{printf "%s ",$0}'; echo
done

echo "===== 5. GATHER offset op+5 (b_gather vs g_off10 int2(1,0)) ====="
printf "no-offset : "; ./texcomp --archive out/comp_b_gather.bin --source $CS --function b_gather --mode read --sampler 2>&1 | awk '/^OUT [0-3] /{printf "%s ",$3}'; echo
printf "off(1,0)  : "; ./texcomp --archive out/comp_g_off10.bin --source $CS --function g_off10 --mode read --sampler 2>&1 | awk '/^OUT [0-3] /{printf "%s ",$3}'; echo

echo "===== 6. LOD query (op+6=0x20; compute has no derivatives -> 0) ====="
printf "lod_c : "; ./tvcmp --archive out/comp_lod_c.bin --source $CS --function lod_c --texfmt rgba --mips --compare none --filter nearest --out float 2>&1 | awk '/^OUT/{printf "%s",$3" "} /STATUS/{print $2}'

echo "===== 7. TEXTURE ATOMICS (r32uint; lowers to 0x67 device atomic) ====="
printf "at_distinct(16) : "; ./atomtex --archive out/at_at_distinct.bin --source $AS --function at_distinct --threads 16 2>&1 | awk '/^TEXEL/{printf "%s",$3" "} /STATUS/{print $2}'
printf "at_contend(256) TEXEL0 : "; ./atomtex --archive out/at_at_contend.bin --source $AS --function at_contend --threads 256 2>&1 | awk '/^TEXEL 0 /{printf "%s ",$3} /STATUS/{print $2}'
printf "at_max(256) TEXEL0 : "; ./atomtex --archive out/at_at_max.bin --source $AS --function at_max --threads 256 2>&1 | awk '/^TEXEL 0 /{printf "%s ",$3} /STATUS/{print $2}'
} 2>&1 | tee raw/hw_validation.txt
echo "=== DONE ==="
