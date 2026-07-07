#!/bin/sh
# EXP-0021 driver — runs on the A18 device under ~/cleanroom_work/exp0021.
# Builds the TBDR parametric draw harness (tvar) + iotrace, captures the registered
# GPU BOs for a change-one-TBDR-parameter matrix, and byte-diffs the tiling context
# (0x68000), 3D attachment descriptor (0x10000110000), FF-state (0x58000), and tiler
# parameter heap on-device. Pulls back text + curated hexdumps only.
# CLEAN-ROOM: DATA-TRACE + OWN-SHADER.
set -e
cd "$(dirname "$0")"

echo "=== build (arm64e; macOS 26 needs interposer+process arch to match) ==="
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o tvar tvar.m
echo "built"

DYL=./iotrace.dylib
CAP=0x8000      # per-BO dump cap (TBDR fields all < 0x2000; attachment chain < 0x1000)
export IOTRACE_MAX_MAP=$CAP

rm -rf caps analysis; mkdir -p caps analysis

run() {  # run LABEL -- <tvar args...>
  label="$1"; shift; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./tvar "$@" --dump > "caps/$label.stdout" 2>&1 || true
  st=$(grep -E '^(PIPELINE_FAIL|SUBMIT.*status=[^4])' "caps/$label.stdout" | head -1 || true)
  cfg=$(grep -E '^CONFIG' "caps/$label.stdout" | head -1 || true)
  echo "  [$label] ${st:-ok}"
}

# ===== baseline / determinism =====
run base   --
run base2  --

# ===== Q1: tile size — RT-size sweep (fixed bgra8) =====
run rt32   -- --w 32  --h 32
run rt96   -- --w 96  --h 96
run rt128  -- --w 128 --h 128
run rt160  -- --w 160 --h 160
run rt256  -- --w 256 --h 256
run rt64x128 -- --w 64 --h 128
# asymmetric to separate x-tiles from y-tiles
run rt128x64 -- --w 128 --h 64

# ===== Q1/Q2: pixel format sweep (fixed 64x64) — bpp affects tile budget =====
run fmt_r8      -- --fmt r8
run fmt_r32f    -- --fmt r32f
run fmt_rgb10a2 -- --fmt rgb10a2
run fmt_rgba16f -- --fmt rgba16f
run fmt_rgba32f -- --fmt rgba32f

# ===== Q2: imageblock / tile memory — MRT count (single-sample) =====
run mrt2  -- --mrt 2
run mrt3  -- --mrt 3
run mrt4  -- --mrt 4
run mrt2_16f -- --mrt 2 --fmt rgba16f
run mrt4_32f -- --mrt 4 --fmt rgba32f

# ===== Q3: MSAA sample count + programmable sample positions =====
run msaa2       -- --samples 2
run msaa4       -- --samples 4
run msaa2_sp    -- --samples 2 --sampos
run msaa4_sp    -- --samples 4 --sampos
run msaa4_16f   -- --samples 4 --fmt rgba16f

# ===== Q4: memoryless attachments =====
run depth_priv  -- --depth                 # Private depth (baseline)
run depth_ml    -- --depth --mldepth       # Memoryless depth
run msaa4_col   -- --samples 4             # Private MSAA color (baseline for mlcolor)
run msaa4_mlcol -- --samples 4 --mlcolor   # Memoryless MSAA color

# ===== Q5: load/store actions + partial render =====
run ld_load     -- --load load             # color load = Load (vs Clear)
run ld_dc       -- --load dontcare         # color load = DontCare
run st_dc       -- --store dontcare        # color store = DontCare (vs Store)
run nocolor     -- --depth --nocolor       # depth-only (partial / Z prepass)
run depth_dstore -- --depth --dstore store # store depth to memory (vs DontCare)
run depth_dload  -- --depth --dload load   # load depth from memory

echo "=== on-device diffs ==="
# d REF VAR -> analysis/diff_VAR.txt across all paired BOs (noise floor 0 for identical cfg)
d() { python3 bodiff.py "caps/$1" "caps/$2" --maxlen 0x1000 > "analysis/diff_$2.txt" 2>&1 || true; }

d base base2
# tile size vs base (bgra8 64x64)
for v in rt32 rt96 rt128 rt160 rt256 rt64x128 rt128x64; do d base $v; done
# format vs base
for v in fmt_r8 fmt_r32f fmt_rgb10a2 fmt_rgba16f fmt_rgba32f; do d base $v; done
# MRT vs base
for v in mrt2 mrt3 mrt4 mrt2_16f mrt4_32f; do d base $v; done
# MSAA vs base
for v in msaa2 msaa4 msaa4_16f; do d base $v; done
d msaa2 msaa2_sp
d msaa4 msaa4_sp
# memoryless
d depth_priv depth_ml
d msaa4_col msaa4_mlcol
# load/store
for v in ld_load ld_dc st_dc; do d base $v; done
d depth_priv nocolor
d depth_priv depth_dstore
d depth_priv depth_dload

# focused BO diffs for the key TBDR structures (tiling ctx / attachment / FF-state)
foc() { # foc REF VAR VA
  python3 bodiff.py "caps/$1" "caps/$2" --va $3 --maxlen 0x1000 2>/dev/null | grep '[+]0x0' \
    >> "analysis/focus_$2.txt" || true
}
for v in rt96 rt128 rt256 fmt_r8 fmt_rgba32f mrt2 mrt4 msaa2 msaa4; do
  : > analysis/focus_$v.txt
  for va in 0x68000 0x58000 0x10000110000 0x10000120000; do foc base $v $va; done
done

# pointer graphs for structurally interesting captures
for v in base msaa4 mrt4 depth_priv nocolor; do
  python3 bograph.py caps/$v > analysis/graph_$v.txt 2>&1 || true
  python3 dumpscan.py caps/$v --list > analysis/list_$v.txt 2>&1 || true
done

# curated hexdumps of key control BOs (trimmed text)
mkdir -p hex
keep_bo() { # keep_bo CAP VA OUT
  f=$(ls caps/$1/bo_sigusr1_*_va$2_*.hex 2>/dev/null | head -1)
  [ -n "$f" ] && head -260 "$f" > "hex/$3.hex" 2>/dev/null || true
}
keep_bo base       68000 base_68000
keep_bo base       10000110000 base_attach
keep_bo base       58000 base_58000
keep_bo rt128      68000 rt128_68000
keep_bo rt256      68000 rt256_68000
keep_bo msaa4      68000 msaa4_68000
keep_bo msaa4      10000110000 msaa4_attach
keep_bo msaa4      58000 msaa4_58000
keep_bo msaa4_sp   10000110000 msaa4sp_attach
keep_bo msaa4_sp   68000 msaa4sp_68000
keep_bo mrt4       68000 mrt4_68000
keep_bo mrt4       10000110000 mrt4_attach
keep_bo depth_priv 10000110000 depth_attach
keep_bo depth_ml   10000110000 depthml_attach
keep_bo depth_priv 68000 depth_68000
keep_bo nocolor    10000110000 nocolor_attach
keep_bo nocolor    68000 nocolor_68000
keep_bo fmt_rgba32f 68000 fmt32f_68000
keep_bo fmt_rgba32f 10000110000 fmt32f_attach

# selector histogram sanity (BO count draw)
{ echo "== base =="; grep -cE '^CALL' caps/base.trace; \
  grep -oE 'sel=[0-9]+' caps/base.trace | sort | uniq -c | sort -rn; } > analysis/selhist.txt 2>&1 || true

echo "=== done ==="
ls analysis | wc -l
ls hex | wc -l
