#!/bin/sh
# EXP-O2A driver — runs on the A18 device under ~/cleanroom_work/exp_o2a.
# Builds the parametric GEOMETRY-OUTPUT draw harness (ovar) + iotrace, captures the
# registered GPU BOs for a change-one-Metal-parameter matrix over the six O2-A
# features, and byte-diffs the control BOs (0x68000 viewport ctx, 0x58000 FF-state,
# 0x18000 VDM, 0x10000130000 USC, 0x10000000000 code) on-device. Pulls back text
# diffs + curated hexdumps only. CLEAN-ROOM: DATA-TRACE + OWN-SHADER.
set -e
cd "$(dirname "$0")"

echo "=== build ==="
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o ovar ovar.m
echo "built"

DYL=./iotrace.dylib
CAP=0x10000        # 64KB/BO: covers 0x68000 arrays, 0x58000 state, USC + start of code BO
rm -rf caps analysis hex; mkdir -p caps analysis hex

run() {  # run LABEL -- <ovar args...>
  label="$1"; shift; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_MAX_MAP="$CAP" IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./ovar "$@" --dump > "caps/$label.stdout" 2>&1 || true
  st=$(grep -E '^(PIPELINE_FAIL|PIPELINE_EXC|SHADER_FAIL|VIEWPORT_EXC|SCISSOR_EXC|DRAW_EXC|ARGERR|CB_ERROR|RTBUF_REJECTED)' "caps/$label.stdout" | head -3 || true)
  sub=$(grep -cE '^SUBMIT.*done status=4' "caps/$label.stdout" || true)
  echo "  [$label] submits_ok=$sub ${st:+ISSUE: $st}"
}

# ===== determinism baseline =====
run base   --
run base2  --

# ===== Feature 1: multiple viewports / scissor rects =====
run vp0   -- --nvp 0                 # single setViewport (baseline shape)
run vp1   -- --nvp 1
run vp2   -- --nvp 2
run vp2m  -- --nvp 2 --vpmod         # perturb ONLY viewport[1] -> stride isolation
run vp4   -- --nvp 4
run vp8   -- --nvp 8
run vp16  -- --nvp 16
run sc1   -- --nsc 1
run sc2   -- --nsc 2
run sc2m  -- --nsc 2 --scmod
run sc4   -- --nsc 4
run sc8   -- --nsc 8
# VS [[viewport_array_index]] output (needs multi-viewport set)
run vpx0  -- --nvp 4 --vpidx 0
run vpx1  -- --nvp 4 --vpidx 1
run vpx3  -- --nvp 4 --vpidx 3

# ===== Feature 2: clip distances =====
run clip1 -- --clipdist 1
run clip2 -- --clipdist 2
run clip3 -- --clipdist 3
run clip4 -- --clipdist 4
run clip8 -- --clipdist 8

# ===== Feature 3: point_size + primitive-type paths =====
run pt        -- --prim point
run pt_ps     -- --prim point --pointsize 8
run pt_ps16   -- --prim point --pointsize 16
run line      -- --prim line
run linestrip -- --prim linestrip
run tristrip  -- --prim tristrip

# ===== Feature 4: primitive restart / index type =====
run ix_tri16   -- --indexed --itype u16 --prim tri
run ix_tri32   -- --indexed --itype u32 --prim tri
run ix_str16   -- --indexed --itype u16 --prim tristrip
run ix_str32   -- --indexed --itype u32 --prim tristrip
run ix_str16r  -- --indexed --itype u16 --prim tristrip --restart
run ix_str32r  -- --indexed --itype u32 --prim tristrip --restart

# ===== Feature 5: alpha-to-coverage / alpha-to-one (need MSAA to be meaningful) =====
run ms4      -- --msaa 4
run ms4_a2c  -- --msaa 4 --a2c
run ms4_a2o  -- --msaa 4 --a2o
run a2c1     -- --a2c              # a2c at msaa=1 (does the bit still set?)

# ===== Feature 6: fill mode (Metal: fill|lines only; point-fill not exposed) =====
run fill_lines -- --fill lines

echo "=== on-device diffs ==="
# targeted single-BO diffs (clean signal) + full-dir discovery diffs.
dv() { # dv A B VA MAXLEN OUT
  python3 bodiff.py "caps/$1" "caps/$2" --va "$3" --maxlen "$4" > "analysis/$5.txt" 2>&1 || true; }
df() { # df A B OUT  (full-dir discovery; note gpu_va=0x0 sel-5 pairing is noise)
  python3 bodiff.py "caps/$1" "caps/$2" --maxlen 0x2000 > "analysis/$3.txt" 2>&1 || true; }

# determinism
df base base2 det_base

# viewports: 0x68000 tiling/viewport context
for v in vp1 vp2 vp2m vp4 vp8 vp16; do dv vp0 $v 0x68000 0x2000 vp_68k_$v; done
dv vp2 vp2m 0x68000 0x2000 vp_68k_slot1
df vp0 vp2 vp_full_0v2
df vp0 vp16 vp_full_0v16
# scissor
for v in sc1 sc2 sc2m sc4 sc8; do dv base $v 0x68000 0x2000 sc_68k_$v; done
dv sc2 sc2m 0x68000 0x2000 sc_68k_slot1
df base sc4 sc_full
df base sc2m sc_full_slot1
# viewport_array_index output
df vp4 vpx0 vpx_full_0
dv vpx0 vpx1 0x68000 0x2000 vpx_68k_01
df vpx0 vpx1 vpx_full_01
df vpx0 vpx3 vpx_full_03

# clip distances: check USC, code, 0x58000, 0x68000, VDM
for v in clip1 clip2 clip3 clip4 clip8; do df base $v clip_full_$v; done
dv base clip1 0x10000130000 0x2000 clip_usc_1
dv base clip4 0x10000130000 0x2000 clip_usc_4
dv clip1 clip4 0x10000130000 0x2000 clip_usc_1v4

# point_size + prim types (VDM 0x18000)
dv base pt 0x18000 0x100 pt_vdm
dv pt pt_ps 0x18000 0x100 pt_ps_vdm
df pt pt_ps pt_ps_full
df base pt pt_full
dv base line 0x18000 0x100 line_vdm
dv base linestrip 0x18000 0x100 linestrip_vdm
dv base tristrip 0x18000 0x100 tristrip_vdm

# primitive restart / index type (VDM 0x18000)
dv base ix_tri16 0x18000 0x100 ix_tri16_vdm
dv ix_tri16 ix_tri32 0x18000 0x100 ix_type_16v32
dv ix_tri16 ix_str16 0x18000 0x100 ix_tri_v_strip
dv ix_str16 ix_str16r 0x18000 0x100 ix_restart_enable16
dv ix_str16r ix_str32r 0x18000 0x100 ix_restart_16v32
df ix_str16 ix_str16r ix_restart_full

# alpha-to-coverage / alpha-to-one (0x58000 + full discovery)
dv ms4 ms4_a2c 0x58000 0x200 a2c_58k
dv ms4 ms4_a2o 0x58000 0x200 a2o_58k
df ms4 ms4_a2c a2c_full
df ms4 ms4_a2o a2o_full
df base a2c1 a2c1_full

# fill mode reconfirm (0x58000 raster)
dv base fill_lines 0x58000 0x100 fill_lines_58k
df base fill_lines fill_full

echo "=== curated hexdumps ==="
keep() { # keep CAP VA OUT NLINES
  f=$(ls caps/$1/bo_sigusr1_*_va$2_*.hex 2>/dev/null | head -1)
  [ -n "$f" ] && head -${4:-160} "$f" > "hex/$3.hex" 2>/dev/null || echo "  (no $2 in $1)"; }
# viewport array
keep vp0  68000 vp0_68000 300
keep vp2  68000 vp2_68000 300
keep vp4  68000 vp4_68000 300
keep vp16 68000 vp16_68000 400
keep vp2m 68000 vp2m_68000 300
# scissor
keep sc4  68000 sc4_68000 400
keep sc2m 68000 sc2m_68000 400
keep base 68000 base_68000 300
# VDM prim/index
keep base       18000 base_18000 120
keep pt         18000 pt_18000 120
keep ix_tri16   18000 ix_tri16_18000 120
keep ix_tri32   18000 ix_tri32_18000 120
keep ix_str16r  18000 ix_str16r_18000 120
keep ix_str32r  18000 ix_str32r_18000 120
# state pool
keep base    58000 base_58000 160
keep ms4     58000 ms4_58000 160
keep ms4_a2c 58000 ms4_a2c_58000 160
keep ms4_a2o 58000 ms4_a2o_58000 160
keep fill_lines 58000 fill_lines_58000 160
# clip / vpidx output select (USC + code)
keep base  10000130000 base_usc 120
keep clip4 10000130000 clip4_usc 120
keep vpx1  10000130000 vpx1_usc 120
keep base  10000000000 base_code 60
keep clip4 10000000000 clip4_code 60

# selector / BO-count sanity
{ echo "== base =="; grep -cE '^CALL' caps/base.trace; \
  echo "== BOs (sel-9 gpu_va) =="; grep -oE 'gpu_va=0x[0-9a-f]+' caps/base.trace | sort -u | head -60; } > analysis/selhist.txt 2>&1 || true

echo "=== done. caps=$(ls -d caps/*/ 2>/dev/null | wc -l) analysis=$(ls analysis | wc -l) hex=$(ls hex | wc -l) ==="
