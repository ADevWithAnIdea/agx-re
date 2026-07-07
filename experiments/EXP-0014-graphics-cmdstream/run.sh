#!/bin/sh
# EXP-0014 driver — runs on the A18 device under ~/cleanroom_work/exp0014.
# Builds the parametric DRAW harness (dvar) + iotrace + compute harness, captures
# the registered GPU BOs for a matrix of one-parameter-changed draws, and runs the
# on-device pointer-graph / diff analysis. Pulls back text only.
set -e
cd "$(dirname "$0")"

echo "=== build ==="
clang -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -fobjc-arc -framework Metal -framework Foundation -o dvar dvar.m
clang -fobjc-arc -framework Metal -framework Foundation -o iohello_compute iohello_compute.m
echo "built"

DYL=./iotrace.dylib
# bound per-BO snapshot so heap dumps stay pull-back-able
export IOTRACE_MAX_MAP=0x20000

run() {  # run LABEL -- <dvar args...>
  label="$1"; shift; [ "$1" = "--" ] && shift
  d="caps/$label"
  rm -rf "$d"; mkdir -p "$d"
  echo "--- capture $label : $* ---"
  IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./dvar "$@" --dump > "caps/$label.stdout" 2>&1 || true
  grep -E '^(CONFIG|VA |PIXEL|PIPELINE_FAIL|RTBUF|PSO2)' "caps/$label.stdout" || true
}

rm -rf caps; mkdir -p caps

# ---- baseline + determinism check -----------------------------------------
run base   --
run base2  --

# ---- Task 2: draw parameters ----------------------------------------------
run verts6     -- --verts 6
run prim_line  -- --prim line
run prim_point -- --prim point
run prim_strip -- --prim strip
run inst4      -- --inst 4
run indexed    -- --indexed

# ---- Task 3: viewport / scissor / render-target ---------------------------
run vp32       -- --vpw 32 --vph 32
run rt128      -- --w 128 --h 128
run fmt_rgba8  -- --fmt rgba8
run fmt_16f    -- --fmt rgba16f
run clear      -- --cr 1 --cg 0 --cb 0

# ---- Task 4: fixed-function state -----------------------------------------
run blend      -- --blend
run depth      -- --depth

# ---- Task 1: shader references --------------------------------------------
run vbig       -- --vshader big
run fbig       -- --fshader big
run two        -- --two

# ---- compute comparison (BO-set delta draw-vs-compute) --------------------
echo "--- capture compute (for BO-set comparison) ---"
rm -rf caps/compute; mkdir -p caps/compute
IOTRACE_LOG=caps/compute.trace IOTRACE_DUMP_DIR=caps/compute \
  DYLD_INSERT_LIBRARIES=$DYL ./iohello_compute --dump > caps/compute.stdout 2>&1 || true

echo "=== on-device analysis ==="
mkdir -p analysis
LABELS="base base2 verts6 prim_line prim_point prim_strip inst4 indexed vp32 rt128 fmt_rgba8 fmt_16f clear blend depth vbig fbig two compute"
for l in $LABELS; do
  python3 dumpscan.py caps/$l --list > analysis/list_$l.txt 2>&1 || true
done
# pointer graph for structurally-interesting captures
for l in base vbig fbig two depth blend indexed rt128; do
  python3 bograph.py caps/$l > analysis/graph_$l.txt 2>&1 || true
done
# full BO diffs vs baseline (bounded), pairing by gpu_va
for l in base2 verts6 prim_line prim_point prim_strip inst4 indexed vp32 rt128 fmt_rgba8 fmt_16f clear blend depth vbig fbig two; do
  python3 bodiff.py caps/base caps/$l --maxlen 0x400 > analysis/diff_$l.txt 2>&1 || true
done
# trace call/selector histograms (draw vs compute BO count)
for l in base compute; do
  echo "== $l ==" >> analysis/selhist.txt
  grep -cE '^CALL' caps/$l.trace >> analysis/selhist.txt 2>&1 || true
  grep -oE 'sel=[0-9]+' caps/$l.trace | sort | uniq -c | sort -rn >> analysis/selhist.txt 2>&1 || true
done
echo "=== done ==="
ls -la analysis | head
