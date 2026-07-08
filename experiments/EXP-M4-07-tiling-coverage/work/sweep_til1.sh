#!/bin/sh
# TIL-1: 3D / 2DArray / Cube / CubeArray twiddle across bpp1/2/4/8/16.
# Dims chosen so tile-multiple padW != nextpow2(W) (distinguishes plane padding)
# and the intra-plane cols rule is exercised (odd/even tile counts).
#   bpp1 T128: 320 -> cols3(flat) padW384 vs np2 512
#   bpp2 T64 G2: 320 -> cols6(even) padW384 vs ceil5=320 vs np2 512
#   bpp4 T64 G1: 192 -> cols3 padW192 vs np2 256
#   bpp8 T32 G2: 160 -> cols6(even) padW192 vs ceil5=160 vs np2 256
#   bpp16 T32 G1: 96 -> cols3 padW96 vs np2 128
set -e
cd "$(dirname "$0")"
run(){ # type fmt W H slices extra...
  typ=$1; fmt=$2; W=$3; H=$4; sl=$5; shift 5
  tag="${typ}_${fmt}_${W}"
  d="maps_t1_${tag}"; rm -rf "$d"
  echo "=== RUN $tag  ($typ $fmt ${W}x${H} slices=$sl $*) ==="
  IOTRACE_LOG="io_t1_${tag}.log" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=./iotrace.dylib ./typrobe2 --type "$typ" --fmt "$fmt" --w "$W" --h "$H" "$@" --upload --dump \
    2>&1 | grep -vE "^CALL|^MAP"
}
# --- 3D (depth 2) and 2DArray (arraylen 2) for all bpp ---
run 3d      r8uint     320 320 2 --d 2
run 2darray r8uint     320 320 2 --arraylen 2
run 3d      r16uint    320 320 2 --d 2
run 2darray r16uint    320 320 2 --arraylen 2
run 3d      r32uint    192 192 2 --d 2
run 2darray r32uint    192 192 2 --arraylen 2
run 3d      rg32uint   160 160 2 --d 2
run 2darray rg32uint   160 160 2 --arraylen 2
run 3d      rgba32uint  96  96 2 --d 2
run 2darray rgba32uint  96  96 2 --arraylen 2
# --- Cube (6 faces) + CubeArray (12 faces) at the T extremes bpp1 & bpp16 ---
run cube      r8uint     320 320 6  --arraylen 1
run cubearray r8uint     320 320 12 --arraylen 2
run cube      rgba32uint  96  96 6  --arraylen 1
run cubearray rgba32uint  96  96 12 --arraylen 2
echo "ALL_TIL1_RUNS_DONE"
