#!/bin/sh
# EXP-0017 driver — runs on the A18 device under ~/cleanroom_work/exp0017.
# Builds the read-only iotrace interposer + the tiling probe harness, captures the
# registered GPU BOs for a matrix of texture writes (known (x,y) pattern), and runs
# the twiddle analyzer on each. Pulls back text only (hexdumps + analysis).
# Clean-room: HW-PROBE + OWN-SHADER + DATA-TRACE.
set -u
cd "$(dirname "$0")"

echo "=== build ==="
clang -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation || exit 1
clang -fobjc-arc -framework Metal -framework Foundation -o texprobe texprobe.m || exit 1
echo "built"

DYL=./iotrace.dylib
rm -rf caps analysis; mkdir -p caps analysis

cap() {  # cap LABEL FMT W H [extra texprobe args...]
  label="$1"; fmt="$2"; W="$3"; H="$4"; shift 4
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./texprobe --fmt "$fmt" --w "$W" --h "$H" "$@" --dump \
    > "caps/$label.stdout" 2>&1 || true
  st=$(grep -E 'status=4' "caps/$label.stdout" | wc -l | tr -d ' ')
  echo "  cap $label fmt=$fmt ${W}x${H} $* : status4=$st"
  grep -E '^(CB_ERROR|.*_FAIL|COMPILE_FAIL)' "caps/$label.stdout" || true
  # analyze
  python3 twiddle.py "$d" --fmt "$fmt" --w "$W" --h "$H" --grid 32 \
    > "analysis/$label.txt" 2>&1 || echo "    (analyze failed)"
}

echo "=== A: twiddle order (r32uint, various sizes) ==="
cap A_r32_16   r32uint 16 16
cap A_r32_32   r32uint 32 32
cap A_r32_64   r32uint 64 64
cap A_r32_128  r32uint 128 128
cap A_r32_48   r32uint 48 48
cap A_r32_17x9 r32uint 17 9
cap A_r32_256x8 r32uint 256 8

echo "=== B: bytes-per-pixel scaling (32x32) ==="
cap B_r8    r8uint     32 32
cap B_r16   r16uint    32 32
cap B_r32   r32uint    32 32
cap B_rgba8 rgba8uint  32 32
cap B_rg32  rg32uint   32 32
cap B_rgba16 rgba16uint 32 32
cap B_rgba32 rgba32uint 32 32

echo "=== C: linear reference ==="
cap C_lin_r32 r32uint 64 64 --linear

echo "=== D: mipmaps ==="
cap D_mip_r32 r32uint 128 128 --mips 4
cap D_mip_r8  r8uint  128 128 --mips 4

echo "=== E: compression probe (render target, size sweep) ==="
for S in 16 32 64 128 256 512 1024; do
  cap E_rt_$S rgba8unorm $S $S --render --usage rt
done
# also a large plain sampled texture (no RT) to see if compression needs RT
cap E_read_256 rgba8unorm 256 256 --usage read --nowrite
cap E_read_512 rgba8unorm 512 512 --usage read --nowrite

echo "=== BO lists for compression cases ==="
for S in 128 256 512 1024; do
  echo "--- E_rt_$S BOs ---" >> analysis/E_bolists.txt
  python3 dumpscan.py caps/E_rt_$S --list >> analysis/E_bolists.txt 2>&1 || true
done

echo "=== done ==="
ls analysis/
