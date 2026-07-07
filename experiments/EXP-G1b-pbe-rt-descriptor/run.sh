#!/bin/sh
# EXP-G1b driver — runs on the A18 device under ~/cleanroom_work/exp_g1b.
# Builds the storage-image compute harness (svar), the render-target draw harness (rtvar),
# and the iotrace interposer; captures the registered GPU BOs for a change-one-parameter
# matrix; curates + byte-diffs the Tier-2 argument-buffer descriptor (storage image) and
# the 3D attachment descriptor (render target, gpu_va 0x10000110000). Text + curated hex only.
# CLEAN-ROOM: DATA-TRACE + OWN-SHADER.
set -e
cd "$(dirname "$0")"

echo "=== build (arm64e — macOS 26 needs interposer+process arch to match) ==="
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o svar  svar.m
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o rtvar rtvar.m
echo built

DYL=./iotrace.dylib
export IOTRACE_MAX_MAP=0x2000     # attachment chain < 0x900; arg-buf descriptor < 0x1600
rm -rf caps raw analysis; mkdir -p caps raw analysis

obuf_of(){ grep -E '^VA obuf' "$1" | sed -E 's/.*= (0x[0-9a-f]+).*/\1/' | head -1; }
rtbuf_of(){ grep -E '^VA rtBuf0' "$1" | sed -E 's/.*= (0x[0-9a-f]+).*/\1/' | head -1; }

# ---------- storage-image (svar) ----------
srun(){  # srun LABEL -- <svar args...>
  label="$1"; shift; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" DYLD_INSERT_LIBRARIES=$DYL \
    ./svar "$@" --dump > "caps/$label.out" 2>&1 || true
  ob=$(obuf_of "caps/$label.out")
  st=$(grep -E '^SUBMIT' "caps/$label.out" | head -1)
  echo "  [$label] obuf=$ob $st"
  [ -n "$ob" ] && python3 argx2.py "$d" --obuf "$ob" --curate "raw/$label.hex" >/dev/null 2>&1 || true
  [ -n "$ob" ] && python3 argx2.py "$d" --obuf "$ob" --words > "analysis/$label.txt" 2>&1 || true
}

echo "=== STORAGE-IMAGE matrix (svar) ==="
srun s_sample_rgba8  -- --fmt rgba8   --access sample
srun s_read_rgba8    -- --fmt rgba8   --access read
srun s_write_rgba8   -- --fmt rgba8   --access write
srun s_rw_rgba8      -- --fmt rgba8   --access readwrite
srun s_write_r32f    -- --fmt r32f    --access write
srun s_write_rgba32f -- --fmt rgba32f --access write
srun s_write_r32u    -- --fmt r32u    --access write
srun s_write_rg16f   -- --fmt rg16f   --access write
srun s_write_r16f    -- --fmt r16f    --access write
srun s_write_rgba16f -- --fmt rgba16f --access write
srun s_write_256     -- --fmt rgba8   --access write --w 256 --h 256
srun s_write_33x17   -- --fmt rgba8   --access write --w 33  --h 17
srun s_write_129x63  -- --fmt rgba8   --access write --w 129 --h 63
srun s_write_bb_r32f -- --fmt r32f    --access write --bb
srun s_sample_bb_r32f -- --fmt r32f   --access sample --bb

# ---------- render-target attachment (rtvar) ----------
rrun(){  # rrun LABEL -- <rtvar args...>
  label="$1"; shift; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" DYLD_INSERT_LIBRARIES=$DYL \
    ./rtvar "$@" --dump > "caps/$label.out" 2>&1 || true
  rb=$(rtbuf_of "caps/$label.out")
  st=$(grep -E '^SUBMIT|^PIXEL' "caps/$label.out" | head -1)
  echo "  [$label] rtBuf0=$rb $st"
  python3 attloc.py "$d" --curate "raw/$label.hex" >/dev/null 2>&1 || true
  python3 attloc.py "$d" --n 0x900 > "analysis/$label.txt" 2>&1 || true
  [ -n "$rb" ] && python3 attloc.py "$d" --find "$rb" > "analysis/find_$label.txt" 2>&1 || true
}

echo "=== RENDER-TARGET matrix (rtvar) ==="
rrun rt_base      --                              # bgra8 64x64 clear/store, buffer-backed
rrun rt_priv      -- --priv                       # Private surface (VA-less) contrast
rrun rt_128       -- --w 128 --h 128
rrun rt_256       -- --w 256 --h 256
rrun rt_33x17     -- --w 33  --h 17               # odd dims -> width/height/stride fields
rrun rt_128x64    -- --w 128 --h 64               # asymmetric -> separate W from H
rrun rt_65x65     -- --w 65  --h 65
rrun fmt_rgba8    -- --fmt rgba8
rrun fmt_r8       -- --fmt r8
rrun fmt_r32f     -- --fmt r32f
rrun fmt_rgba16f  -- --fmt rgba16f
rrun fmt_rgba32f  -- --fmt rgba32f
rrun fmt_rgb10a2  -- --fmt rgb10a2
rrun ld_load      -- --load load
rrun ld_dc        -- --load dontcare
rrun st_dc        -- --store dontcare
rrun mrt2         -- --mrt 2
rrun mrt3         -- --mrt 3
rrun mrt4         -- --mrt 4
rrun msaa2        -- --samples 2
rrun msaa4        -- --samples 4

# ---------- diffs ----------
echo "=== DIFFS ==="
DF(){ echo "#### $1 : $2 vs $3"; python3 bodiff.py "raw/$2.hex" "raw/$3.hex"; echo; }
{
echo "==================== STORAGE-IMAGE DIFFS ===================="
DF "write vs sample (rgba8)"      s_sample_rgba8 s_write_rgba8
DF "read vs sample (rgba8)"       s_sample_rgba8 s_read_rgba8
DF "readwrite vs write (rgba8)"   s_write_rgba8  s_rw_rgba8
DF "write r32f vs rgba8"          s_write_rgba8  s_write_r32f
DF "write rgba32f vs rgba8"       s_write_rgba8  s_write_rgba32f
DF "write r32u vs rgba8"          s_write_rgba8  s_write_r32u
DF "write rg16f vs rgba8"         s_write_rgba8  s_write_rg16f
DF "write r16f vs rgba8"          s_write_rgba8  s_write_r16f
DF "write rgba16f vs rgba8"       s_write_rgba8  s_write_rgba16f
DF "write 256 vs 64"              s_write_rgba8  s_write_256
DF "write 33x17 vs 64"            s_write_rgba8  s_write_33x17
DF "write 129x63 vs 64"           s_write_rgba8  s_write_129x63
DF "write bb vs write r32f"       s_write_r32f   s_write_bb_r32f
echo "==================== RENDER-TARGET DIFFS ===================="
DF "rt 128 vs base"               rt_base rt_128
DF "rt 256 vs base"               rt_base rt_256
DF "rt 33x17 vs base"             rt_base rt_33x17
DF "rt 128x64 vs base"            rt_base rt_128x64
DF "rt 65x65 vs base"             rt_base rt_65x65
DF "rt priv vs base"              rt_base rt_priv
DF "fmt rgba8 vs bgra8(base)"     rt_base fmt_rgba8
DF "fmt r8 vs base"               rt_base fmt_r8
DF "fmt r32f vs base"             rt_base fmt_r32f
DF "fmt rgba16f vs base"          rt_base fmt_rgba16f
DF "fmt rgba32f vs base"          rt_base fmt_rgba32f
DF "fmt rgb10a2 vs base"          rt_base fmt_rgb10a2
DF "load=load vs clear(base)"     rt_base ld_load
DF "load=dontcare vs clear"       rt_base ld_dc
DF "store=dontcare vs store"      rt_base st_dc
DF "mrt2 vs base"                 rt_base mrt2
DF "mrt3 vs mrt2"                 mrt2    mrt3
DF "mrt4 vs mrt2"                 mrt2    mrt4
DF "msaa2 vs base"                rt_base msaa2
DF "msaa4 vs msaa2"               msaa2   msaa4
} > analysis/DIFFS.txt 2>&1
echo "wrote analysis/DIFFS.txt"
echo "=== surface-VA correlation (rt_base) ==="; cat analysis/find_rt_base.txt 2>/dev/null | head
echo DONE
