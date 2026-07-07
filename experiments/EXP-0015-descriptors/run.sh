#!/bin/sh
# EXP-0015 driver — runs on the A18 device under ~/cleanroom_work/exp0015.
# Builds the parametric texture/sampler descriptor harness + the (read-only) iotrace
# interposer, captures the registered GPU BOs for a matrix of one-descriptor-parameter-
# changed compute dispatches, and extracts/diffs the appended descriptor blocks.
# Pulls back text only. Clean-room: DATA-TRACE + OWN-SHADER.
set -u
cd "$(dirname "$0")"

echo "=== build ==="
clang -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -fobjc-arc -framework Metal -framework Foundation -o tvar tvar.m
echo "built"

DYL=./iotrace.dylib
rm -rf caps; mkdir -p caps analysis raw

cap() {  # cap LABEL -- <tvar args...>
  label="$1"; shift; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./tvar "$@" --dump > "caps/$label.stdout" 2>&1 || true
  ok=$(grep -c 'SUBMIT done status=4' "caps/$label.stdout" 2>/dev/null || echo 0)
  echo "  cap $label  ok=$ok  : $*"
  grep -E '^(CB_ERROR|.*_FAIL|BORDER_UNSUPPORTED)' "caps/$label.stdout" 2>/dev/null || true
}

# ============ TEXTURE DESCRIPTOR ============
# ---- format sweep (float/normalized kernels) ----
for f in r8unorm r8snorm a8unorm rg8unorm rgba8unorm rgba8snorm bgra8unorm \
         rgba8unorm_srgb bgra8unorm_srgb r16unorm rgba16unorm r16float rg16float \
         rgba16float r32float rg32float rgba32float rgb10a2unorm bgr10a2unorm \
         rg11b10float rgb9e5float; do
  cap fmt_$f -- --type 2d --fmt $f --w 4 --h 4
done
# ---- format sweep (uint/sint kernels) ----
for f in r8uint rg8uint rgba8uint r16uint rgba16uint r32uint rgba32uint \
         r8sint rgba8sint r32sint; do
  cap fmt_$f -- --type 2d --fmt $f --w 4 --h 4
done

# ---- dimensions ----
cap dim_4x4    -- --type 2d --fmt rgba8unorm --w 4   --h 4
cap dim_8x4    -- --type 2d --fmt rgba8unorm --w 8   --h 4
cap dim_4x8    -- --type 2d --fmt rgba8unorm --w 4   --h 8
cap dim_16x16  -- --type 2d --fmt rgba8unorm --w 16  --h 16
cap dim_64x32  -- --type 2d --fmt rgba8unorm --w 64  --h 32
cap dim_1x1    -- --type 2d --fmt rgba8unorm --w 1   --h 1
cap dim_256x1  -- --type 2d --fmt rgba8unorm --w 256 --h 1
cap dim_100x50 -- --type 2d --fmt rgba8unorm --w 100 --h 50

# ---- texture type ----
cap type_1d      -- --type 1d      --fmt rgba8unorm --w 16
cap type_2d      -- --type 2d      --fmt rgba8unorm --w 16 --h 16
cap type_3d      -- --type 3d      --fmt rgba8unorm --w 16 --h 16 --d 4
cap type_cube    -- --type cube    --fmt rgba8unorm --w 16 --h 16
cap type_2darray -- --type 2darray --fmt rgba8unorm --w 16 --h 16 --arraylen 6
cap type_2dms    -- --type 2dms    --fmt rgba8unorm --w 16 --h 16 --samples 4

# ---- depth (3d) volume depth ----
cap d3d_d2 -- --type 3d --fmt rgba8unorm --w 16 --h 16 --d 2
cap d3d_d8 -- --type 3d --fmt rgba8unorm --w 16 --h 16 --d 8

# ---- mip levels ----
cap mip_1 -- --type 2d --fmt rgba8unorm --w 16 --h 16 --mips 1
cap mip_2 -- --type 2d --fmt rgba8unorm --w 16 --h 16 --mips 2
cap mip_4 -- --type 2d --fmt rgba8unorm --w 16 --h 16 --mips 4
cap mip_5 -- --type 2d --fmt rgba8unorm --w 16 --h 16 --mips 5

# ---- array length ----
cap arr_1 -- --type 2darray --fmt rgba8unorm --w 16 --h 16 --arraylen 1
cap arr_2 -- --type 2darray --fmt rgba8unorm --w 16 --h 16 --arraylen 2
cap arr_6 -- --type 2darray --fmt rgba8unorm --w 16 --h 16 --arraylen 6

# ---- sample count (MS) ----
cap ms_2 -- --type 2dms --fmt rgba8unorm --w 16 --h 16 --samples 2
cap ms_4 -- --type 2dms --fmt rgba8unorm --w 16 --h 16 --samples 4

# ---- swizzle / channel map ----
cap sw_rgba -- --type 2d --fmt rgba8unorm --w 4 --h 4 --swizzle rgba
cap sw_bgra -- --type 2d --fmt rgba8unorm --w 4 --h 4 --swizzle bgra
cap sw_rrrr -- --type 2d --fmt rgba8unorm --w 4 --h 4 --swizzle rrrr
cap sw_aaaa -- --type 2d --fmt rgba8unorm --w 4 --h 4 --swizzle aaaa
cap sw_000a -- --type 2d --fmt rgba8unorm --w 4 --h 4 --swizzle 000a
cap sw_1111 -- --type 2d --fmt rgba8unorm --w 4 --h 4 --swizzle 1111
cap sw_gbar -- --type 2d --fmt rgba8unorm --w 4 --h 4 --swizzle gbar

# ---- base GPU VA (buffer-backed 2D texture; VA = texbuf.gpuAddress+texoff) ----
cap va_0     -- --type 2d --fmt rgba8unorm --w 16 --h 16 --texoff 0
cap va_100   -- --type 2d --fmt rgba8unorm --w 16 --h 16 --texoff 0x100
cap va_1000  -- --type 2d --fmt rgba8unorm --w 16 --h 16 --texoff 0x1000
cap va_10000 -- --type 2d --fmt rgba8unorm --w 16 --h 16 --texoff 0x10000

# ============ SAMPLER DESCRIPTOR ============
S="--type 2d --fmt rgba8unorm --w 16 --h 16"
cap smp_base    -- $S
cap smp_minlin  -- $S --minf linear
cap smp_maglin  -- $S --magf linear
cap smp_bothlin -- $S --minf linear --magf linear
cap smp_mipnear -- $S --mipf nearest
cap smp_miplin  -- $S --mipf linear
cap smp_srep    -- $S --saddr repeat
cap smp_trep    -- $S --taddr repeat
cap smp_smir    -- $S --saddr mirror
cap smp_sczero  -- $S --saddr clampzero
cap smp_smedge  -- $S --saddr mirroredge
cap smp_sborder -- $S --saddr border
cap smp_aniso2  -- $S --aniso 2
cap smp_aniso4  -- $S --aniso 4
cap smp_aniso16 -- $S --aniso 16
cap smp_unorm   -- $S --unorm
cap smp_lodmin1 -- $S --lodmin 1
cap smp_lodmax3 -- $S --lodmax 3
cap smp_lod2_5  -- $S --lodmin 2 --lodmax 5
cap smp_lodmaxf -- $S --lodmax 15
cap smp_bordwhite -- $S --saddr border --border owhite
cap smp_bordblack -- $S --saddr border --border oblack
cap smp_bordtrans -- $S --saddr border --border tblack

# ---- 3D so the r (3rd) axis address mode is meaningful ----
S3="--type 3d --fmt rgba8unorm --w 16 --h 16 --d 4"
cap smp3_base -- $S3
cap smp3_rrep -- $S3 --raddr repeat
cap smp3_rmir -- $S3 --raddr mirror

# ---- compare function (depth-compare sampler path) ----
for c in never less lequal greater gequal equal nequal always; do
  cap cmp_$c -- --cmp --cmpf $c
done

echo "=== extract descriptors ==="
# per-capture human-readable descriptor dump (word view)
for d in caps/*/ ; do
  l=$(basename "$d")
  python3 descx.py "$d" --words --tlen 0x30 --slen 0x40 > "raw/desc_$l.txt" 2>&1 || true
done

# raw offset-relative hex (for stable diffing)
for d in caps/*/ ; do
  l=$(basename "$d")
  python3 descx.py "$d" --tlen 0x30 --slen 0x40 > "analysis/hex_$l.txt" 2>&1 || true
done

echo "=== diffs vs group baselines ==="
dcmp() { # dcmp BASE VARIANT
  echo "### $2 vs $1"; diff "analysis/hex_$1.txt" "analysis/hex_$2.txt" || true
}
{
  echo "===== FORMAT (base fmt_rgba8unorm) ====="
  for f in r8unorm r8snorm a8unorm rg8unorm rgba8snorm bgra8unorm rgba8unorm_srgb \
           bgra8unorm_srgb r16unorm rgba16unorm r16float rg16float rgba16float \
           r32float rg32float rgba32float rgb10a2unorm bgr10a2unorm rg11b10float \
           rgb9e5float r8uint rg8uint rgba8uint r16uint rgba16uint r32uint rgba32uint \
           r8sint rgba8sint r32sint; do
    dcmp fmt_rgba8unorm fmt_$f
  done
} > analysis/diff_format.txt 2>&1

{
  echo "===== DIMENSIONS (base dim_4x4) ====="
  for v in 8x4 4x8 16x16 64x32 1x1 256x1 100x50; do dcmp dim_4x4 dim_$v; done
} > analysis/diff_dim.txt 2>&1

{
  echo "===== TYPE (base type_2d) ====="
  for v in 1d 3d cube 2darray 2dms; do dcmp type_2d type_$v; done
  echo "===== 3D depth ====="; dcmp type_3d d3d_d2; dcmp type_3d d3d_d8
  echo "===== MIPS (base mip_1) ====="; for v in 2 4 5; do dcmp mip_1 mip_$v; done
  echo "===== ARRAY (base arr_1) ====="; for v in 2 6; do dcmp arr_1 arr_$v; done
  echo "===== MS (base ms_2) ====="; dcmp ms_2 ms_4
} > analysis/diff_type.txt 2>&1

{
  echo "===== SWIZZLE (base sw_rgba) ====="
  for v in bgra rrrr aaaa 000a 1111 gbar; do dcmp sw_rgba sw_$v; done
} > analysis/diff_swizzle.txt 2>&1

{
  echo "===== BASE VA (base va_0) ====="
  for v in 100 1000 10000; do dcmp va_0 va_$v; done
} > analysis/diff_va.txt 2>&1

{
  echo "===== SAMPLER (base smp_base) ====="
  for v in minlin maglin bothlin mipnear miplin srep trep smir sczero smedge sborder \
           aniso2 aniso4 aniso16 unorm lodmin1 lodmax3 lod2_5 lodmaxf \
           bordwhite bordblack bordtrans; do dcmp smp_base smp_$v; done
  echo "===== SAMPLER 3D r-axis (base smp3_base) ====="
  for v in rrep rmir; do dcmp smp3_base smp3_$v; done
} > analysis/diff_sampler.txt 2>&1

{
  echo "===== COMPARE FUNC (base cmp_never) ====="
  for v in less lequal greater gequal equal nequal always; do dcmp cmp_never cmp_$v; done
} > analysis/diff_compare.txt 2>&1

echo "=== VA correlation (texbuf gpuAddress vs descriptor) ==="
for v in va_0 va_100 va_1000 va_10000; do
  echo "--- $v ---"; grep -E '^(TEXBUF|VA texbuf)' caps/$v.stdout
  python3 descx.py caps/$v --words --tlen 0x30 --slen 0x10 | sed -n '/TEXDESC/,/SAMPDESC/p'
done > analysis/va_correlation.txt 2>&1

echo "=== done. see analysis/ and raw/ ==="
