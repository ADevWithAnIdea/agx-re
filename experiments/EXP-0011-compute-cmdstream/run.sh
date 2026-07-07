#!/bin/sh
# EXP-0011 driver — runs on the A18 device under ~/cleanroom_work/exp0011.
# Builds the parametric compute harness + iotrace, captures the registered GPU
# BOs for a matrix of one-parameter-changed compute dispatches, and runs the
# on-device pointer-graph / diff analysis. Pulls back text only.
set -e
cd "$(dirname "$0")"

echo "=== build ==="
clang -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -fobjc-arc -framework Metal -framework Foundation -o cvar cvar.m
echo "built"

DYL=./iotrace.dylib
run() {  # run LABEL -- <cvar args...>
  label="$1"; shift; [ "$1" = "--" ] && shift
  d="caps/$label"
  rm -rf "$d"; mkdir -p "$d"
  echo "--- capture $label : $* ---"
  IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./cvar "$@" --dump > "caps/$label.stdout" 2>&1 || true
  grep -E '^(CONFIG|VA |PSO|TEX|SMP)' "caps/$label.stdout" || true
}

rm -rf caps; mkdir -p caps

# ---- Task 1: launch/dispatch descriptor (vary one dim at a time) -----------
run base    -- --kernel add3 --gx 64  --gy 1 --gz 1 --tgx 32 --tgy 1 --tgz 1
run gx128   -- --kernel add3 --gx 128 --gy 1 --gz 1 --tgx 32 --tgy 1 --tgz 1
run gx256   -- --kernel add3 --gx 256 --gy 1 --gz 1 --tgx 32 --tgy 1 --tgz 1
run gy2     -- --kernel add3 --gx 64  --gy 2 --gz 1 --tgx 32 --tgy 1 --tgz 1
run gz2     -- --kernel add3 --gx 64  --gy 1 --gz 2 --tgx 32 --tgy 1 --tgz 1
run tgx64   -- --kernel add3 --gx 64  --gy 1 --gz 1 --tgx 64 --tgy 1 --tgz 1
run tg8x4   -- --kernel add3 --gx 64  --gy 4 --gz 1 --tgx 8  --tgy 4 --tgz 1
run groups2 -- --kernel add3 --groups --gx 2 --gy 1 --gz 1 --tgx 32 --tgy 1 --tgz 1
run heavy   -- --kernel heavy --gx 64 --gy 1 --gz 1 --tgx 32 --tgy 1 --tgz 1

# ---- Task 2: argument buffer (vary buffer count / texture / sampler) --------
run buf1    -- --kernel mul1  --gx 64 --tgx 32
run buf2    -- --kernel add2  --gx 64 --tgx 32
run buf4    -- --kernel add4  --gx 64 --tgx 32
run buf8    -- --kernel add8  --gx 64 --tgx 32
run tex     -- --kernel tex   --gx 64 --tgx 32
run tgmem   -- --kernel tgmem --gx 64 --tgx 32 --tgmem 256

# ---- Task 1a: shader-pointer confirmation — two pipelines in one submit -----
echo "--- capture two : add3 + heavy in one command buffer ---"
rm -rf caps/two; mkdir -p caps/two
IOTRACE_LOG=caps/two.trace IOTRACE_DUMP_DIR=caps/two \
  DYLD_INSERT_LIBRARIES=$DYL ./cvar --kernel add3 --gx 64 --tgx 32 --k2 heavy --dump \
  > caps/two.stdout 2>&1 || true

# ---- Task 3: shader BO byte-validation vs shdump ---------------------------
echo "--- shader byte-validation (shdump add3) ---"
cp ../exp0009/shdump ../exp0009/agxparse.py . 2>/dev/null || true
cat > add3.metal <<'EOF'
#include <metal_stdlib>
using namespace metal;
kernel void k(device const float* a [[buffer(0)]],
              device const float* b [[buffer(1)]],
              device float* o       [[buffer(2)]],
              uint i [[thread_position_in_grid]]) { o[i]=a[i]+b[i]; }
EOF
./shdump -o add3.bin add3.metal 2>/dev/null || true

# ---- Task 4: ring / doorbell (per-submit snapshots + Mach map hunt) --------
echo "--- capture ring : 4 submits, per-submit snapshots, vmmap wrap ---"
rm -rf caps/ring; mkdir -p caps/ring
IOTRACE_LOG=caps/ring.trace IOTRACE_DUMP_DIR=caps/ring IOTRACE_DUMP_PERSIG=1 IOTRACE_WRAP_VMMAP=1 \
  DYLD_INSERT_LIBRARIES=$DYL ./cvar --kernel add3 --gx 64 --tgx 32 --iters 4 --dumpall \
  > caps/ring.stdout 2>&1 || true
echo "map/mementry/vmmap lines in ring trace (expect ~0 into GPU space):"
grep -cE '^(MAP |MAP32|MEMENTRY|VMMAP)' caps/ring.trace || true
grep -E '^(MAP |MAP32|MEMENTRY|VMMAP)' caps/ring.trace | head -40 || true
echo "ring producer index across submits (heap-alias +0x1ff04, expect +0x58/submit):"
for i in 00 01 02 03; do echo -n "dump$i: "; sed -n '/^0001ff00:/p' caps/ring/dump$i/*va10000030100_* 2>/dev/null; done

echo "=== on-device analysis ==="
mkdir -p analysis
# manifests
for l in base gx128 gx256 gy2 gz2 tgx64 tg8x4 groups2 heavy buf1 buf2 buf4 buf8 tex tgmem; do
  python3 dumpscan.py caps/$l --list > analysis/list_$l.txt 2>&1 || true
done
# pointer graph for baseline + a couple variants
for l in base buf4 tex heavy; do
  python3 bograph.py caps/$l > analysis/graph_$l.txt 2>&1 || true
done
# launch-descriptor diffs vs baseline (restrict to the launch BO 0x100000b0000)
for l in gx128 gx256 gy2 gz2 tgx64 tg8x4 groups2 heavy tgmem; do
  python3 bodiff.py caps/base caps/$l --va 0x100000b0000 --maxlen 0x40 > analysis/diff_launch_$l.txt 2>&1 || true
done
# arg-buffer diffs vs baseline (restrict to the arg BO 0x100000e0000)
for l in buf1 buf2 buf4 buf8 tex tgmem; do
  python3 bodiff.py caps/base caps/$l --va 0x100000e0000 --maxlen 0x2000 > analysis/diff_arg_$l.txt 2>&1 || true
done
# ring per-submit diffs
python3 bodiff.py caps/ring/dump00 caps/ring/dump01 > analysis/ring_d0_d1.txt 2>&1 || true
python3 bodiff.py caps/ring/dump01 caps/ring/dump02 > analysis/ring_d1_d2.txt 2>&1 || true
echo "=== done ==="
