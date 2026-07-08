#!/bin/sh
# caprt.sh — DESC-1: capture the RT attachment LOAD(seg0)/RENDER(seg1)/STORE(seg2)
# format words for EVERY renderable format. Emits parseable lines with the 32-bit
# words at seg0+0x20, seg1+0x20 (=+0x320), seg2+0x20 (=+0x620). Clean-room: DATA-TRACE.
set -u
DYL=./iotrace.dylib
OUT=${1:-../raw/rt_format_capture.txt}
: > "$OUT"
FMTS="r8unorm rg8unorm rgba8unorm bgra8unorm rgba8unorm_srgb bgra8unorm_srgb \
r8snorm rg8snorm rgba8snorm r16unorm rg16unorm rgba16unorm r16snorm rg16snorm rgba16snorm \
r16float rg16float rgba16float r32float rg32float rgba32float \
rgb10a2unorm bgr10a2unorm rg11b10float rgb9e5float bgr10_xr bgra10_xr \
r8uint rg8uint rgba8uint r16uint rg16uint rgba16uint r32uint rg32uint rgba32uint rgb10a2uint \
r8sint rg8sint rgba8sint r16sint rg16sint rgba16sint r32sint rg32sint rgba32sint"

for f in $FMTS; do
  d=/tmp/rt_$f; rm -rf "$d"; mkdir -p "$d"
  st=$(IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" DYLD_INSERT_LIBRARIES=$DYL \
    ./rtfmt --fmt "$f" --w 64 --h 64 --dump 2>/dev/null | grep -E "RT_UNSUPPORTED|SUBMIT|COMPILE_FAIL")
  if echo "$st" | grep -q "status=4"; then
    dec=$(python3 attloc.py "$d" --n 0x700 2>/dev/null)
    s0=$(echo "$dec" | grep '+0020 ' | awk '{print $4}')
    s1=$(echo "$dec" | grep '+0320 ' | awk '{print $4}')
    s2=$(echo "$dec" | grep '+0620 ' | awk '{print $4}')
    s2w1=$(echo "$dec" | grep '+0620 ' | awk '{print $5}')
    printf 'RT %-20s seg0=%s seg1=%s store=%s storew1=%s\n' "$f" "$s0" "$s1" "$s2" "$s2w1" >> "$OUT"
  else
    printf 'RT %-20s %s\n' "$f" "$(echo $st | head -c80)" >> "$OUT"
  fi
  rm -rf "$d"
done
echo "wrote $OUT"; wc -l "$OUT"
