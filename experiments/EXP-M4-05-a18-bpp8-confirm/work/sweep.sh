#!/bin/sh
# bpp8 even-column / 16-KiB-row-stride confirmation sweep on the A18 Pro.
# Each config -> its own maps dir; run texprobe under iotrace, --dump snapshots BOs.
set -e
cd ~/cleanroom_work/exp_bpp8
run() { # fmt W H tag
  fmt=$1; W=$2; H=$3; tag=$4
  d="maps_${tag}"
  rm -rf "$d"
  echo "=== RUN $tag : $fmt ${W}x${H} ==="
  IOTRACE_LOG="io_${tag}.log" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=./iotrace.dylib ./texprobe --fmt "$fmt" --w "$W" --h "$H" --dump \
    2>&1 | grep -vE "^CALL|^MAP"
}

# --- bpp8 (rg32uint, T=32): the even-column probes ---
run rg32uint  96  96 b8_96
run rg32uint 160 160 b8_160
run rg32uint 288 288 b8_288
run rg32uint 320 320 b8_320
run rg32uint 448 448 b8_448
run rg32uint 160 256 b8_160x256

# --- controls: bpp4 (r32uint, T=64) should keep ODD cols ---
run r32uint  160 160 b4_160

# --- controls: bpp16 (rgba32uint, T=32) should keep ODD cols ---
run rgba32uint  96  96 b16_96
run rgba32uint 160 160 b16_160

echo "ALL_RUNS_DONE"
