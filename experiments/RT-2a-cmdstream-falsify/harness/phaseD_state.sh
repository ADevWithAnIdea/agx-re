#!/bin/sh
# RT-2a Phase D — falsify STATE PACKETS (0x58000) + PPP length word + programmable blend.
# Claims: depth +0x38, stencil +0x3c, raster +0x70, PPP output-select +0x20;
#         PPP header = monotone length word (0x18000+0x0c / 0x58000+0x14 grow +0x400 w/ depth);
#         blend is programmable (rewrites FS code BO 0x10000000000, not 0x58000).
set -e
cd "$(dirname "$0")"
DYL=./iotrace.dylib; S=0x800; BIG=0x8000
rm -rf capsD analysisD hexD; mkdir -p capsD analysisD hexD
rs(){ label="$1"; shift; d="capsD/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$S IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./svar "$@" --dump > "capsD/$label.out" 2>&1 || true
  echo "  [$label] $(grep -E 'PIPELINE_FAIL|SHADER_FAIL|ARGERR|status=' capsD/$label.out|head -1)"; }
ro(){ label="$1"; shift; d="capsD/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$S IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./ovar "$@" --dump > "capsD/$label.out" 2>&1 || true
  echo "  [$label] $(grep -E 'PIPELINE_FAIL|SHADER_FAIL|status=' capsD/$label.out|head -1)"; }
rm_(){ label="$1"; shift; d="capsD/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$BIG IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./mrtvar "$@" --dump > "capsD/$label.out" 2>&1 || true
  echo "  [$label] $(grep -E 'PIPELINE_FAIL|SHADER_FAIL|status=' capsD/$label.out|head -1)"; }
# blend needs bigger cap to see FS code BO
rb(){ label="$1"; shift; d="capsD/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$BIG IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./svar "$@" --dump > "capsD/$label.out" 2>&1 || true
  echo "  [$label] $(grep -E 'PIPELINE_FAIL|SHADER_FAIL|status=' capsD/$label.out|head -1)"; }

# ===== baselines =====
rs base   --
rs base2  --
# ===== DEPTH (0x58000+0x38): all 8 compare + write =====
rs d_ref  --depth --dcmp always --dwrite 1
for f in never less equal lequal greater nequal gequal always; do rs d_$f --depth --dcmp $f --dwrite 1; done
rs d_wroff --depth --dcmp always --dwrite 0
# ===== STENCIL (0x58000+0x3c): compare + ops + per-face =====
rs s_ref --stencil --scmp less --spass replace
for f in never less equal lequal greater nequal gequal always; do rs s_$f --stencil --scmp $f --spass replace; done
for op in keep zero replace incrclamp decrclamp invert incrwrap decrwrap; do rs sp_$op --stencil --scmp less --spass $op; done
rs s_fail  --stencil --scmp less --sfail invert
rs s_zfail --stencil --scmp less --szfail incrwrap
rs s_back  --stencil --scmp less --spass replace --sback
rs s_rd    --stencil --scmp less --spass replace --sread 0x3c
rs s_wr    --stencil --scmp less --spass replace --swrite 0x5a
rs s_ref5  --stencil --scmp less --spass replace --sref 0x27
# ===== RASTER (0x58000+0x70) =====
rs r_cullf --cull front
rs r_cullb --cull back
rs r_ccw   --front ccw
rs r_lines --fill lines
rs r_clamp --depth --dcmp always --dwrite 1 --clip clamp
# ===== PPP length word / multiple groups on-off =====
rs g_blend --blend
rs g_cull  --cull back
rs g_depth --depth --dcmp less --dwrite 1
rs g_all   --depth --dcmp less --stencil --scmp less --spass replace --blend --cull back
# ===== PPP output-select (0x58000+0x20) via ovar =====
ro o_base  --prim tri
ro o_clip1 --prim tri --clipdist 1
ro o_clip3 --prim tri --clipdist 3
ro o_clip8 --prim tri --clipdist 8
ro o_psize --prim point --pointsize 8
ro o_vpidx --prim tri --nvp 4 --vpidx 2
ro o_vp16  --prim tri --nvp 16 --vpidx 3
# ===== MRT (adversarial large) =====
rm_ mrt1 --n 1
rm_ mrt2 --n 2
rm_ mrt4 --n 4
rm_ mrt8 --n 8
rm_ mrt4b --n 4 --blendmask 0xf
# ===== programmable blend: factor/op combos + dual-source (code BO vs 0x58000) =====
rb bl_ref  --blend
rb bl_srczero --blend --srgb zero
rb bl_srcone  --blend --srgb one
rb bl_dstcol  --blend --drgb dstcolor
rb bl_opmin   --blend --brgbop min
rb bl_opsub   --blend --brgbop revsub
rb bl_dual    --dualsrc
rb bl_dual1c  --dualsrc --srgb src1color

echo "=== DIFFS ==="
D58(){ python3 bodiff.py "capsD/$1" "capsD/$2" --va 0x58000 --maxlen 0x100 > "analysisD/$3.txt" 2>&1 || true; }
D18(){ python3 bodiff.py "capsD/$1" "capsD/$2" --va 0x18000 --maxlen 0x40 > "analysisD/$3_vdm.txt" 2>&1 || true; }
DCODE(){ python3 bodiff.py "capsD/$1" "capsD/$2" --va 0x10000000000 --maxlen 0x4000 > "analysisD/$3_code.txt" 2>&1 || true; }
D58 base base2 det
for f in never less equal lequal greater nequal gequal always; do D58 d_ref d_$f depth_$f; done
D58 d_ref d_wroff depth_wroff
for f in never less equal lequal greater nequal gequal always; do D58 s_ref s_$f stencil_$f; done
for op in keep zero replace incrclamp decrclamp invert incrwrap decrwrap; do D58 s_ref sp_$op stencilop_$op; done
for v in s_fail s_zfail s_back s_rd s_wr s_ref5; do D58 s_ref $v $v; done
for v in r_cullf r_cullb r_ccw r_lines; do D58 base $v $v; done
D58 d_ref r_clamp raster_clamp
# PPP length word
D58 base g_depth ppp_depth; D18 base g_depth ppp_depth
D58 base g_blend ppp_blend; D18 base g_blend ppp_blend
D58 base g_cull  ppp_cull;  D18 base g_cull  ppp_cull
D58 base g_all   ppp_all;   D18 base g_all   ppp_all
# PPP output-select
for v in o_clip1 o_clip3 o_clip8 o_psize o_vpidx o_vp16; do D58 o_base $v $v; done
# MRT
D58 mrt1 mrt2 mrt_1v2
D58 mrt1 mrt4 mrt_1v4
D58 mrt1 mrt8 mrt_1v8
D58 mrt4 mrt4b mrt_blend
# programmable blend: code BO vs 0x58000
for v in bl_srczero bl_srcone bl_dstcol bl_opmin bl_opsub bl_dual bl_dual1c; do
  DCODE bl_ref $v $v; D58 bl_ref $v ${v}_58; done

echo "=== curated hex ==="
kb(){ f=$(ls capsD/$1/*va$2_*.hex 2>/dev/null|head -1); [ -n "$f" ] && head -20 "$f" > "hexD/$3.hex" || echo "no $1 $2"; }
kb d_ref 58000 depth_ref
kb s_ref 58000 stencil_ref
kb base 58000 base_58000
kb g_all 58000 gall_58000
kb o_clip3 58000 clip3_58000
kb mrt4 58000 mrt4_58000
kb mrt4 10000110000 mrt4_attach
# code BO sizes for blend
for v in bl_ref bl_srczero bl_dual; do
  f=$(ls capsD/$v/*va10000000000_*.hex 2>/dev/null|head -1); [ -n "$f" ] && head -4 "$f" > "hexD/${v}_codehdr.hex"; done
echo "=== length-word words 0x18000+0x0c and 0x58000+0x14 ==="
for v in base g_depth g_blend g_cull g_all; do
  f=$(ls capsD/$v/*va18000_*.hex|head -1); g=$(ls capsD/$v/*va58000_*.hex|head -1)
  w18=$(sed -n '/^00000000:/,/^00000010:/p' "$f" 2>/dev/null | sed -n '1p')
  printf "%-9s 18000: %s | 58000+0x14: %s\n" "$v" "$(sed -n '/^0000000c:/p;/^00000000:/p' "$f" 2>/dev/null|head -1)" "$(sed -n '/^00000010:/p' "$g" 2>/dev/null)"
done
echo DONE_PHASE_D