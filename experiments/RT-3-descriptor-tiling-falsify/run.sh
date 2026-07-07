#!/bin/sh
# RT-3 driver — red-team falsification of docs/descriptors + docs/tiling.
# Builds the read-only iotrace interposer (arm64e) + probes, captures the registered
# GPU BOs for a matrix chosen to BREAK the documented bit layouts / twiddle formulas,
# and runs the independent checkers. Text (hex + analysis) only.
# CLEAN-ROOM: HW-PROBE + OWN-SHADER + DATA-TRACE. No Apple binary disassembled.
set -u
cd "$(dirname "$0")"
PART="${1:-all}"

echo "=== build (arm64e) ==="
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation || exit 1
for h in dprobe tvar texprobe typrobe svar; do
  clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o $h $h.m || exit 1
done
echo built
DYL=./iotrace.dylib
mkdir -p caps analysis raw

obuf_of(){ grep -E '^VA obuf' "$1" | sed -E 's/.*= (0x[0-9a-f]+).*/\1/' | head -1; }
texbuf_of(){ grep -E '^VA texbuf' "$1" | sed -E 's/.*= (0x[0-9a-f]+).*/\1/' | head -1; }

# ---- generic capture helpers ----
capd(){ # capd LABEL PROBE -- <args>
  label="$1"; probe="$2"; shift 2; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" DYLD_INSERT_LIBRARIES=$DYL \
    ./$probe "$@" --dump > "caps/$label.out" 2>&1 || true
  st=$(grep -E 'SUBMIT status=4|status=4' "caps/$label.out" | head -1)
  fail=$(grep -E '_FAIL|CB_ERROR|COMPILE_FAIL|UNKNOWN_FMT' "caps/$label.out" | head -1)
  echo "  [$label] $st ${fail:+!! $fail}"
}

########################################################################
if [ "$PART" = descr ] || [ "$PART" = all ]; then
echo "=== PART 1: TEXTURE DESCRIPTOR (NPOT / max dims / swizzle / sRGB / mips / samples) ==="
# NPOT dims with distinct nibbles
capd d_npot_1000x700 dprobe -- --fmt rgba8unorm --w 1000 --h 700
capd d_npot_293x437  dprobe -- --fmt rgba8unorm --w 293  --h 437
# width-field size: does the doc's 12-bit claim hold at/above 4096?
capd d_w4096  dprobe -- --fmt r8unorm --w 4096  --h 8
capd d_w8192  dprobe -- --fmt r8unorm --w 8192  --h 8
capd d_w16384 dprobe -- --fmt r8unorm --w 16384 --h 8
capd d_h8192  dprobe -- --fmt r8unorm --w 8  --h 8192
capd d_h16384 dprobe -- --fmt r8unorm --w 8  --h 16384
# swizzle (a NEW combo) + sRGB
capd d_swz_ab01 dprobe -- --fmt rgba8unorm --swizzle ab01 --w 64 --h 64
capd d_srgb_r8  dprobe -- --fmt r8unorm_srgb --w 64 --h 64
capd d_srgb_bc7 dprobe -- --fmt bc7_srgb --w 64 --h 64
# mips (max chain) + sample counts + 3D depth + array
capd d_mip9_256 dprobe -- --fmt r32uint --w 256 --h 256 --mips 9
capd d_mip10_512 dprobe -- --fmt r32uint --w 512 --h 512 --mips 10
capd d_ms2 dprobe -- --fmt rgba8unorm --type 2dms --w 64 --h 64 --samples 2
capd d_ms4 dprobe -- --fmt rgba8unorm --type 2dms --w 64 --h 64 --samples 4
capd d_3d  dprobe -- --fmt r32uint --type 3d --w 32 --h 32 --d 16
capd d_arr dprobe -- --fmt rgba8unorm --type 2darray --w 64 --h 64 --arraylen 6
# base VA (buffer-backed, exact known VA): tvar --texoff
capd d_bva_1000 tvar -- --type 2d --fmt rgba8unorm --texoff 0x1000
capd d_bva_5000 tvar -- --type 2d --fmt rgba8unorm --texoff 0x5000
capd d_bva_a000 tvar -- --type 2d --fmt rgba8unorm --texoff 0xa000
fi

########################################################################
if [ "$PART" = samp ] || [ "$PART" = all ]; then
echo "=== PART 2: SAMPLER DESCRIPTOR (all address modes / compare / border / filter) ==="
for A in edge repeat mirror clampzero border mirroredge; do
  capd s_saddr_$A tvar -- --saddr $A
done
capd s_taddr_mirror tvar -- --taddr mirror
capd s_raddr_repeat tvar -- --raddr repeat
for C in less lequal greater gequal equal nequal always never; do
  capd s_cmp_$C tvar -- --cmp $C
done
for B in tblack oblack owhite; do
  capd s_border_$B tvar -- --saddr border --border $B
done
capd s_filt_lin  tvar -- --minf linear --magf linear --mipf linear
capd s_filt_mipn tvar -- --mipf nearest
capd s_aniso2 tvar -- --aniso 2
capd s_aniso4 tvar -- --aniso 4
capd s_aniso8 tvar -- --aniso 8
capd s_aniso16 tvar -- --aniso 16
capd s_lod tvar -- --lodmin 1.5 --lodmax 7.0
capd s_unnorm tvar -- --unorm
fi

########################################################################
if [ "$PART" = fmt ] || [ "$PART" = all ]; then
echo "=== PART 4: FORMAT->CODE TABLE (obscure formats) ==="
for F in r16snorm rg16unorm rg16snorm rgba16snorm r16sint rg16sint rg16uint rgba16sint \
         rg8snorm rg8sint r8unorm_srgb rgba8sint rgb10a2uint bgr10_xr bgra10_xr bgr10_xr_srgb \
         rg32uint rg32sint rgba32sint depth16unorm stencil8 depth32float_stencil8 \
         eac_r11unorm eac_r11snorm eac_rg11unorm etc2_rgb8 etc2_rgb8a1; do
  capd f_$F dprobe -- --fmt $F --w 64 --h 64
done
# block-compressed need block-multiple dims (64 is fine)
for F in bc1_rgba bc3_rgba bc4_runorm bc4_rsnorm bc5_rgunorm bc6h_float bc7_rgba \
         astc_5x5 astc_6x6 astc_10x10 astc_8x8_hdr astc_6x6_srgb; do
  capd f_$F dprobe -- --fmt $F --w 64 --h 64
done
fi

########################################################################
if [ "$PART" = pbe ] || [ "$PART" = all ]; then
echo "=== PART 3: PBE / storage-image descriptor (new fmts/sizes + read_write) ==="
capd p_w_r32f_96x48   svar -- --fmt r32f    --access write --w 96 --h 48
capd p_w_rgba8_100x60 svar -- --fmt rgba8   --access write --w 100 --h 60
capd p_w_rgba16f_40x24 svar -- --fmt rgba16f --access write --w 40 --h 24
capd p_rw_rgba8_64x64 svar -- --fmt rgba8   --access readwrite --w 64 --h 64
capd p_rw_r32f_48x40  svar -- --fmt r32f    --access readwrite --w 48 --h 40
capd p_w_rg32f_16384x8 svar -- --fmt rg32f  --access write --w 8192 --h 8
fi

########################################################################
if [ "$PART" = twid ] || [ "$PART" = all ]; then
echo "=== PART 5: TWIDDLE FORMULAS (readback) ==="
# 2D large + NPOT non-square (both append directions)
capd t_2d_256   texprobe -- --fmt r32uint --w 256 --h 256
capd t_2d_48x80 texprobe -- --fmt r32uint --w 48  --h 80
capd t_2d_80x48 texprobe -- --fmt r32uint --w 80  --h 48
capd t_2d_96x160 texprobe -- --fmt r32uint --w 96 --h 160
capd t_2d_33x17 texprobe -- --fmt r32uint --w 33  --h 17
# 3D / array / cube / MSAA
capd t_3d_16x16x8 typrobe -- --type 3d --w 16 --h 16 --d 8
capd t_arr6_16    typrobe -- --type 2darray --w 16 --h 16 --arraylen 6
capd t_cube_16    typrobe -- --type cube --w 16 --h 16
capd t_ms2_16     typrobe -- --type 2dms --w 16 --h 16 --samples 2
capd t_ms4_16     typrobe -- --type 2dms --w 16 --h 16 --samples 4
fi

########################################################################
if [ "$PART" = comp ] || [ "$PART" = all ]; then
echo "=== PART 6: COMPRESSION (NPOT + mipmapped thresholds) ==="
# threshold sweep (sampled read-only rgba8 -> compression iff >=16x16)
capd c_15x15 dprobe -- --fmt rgba8unorm --w 15 --h 15
capd c_16x16 dprobe -- --fmt rgba8unorm --w 16 --h 16
capd c_17x15 dprobe -- --fmt rgba8unorm --w 17 --h 15
capd c_15x17 dprobe -- --fmt rgba8unorm --w 15 --h 17
capd c_17x17 dprobe -- --fmt rgba8unorm --w 17 --h 17
capd c_npot_100x100 dprobe -- --fmt rgba8unorm --w 100 --h 100
capd c_npot_48x80   dprobe -- --fmt rgba8unorm --w 48 --h 80
# mipmapped compressible (one aux for whole chain)
capd c_mip_128 dprobe -- --fmt rgba8unorm --w 128 --h 128 --mips 4
capd c_mip_96  dprobe -- --fmt rgba8unorm --w 96  --h 96  --mips 4
fi

echo "=== capture phase done for PART=$PART ==="
ls caps/ | head
