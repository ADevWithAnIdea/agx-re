#!/bin/sh
# TIL-3: MSAA sample interleave + tile-edge(bpp*N) across bpp1/2/8/16 at 2x/4x,
# plus 2x/4x compression-aux size. 8x is Metal-rejected (supportsTextureSampleCount=0).
set -e
cd "$(dirname "$0")"
run(){ # fmt W H samples
  fmt=$1; W=$2; H=$3; N=$4; tag="${fmt}_${W}_${N}x"
  d="maps_ms_${tag}"; rm -rf "$d"
  out=$(IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" DYLD_INSERT_LIBRARIES=./iotrace.dylib \
    ./typrobe2 --type 2dms --fmt "$fmt" --w "$W" --h "$H" --samples "$N" --dump 2>&1)
  if echo "$out" | grep -qE "TEX_FAIL|RPIPE_FAIL|COMPILE_FAIL"; then
    echo "== $tag : $(echo "$out"|grep -oE '(TEX_FAIL|RPIPE_FAIL|COMPILE_FAIL).*'|head -1)"; return; fi
  echo "== $tag =="
  python3 solve3d.py "$d" --type 2dms --fmt "$fmt" --w "$W" --h "$H" --slices "$N" 2>&1 | grep -E "CONFIRMED|NO 0"
}
for N in 2 4; do
  run r8uint     192 192 $N
  run r16uint    192 192 $N
  run r32uint    192 192 $N
  run rg32uint   160 160 $N
  run rgba32uint  96  96 $N
done
echo DONE_MSAA
