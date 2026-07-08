#!/bin/sh
# EXP-M4-06 bpp1 (r8, T=64, granule G=4) and bpp2 (r16, T=64, granule G=2)
# tile-column-padding granule confirmation sweep on the A18 Pro.
# Each config -> its own maps dir; run texprobe under iotrace, --dump snapshots BOs.
set -e
cd ~/cleanroom_work/exp_bpp12
run() { # fmt W H tag
  fmt=$1; W=$2; H=$3; tag=$4
  d="maps_${tag}"
  rm -rf "$d"
  echo "=== RUN $tag : $fmt ${W}x${H} ==="
  IOTRACE_LOG="io_${tag}.log" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=./iotrace.dylib ./texprobe --fmt "$fmt" --w "$W" --h "$H" --dump \
    2>&1 | grep -vE "^CALL|^MAP"
}

# --- bpp1 (r8uint, T=64): granule G = 0x4000/(64*64*1) = 4  -> cols mult of 4 ---
run r8uint   64  64 b1_64        # W<=T single-tile exception (no granule rounding)
run r8uint  128 128 b1_128       # ceil 2; granule 4; nextpow2 2   <- KEY (granule vs nextpow2/ceil)
run r8uint  192 192 b1_192       # ceil 3; granule 4; nextpow2 4
run r8uint  256 256 b1_256       # ceil 4; granule 4 (control, no rounding)
run r8uint  320 320 b1_320       # ceil 5; granule 8; nextpow2 8
run r8uint  192 320 b1_192x320   # padH test: W->cols4/padW256 ; H ceil5 (NOT granule-rounded)

# --- bpp2 (r16uint, T=64): granule G = 0x4000/(64*64*2) = 2  -> cols even ---
run r16uint 192 192 b2_192       # ceil 3; granule 4; nextpow2 4
run r16uint 256 256 b2_256       # ceil 4; granule 4 (control, no rounding)
run r16uint 320 320 b2_320       # ceil 5; granule 6; nextpow2 8   <- KEY (granule vs nextpow2 AND ceil)
run r16uint 448 448 b2_448       # ceil 7; granule 8; nextpow2 8
run r16uint 320 192 b2_320x192   # padH test: W->cols6/padW384 ; H ceil3 (NOT granule-rounded)

echo "ALL_RUNS_DONE"
