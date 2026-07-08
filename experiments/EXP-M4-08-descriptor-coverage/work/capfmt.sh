#!/bin/sh
# capfmt.sh — DESC-5/DESC-6: capture the sampled texture descriptor word0/word1 for
# EVERY format in tvar's FMTS list, via iotrace + descauto. Emits one parseable line
# per format: "FMT <name> word0=<hex> word1=<hex>" plus the tvar CONFIG/TEX line.
# Clean-room: DATA-TRACE of our own process only.
set -u
DYL=./iotrace.dylib
OUT=${1:-../raw/format_capture.txt}
: > "$OUT"
# All format names from tvar.m FMTS. Compressed use 32x32; rest use 8x8 (asymmetric
# would move swizzle; 8x8 keeps width-1=height-1=7 so any dims bleed is visible).
FMTS_SMALL="r8unorm r8snorm a8unorm rg8unorm rg8snorm rgba8unorm rgba8snorm bgra8unorm \
rgba8unorm_srgb bgra8unorm_srgb b5g6r5unorm a1bgr5unorm abgr4unorm bgr5a1unorm \
r16unorm r16snorm rg16unorm rg16snorm rgba16unorm rgba16snorm r16float rg16float rgba16float \
r32float rg32float rgba32float rgb10a2unorm bgr10a2unorm rgb10a2uint rg11b10float rgb9e5float \
bgr10_xr bgr10_xr_srgb bgra10_xr bgra10_xr_srgb \
r8uint rg8uint rgba8uint r16uint rg16uint rgba16uint r32uint rg32uint rgba32uint \
r8sint rg8sint rgba8sint r16sint rg16sint rgba16sint r32sint rg32sint rgba32sint \
depth32float depth16unorm stencil8 depth32float_stencil8 x32_stencil8 gbgr422 bgrg422"
FMTS_COMP="bc1_rgba bc1_rgba_srgb bc2_rgba bc3_rgba bc4_runorm bc4_rsnorm bc5_rgunorm bc5_rgsnorm \
bc6h_rgbfloat bc6h_rgbufloat bc7_rgba bc7_rgba_srgb \
astc_4x4 astc_5x4 astc_5x5 astc_6x5 astc_6x6 astc_8x5 astc_8x6 astc_8x8 astc_10x5 astc_10x6 \
astc_10x8 astc_10x10 astc_12x10 astc_12x12 astc_4x4_hdr astc_6x6_hdr astc_8x8_hdr astc_4x4_srgb \
etc2_rgb8 etc2_rgb8a1 eac_rgba8 eac_r11unorm eac_r11snorm eac_rg11unorm eac_rg11snorm"

cap() {
  fmt=$1; W=$2; H=$3
  d=/tmp/m408_$fmt; rm -rf "$d"; mkdir -p "$d"
  line=$(IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" DYLD_INSERT_LIBRARIES=$DYL \
    ./tvar --fmt "$fmt" --w "$W" --h "$H" --dump 2>/dev/null \
    | grep -E "TEX ok|TEX_FAIL|COMPILE_FAIL|PIPELINE_FAIL")
  if echo "$line" | grep -q "TEX ok"; then
    desc=$(python3 descauto.py "$d" --tlen 0x10 2>/dev/null | grep -A1 TEXDESC | grep '+0000')
    w0=$(echo "$desc" | awk '{print $2}')
    w1=$(echo "$desc" | awk '{print $3}')
    printf 'FMT %-24s word0=%s word1=%s\n' "$fmt" "$w0" "$w1" >> "$OUT"
  else
    printf 'FMT %-24s FAIL: %s\n' "$fmt" "$line" >> "$OUT"
  fi
  rm -rf "$d"
}

for f in $FMTS_SMALL; do cap "$f" 8 8; done
for f in $FMTS_COMP;  do cap "$f" 32 32; done
echo "wrote $OUT"; wc -l "$OUT"
