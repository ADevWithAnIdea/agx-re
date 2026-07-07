#!/bin/sh
# EXP-O2H driver — runs on the A18 device under ~/cleanroom_work/exp_o2h.
# Determines how Metal implements TESSELLATION on Apple9 (G17P): does drawPatches
# produce a compute pre-pass (a CDM launch descriptor + a VDM draw), reuse the mesh
# path (0x70000600), or a dedicated HW/tiler tessellation record? Plus decodes the
# tessellation-factor buffer format and the patch-type/count encoding.
# CLEAN-ROOM: DATA-TRACE (iotrace) + OWN-SHADER (our own tessellation MSL).
set -e
cd "$(dirname "$0")"
SRC=kernels/tess.metal
[ -f "$SRC" ] || SRC=tess.metal   # allow flat layout on device

echo "=== build ==="
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o tess tess.m
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o shdump_tess shdump_tess.m
clang -fobjc-arc -framework Metal -framework Foundation -o iohello_draw iohello_draw.m
clang -fobjc-arc -framework Metal -framework Foundation -o iohello_compute iohello_compute.m
echo "built"

DYL=./iotrace.dylib
CAP=0x10000
rm -rf caps analysis hex code; mkdir -p caps analysis hex code

# run LABEL -- <argv...>   (captures BO snapshots of one submit + the trace)
run(){ label="$1"; shift; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_MAX_MAP="$CAP" IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL "$@" --dump > "caps/$label.stdout" 2>&1 || true
  calls=$(grep -cE '^CALL' "caps/$label.trace" 2>/dev/null || echo 0)
  sub=$(grep -cE 'done status=(4|0)' "caps/$label.stdout" 2>/dev/null || echo 0)
  cov=$(grep -oE 'COVERED [0-9]+' "caps/$label.stdout" | head -1 || true)
  st=$(grep -E '^(ERROR|CB_ERROR|COMPILE|PIPELINE|CPIPE|FUNC|STATUS OK)' "caps/$label.stdout" | head -2 | tr '\n' ';' || true)
  echo "  [$label] iokit_calls=$calls submits=$sub $cov  {$st}"
}

echo "=== captures ==="
# --- baselines for IOKit call-count / BO-set comparison ---
run draw    -- ./iohello_draw --w 64 --h 64
run compute -- ./iohello_compute

# --- TESSELLATION: crux capture. --cpu-factors => NO user compute encoder. ---
run tess_cpu   -- ./tess --source $SRC --patch tri  --level 8 --cpu-factors --w 64 --h 64
run tess_comp  -- ./tess --source $SRC --patch tri  --level 8               --w 64 --h 64
run tess_q_cpu -- ./tess --source $SRC --patch quad --level 8 --cpu-factors --w 64 --h 64

# --- factor-format decode: vary level (cpu-factors, isolate the factor buffer) ---
run tess_l1    -- ./tess --source $SRC --patch tri --level 1  --cpu-factors --w 64 --h 64
run tess_l4    -- ./tess --source $SRC --patch tri --level 4  --cpu-factors --w 64 --h 64
run tess_l16   -- ./tess --source $SRC --patch tri --level 16 --cpu-factors --w 64 --h 64

# --- partition-mode encoding (state pool / pipeline) ---
run tess_int   -- ./tess --source $SRC --patch tri --level 8 --cpu-factors --partition int  --w 64 --h 64
run tess_pow2  -- ./tess --source $SRC --patch tri --level 8 --cpu-factors --partition pow2 --w 64 --h 64
run tess_fo    -- ./tess --source $SRC --patch tri --level 8 --cpu-factors --partition fo   --w 64 --h 64
run tess_fe    -- ./tess --source $SRC --patch tri --level 8 --cpu-factors --partition fe   --w 64 --h 64

# --- HW validation of SUBDIVISION: bulge makes silhouette level-dependent ---
echo "=== HW-validate subdivision (bulge, coverage must grow with level) ==="
for LV in 1 2 4 8 16; do
  ./tess --source $SRC --patch tri --level $LV --bulge 0.25 --w 96 --h 96 \
    > "caps/bulge_l$LV.stdout" 2>&1 || true
  echo "  bulge level=$LV $(grep -oE 'COVERED [0-9]+ of [0-9]+' caps/bulge_l$LV.stdout | head -1)"
done
./tess --source $SRC --patch quad --level 8 --bulge 0.25 --w 96 --h 96 > caps/bulge_quad.stdout 2>&1 || true

echo "=== BO inventory per capture (which records/BOs appear) ==="
for L in draw compute tess_cpu tess_comp tess_q_cpu; do
  echo "== $L =="; python3 dumpscan.py "caps/$L" --list 2>/dev/null | sort || true
done > analysis/bo_inventory.txt 2>&1
# extract just the gpu_va set for a compact compare
for L in draw compute tess_cpu tess_comp tess_q_cpu; do
  echo "== $L gpu_vas =="; python3 dumpscan.py "caps/$L" --list 2>/dev/null | grep -oE 'gpu_va=0x[0-9a-f]+' | sort -u
done > analysis/bo_vaset.txt 2>&1

echo "=== IOKit call-count summary ==="
{ for L in draw compute tess_cpu tess_comp tess_q_cpu; do
    printf "%-12s calls=%s sel9=%s\n" "$L" \
      "$(grep -cE '^CALL' caps/$L.trace 2>/dev/null||echo 0)" \
      "$(grep -cE 'selector=9|sel=9|gpu_va=' caps/$L.trace 2>/dev/null||echo 0)"
  done; } > analysis/callcounts.txt 2>&1

echo "=== VDM/tiler record diff (0x18000): patch draw record vs 0x61c4 / 0x70000600 ==="
dv(){ python3 bodiff.py "caps/$1" "caps/$2" --va "$3" --maxlen "$4" > "analysis/$5.txt" 2>&1 || true; }
df(){ python3 bodiff.py "caps/$1" "caps/$2" --maxlen 0x400 > "analysis/$3.txt" 2>&1 || true; }
dv draw    tess_cpu   0x18000 0x120 vdm_draw_v_tess
dv tess_cpu tess_comp 0x18000 0x120 vdm_tess_cpu_v_comp
dv tess_cpu tess_q_cpu 0x18000 0x120 vdm_tri_v_quad
# full-dir discovery: any BO present in tess but not draw
df draw tess_cpu full_draw_v_tesscpu
df tess_cpu tess_comp full_tesscpu_v_comp

echo "=== factor-buffer format decode (vary level) ==="
# the factor buffer is OUR buffer; grab its raw BO snapshot (found by the VA ./tess printed).
dumpbo(){ # dumpbo CAP VA_no0x  -> prints first bytes of that BO's hex snapshot
  ls caps/$1/bo_sigusr1_*_va$2_*.hex 2>/dev/null | head -1 | while read f; do head -6 "$f"; done; }
for L in tess_l1 tess_l4 tess_l16 tess_cpu tess_q_cpu; do
  fva=$(grep -oE 'VA tessfactors +.*0x[0-9a-f]+' caps/$L.stdout | grep -oE '0x[0-9a-f]{6,}' | head -1 | sed 's/^0x//')
  echo "== $L tessfactors=0x$fva =="
  [ -n "$fva" ] && dumpbo "$L" "$fva" || echo "  (factor VA not found)"
done > analysis/factorbuf.txt 2>&1
# byte-diff the factor buffer between levels (bodiff pairs BOs by gpu_va)
for pair in "tess_l1 tess_l4" "tess_l4 tess_l16"; do set -- $pair
  fva=$(grep -oE 'VA tessfactors +.*0x[0-9a-f]+' caps/$1.stdout | grep -oE '0x[0-9a-f]{6,}' | head -1)
  [ -n "$fva" ] && python3 bodiff.py "caps/$1" "caps/$2" --va "$fva" --maxlen 0x20 > "analysis/factordiff_${1}_${2}.txt" 2>&1 || true
done

echo "=== partition-mode diffs (state pool 0x58000 + full) ==="
for P in tess_pow2 tess_fo tess_fe; do
  dv tess_int $P 0x58000 0x200 part_58k_$P
  df tess_int $P part_full_$P
done

echo "=== post-tessellation vertex shader bytes (OWN-SHADER opcode census) ==="
./shdump_tess -o tess_tri.bin  --patch tri  $SRC 2>code/shdump_tri.log  || true
./shdump_tess -o tess_quad.bin --patch quad $SRC 2>code/shdump_quad.log || true
for B in tess_tri tess_quad; do
  python3 agxparse.py $B.bin > code/${B}_report.txt 2>&1 || true
  python3 agxparse.py $B.bin --stage vertex   --extract-hex > code/${B}_vertex.hex   2>/dev/null || true
  python3 agxparse.py $B.bin --stage fragment --extract-hex > code/${B}_fragment.hex 2>/dev/null || true
done
# compare against a PLAIN (non-tess) vertex+fragment archive: is the post-tess VS special?
cat > plain.metal <<'EOF'
#include <metal_stdlib>
using namespace metal;
struct VO{float4 pos [[position]]; float4 col;};
vertex VO v_main(uint vid [[vertex_id]]){ float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};
  VO o; o.pos=float4(p[vid],0,1); o.col=float4(0.25,0.5,0.75,1); return o; }
fragment float4 tess_frag(VO in [[stage_in]]){ return in.col; }
EOF
# reuse the shared shdump --render if present; else skip (informational)
[ -x ./shdump ] && ./shdump -o plain.bin --render --vertex v_main --fragment tess_frag plain.metal 2>code/shdump_plain.log && \
  python3 agxparse.py plain.bin --stage vertex --extract-hex > code/plain_vertex.hex 2>/dev/null || echo "(no shared shdump; plain VS compare skipped)" >code/plain_note.txt

echo "=== curated hexdumps ==="
keep(){ f=$(ls caps/$1/bo_sigusr1_*_va$2_*.hex 2>/dev/null | head -1)
  [ -n "$f" ] && head -${4:-160} "$f" > "hex/$3.hex" 2>/dev/null || echo "  (no $2 in $1)"; }
for L in draw tess_cpu tess_comp tess_q_cpu; do keep $L 18000 ${L}_18000 140; done
for L in tess_cpu tess_comp; do keep $L 58000 ${L}_58000 120; keep $L 68000 ${L}_68000 80; done
# the mesh-style dispatch descriptor, if any (mesh used 0x100000f8000)
for L in tess_cpu tess_comp; do keep $L 100000f8000 ${L}_f8000 60; keep $L 100000b0000 ${L}_b0000 40; done

echo "=== done. caps=$(ls -d caps/*/ 2>/dev/null|wc -l) analysis=$(ls analysis|wc -l) hex=$(ls hex|wc -l) code=$(ls code|wc -l) ==="
