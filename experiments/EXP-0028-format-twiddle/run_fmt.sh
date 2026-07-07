#!/bin/sh
# EXP-0028 part 1+4 — FORMAT-code and TYPE-code descriptor capture sweep.
# Builds fmtprobe + the read-only iotrace interposer, captures the appended
# texture descriptor for a matrix of untested formats and texture types, and
# decodes byte0/byte1 + type code host-side. Text artifacts only. Clean-room:
# DATA-TRACE + OWN-SHADER.
set -u
cd "$(dirname "$0")"

echo "=== build ==="
clang -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation || exit 1
clang -fobjc-arc -framework Metal -framework Foundation -o fmtprobe fmtprobe.m || exit 1
echo built

DYL=./iotrace.dylib
rm -rf caps analysis; mkdir -p caps analysis

cap() {  # cap LABEL W H -- <fmtprobe args...>
  label="$1"; W="$2"; H="$3"; shift 3; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./fmtprobe "$@" --dump > "caps/$label.stdout" 2>&1 || true
  st=$(grep -oE 'SUBMIT done status=[0-9]+|UNSUPPORTED[_A-Z]*|COMPILE_FAIL|PIPELINE_FAIL' "caps/$label.stdout" | head -1)
  echo "  cap $label ($W x $H) $* -> $st"
}

echo "=== FORMAT sweep (all 2D, 32x32) ==="
FMTS="r16snorm rg16unorm rg16snorm rgba16snorm rg16uint rg16sint rgba16sint r16sint \
rg8snorm rg8sint rg32uint rg32sint rgba32sint rgb10a2uint bgr10a2unorm \
bgra10_xr bgra10_xr_srgb bgr10_xr bgr10_xr_srgb \
depth16unorm depth32float stencil8 depth32float_stencil8 depth24unorm_stencil8 x32_stencil8 x24_stencil8 \
bc1_rgba bc1_rgba_srgb bc2_rgba bc3_rgba bc4_runorm bc4_rsnorm bc5_rgunorm bc5_rgsnorm \
bc6h_rgbfloat bc6h_rgbufloat bc7_rgba bc7_rgba_srgb \
etc2_rgb8 etc2_rgb8_srgb etc2_rgb8a1 eac_rgba8 eac_r11unorm eac_r11snorm eac_rg11unorm eac_rg11snorm \
astc_4x4_ldr astc_5x5_ldr astc_6x6_ldr astc_8x8_ldr astc_10x10_ldr astc_12x12_ldr astc_4x4_srgb astc_8x8_srgb \
astc_4x4_hdr astc_6x6_hdr astc_8x8_hdr pvrtc_rgba_4bpp pvrtc_rgb_4bpp \
rgba8unorm r32uint"
for f in $FMTS; do cap fmt_$f 32 32 -- --type 2d --fmt $f --w 32 --h 32; done

echo "=== TYPE sweep (rgba8unorm, capture type codes) ==="
cap type_1d        16 1  -- --type 1d        --fmt rgba8unorm --w 16 --h 1
cap type_1darray   16 1  -- --type 1darray   --fmt rgba8unorm --w 16 --h 1 --arraylen 6
cap type_2d        16 16 -- --type 2d        --fmt rgba8unorm --w 16 --h 16
cap type_2darray   16 16 -- --type 2darray   --fmt rgba8unorm --w 16 --h 16 --arraylen 6
cap type_cube      16 16 -- --type cube      --fmt rgba8unorm --w 16 --h 16
cap type_cubearray 16 16 -- --type cubearray --fmt rgba8unorm --w 16 --h 16 --arraylen 2
cap type_3d        16 16 -- --type 3d        --fmt rgba8unorm --w 16 --h 16 --d 4
cap type_2dms2     16 16 -- --type 2dms      --fmt rgba8unorm --w 16 --h 16 --samples 2
cap type_2dms4     16 16 -- --type 2dms      --fmt rgba8unorm --w 16 --h 16 --samples 4
cap type_2dmsarray 16 16 -- --type 2dmsarray --fmt rgba8unorm --w 16 --h 16 --samples 4 --arraylen 2

echo "=== decode descriptors ==="
{
  echo "##### FORMAT CODES (2D, 32x32) #####"
  for f in $FMTS; do
    python3 fmtx.py caps/fmt_$f --w 32 --h 32 --type 2 --label "fmt_$f" 2>&1
    grep -hE 'UNSUPPORTED|COMPILE_FAIL|PIPELINE_FAIL' caps/fmt_$f.stdout 2>/dev/null || true
  done
  echo; echo "##### TYPE CODES #####"
  python3 fmtx.py caps/type_1d        --w 16 --h 1  --label type_1d
  python3 fmtx.py caps/type_1darray   --w 16 --h 1  --label type_1darray
  python3 fmtx.py caps/type_2d        --w 16 --h 16 --label type_2d
  python3 fmtx.py caps/type_2darray   --w 16 --h 16 --label type_2darray
  python3 fmtx.py caps/type_cube      --w 16 --h 16 --label type_cube
  python3 fmtx.py caps/type_cubearray --w 16 --h 16 --label type_cubearray
  python3 fmtx.py caps/type_3d        --w 16 --h 16 --label type_3d
  python3 fmtx.py caps/type_2dms2     --w 16 --h 16 --label type_2dms2
  python3 fmtx.py caps/type_2dms4     --w 16 --h 16 --label type_2dms4
  python3 fmtx.py caps/type_2dmsarray --w 16 --h 16 --label type_2dmsarray
} > analysis/decoded.txt 2>&1
cat analysis/decoded.txt
echo "=== done run_fmt ==="
