#!/bin/sh
# RT-4 red-team driver — runs on the A18 device under ~/cleanroom_work/rt4.
# RED-TEAM falsification of the EXP-0021 TBDR pipeline facts (docs/pipeline/README.md).
# Adversarial: extreme/large/asymmetric RT sizes, all formats, rgba32f+4xMSAA, 1..8
# attachments + mixed formats, 8x MSAA rejection, memoryless color(1x & MSAA)+depth,
# load/store combos, and the negatives (programmable sample positions, depth store).
# Method: change-one-Metal-parameter, capture registered GPU BOs under iotrace, byte-diff.
# CLEAN-ROOM: DATA-TRACE + OWN-SHADER.
set -e
cd "$(dirname "$0")"

echo "=== build (arm64e) ==="
clang -arch arm64e -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -arch arm64e -fobjc-arc -framework Metal -framework Foundation -o tvar4 tvar4.m
echo "built"

DYL=./iotrace.dylib
export IOTRACE_MAX_MAP=0x10000
rm -rf caps analysis hex; mkdir -p caps analysis hex

run() {  # run LABEL -- <tvar4 args...>
  label="$1"; shift; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_LOG="caps/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./tvar4 "$@" --dump > "caps/$label.stdout" 2>&1 || true
  st=$(grep -E '^(PIPELINE_FAIL|SUBMIT.*done)' "caps/$label.stdout" | head -1 || true)
  echo "  [$label] ${st:-NORUN}"
}

# ================= Phase 0: baseline / determinism / capability probe =================
run probe -- --probe
run base   --
run base2  --

# ================= Phase 1: tile 32x32 FIXED — adversarial RT sizes (bgra8) =================
# degenerate / boundary
run rt1     -- --w 1    --h 1
run rt31    -- --w 31   --h 31
run rt32    -- --w 32   --h 32
run rt33    -- --w 33   --h 33
run rt63    -- --w 63   --h 63
run rt65    -- --w 65   --h 65
# large POT
run rt512   -- --w 512  --h 512
run rt1024  -- --w 1024 --h 1024
run rt2048  -- --w 2048 --h 2048
# large NPOT / prime-ish
run rt1000  -- --w 1000 --h 1000
run rt777   -- --w 777  --h 777
# extreme asymmetric (separate X/Y tile fields hard)
run rt2048x32 -- --w 2048 --h 32
run rt32x2048 -- --w 32   --h 2048
run rt96x1000 -- --w 96   --h 1000
run rt1000x96 -- --w 1000 --h 96

# ---- Phase 1b: pixel format sweep (fixed 64x64) — does tile grid EVER change with bpp? ----
run fmt_rgba8   -- --fmt rgba8
run fmt_r8      -- --fmt r8
run fmt_r32f    -- --fmt r32f
run fmt_rgb10a2 -- --fmt rgb10a2
run fmt_rgba16f -- --fmt rgba16f
run fmt_rgba32f -- --fmt rgba32f
# same format at a large size (does high-bpp+large ever shrink?)
run fmt32f_512  -- --fmt rgba32f --w 512 --h 512

# ---- Phase 1c: rgba32f + 4x MSAA (imageblock 64 KiB > 32 KiB tile SRAM) ----
run m4_32f      -- --samples 4 --fmt rgba32f
run m4_32f_128  -- --samples 4 --fmt rgba32f --w 128 --h 128
run m4_16f      -- --samples 4 --fmt rgba16f
# depth + color combined (does depth presence perturb tile grid?)
run dc          -- --depth
run dc_512      -- --depth --w 512 --h 512

# ================= Phase 2: imageblock budget — 1..8 attachments + mixed formats =========
run mrt1  -- --mrt 1
run mrt2  -- --mrt 2
run mrt3  -- --mrt 3
run mrt4  -- --mrt 4
run mrt5  -- --mrt 5
run mrt6  -- --mrt 6
run mrt7  -- --mrt 7
run mrt8  -- --mrt 8
# format scaling per attachment
run mrt2_32f -- --mrt 2 --fmt rgba32f
run mrt4_32f -- --mrt 4 --fmt rgba32f
run mrt8_32f -- --mrt 8 --fmt rgba32f
run mrt4_16f -- --mrt 4 --fmt rgba16f
# mixed per-attachment formats (does per-attachment stride track each format's bpp?)
run mrt4_mix -- --mrt 4 --mrtfmt bgra8,rgba32f,r8,rgba16f
run mrt8_mix -- --mrt 8 --mrtfmt bgra8,rgba32f,r8,rgba16f,bgra8,rgba32f,r8,rgba16f
run mrt2_mixA -- --mrt 2 --mrtfmt bgra8,rgba32f
run mrt2_mixB -- --mrt 2 --mrtfmt rgba32f,bgra8

# ================= Phase 3: MSAA sample count + 8x rejection + relocation ================
run msaa2       -- --samples 2
run msaa4       -- --samples 4
run msaa8       -- --samples 8     # expect PIPELINE_FAIL (rejected)
run msaa16      -- --samples 16    # expect PIPELINE_FAIL
run msaa4_r8    -- --samples 4 --fmt r8

# ================= Phase 4: memoryless — color(1x & MSAA) + depth =======================
run mlcol1x     -- --mlcolor                    # single-sample memoryless color (NEW)
run mlcol1x_32f -- --mlcolor --fmt rgba32f
run msaa4_col   -- --samples 4                  # Private MSAA color baseline
run msaa4_mlcol -- --samples 4 --mlcolor        # Memoryless MSAA color
run depth_priv  -- --depth                      # Private depth baseline
run depth_ml    -- --depth --mldepth            # Memoryless depth
run dc_mlcol    -- --depth --mlcolor            # memoryless color WITH depth

# ================= Phase 5: load/store combos + store-program 0x6f ======================
run ld_load        -- --load load
run ld_dc          -- --load dontcare
run st_dc          -- --store dontcare
run ld_dc_st_dc    -- --load dontcare --store dontcare
run ld_load_st_dc  -- --load load     --store dontcare
run ld_load_st_st  -- --load load     --store store
run nocolor        -- --depth --nocolor
run depth_dstore   -- --depth --dstore store
run depth_dload    -- --depth --dload load

# ================= Phase 6: NEGATIVES — programmable sample positions / depth store =====
run msaa2_sp    -- --samples 2 --sampos
run msaa4_sp    -- --samples 4 --sampos

echo "=== on-device diffs ==="
d() { python3 bodiff.py "caps/$1" "caps/$2" --maxlen 0x2000 > "analysis/diff_$2.txt" 2>&1 || true; }

d base base2
for v in rt1 rt31 rt32 rt33 rt63 rt65 rt512 rt1024 rt2048 rt1000 rt777 \
         rt2048x32 rt32x2048 rt96x1000 rt1000x96; do d base $v; done
for v in fmt_rgba8 fmt_r8 fmt_r32f fmt_rgb10a2 fmt_rgba16f fmt_rgba32f; do d base $v; done
for v in mrt2 mrt3 mrt4 mrt5 mrt6 mrt7 mrt8 mrt2_32f mrt4_32f mrt8_32f mrt4_16f \
         mrt4_mix mrt8_mix mrt2_mixA mrt2_mixB; do d base $v; done
for v in msaa2 msaa4 msaa4_r8; do d base $v; done
d msaa2 msaa2_sp
d msaa4 msaa4_sp
d msaa4_col msaa4_mlcol
d base mlcol1x
d depth_priv depth_ml
d depth_priv nocolor
d depth_priv depth_dstore
d depth_priv depth_dload
d depth_priv dc_mlcol
for v in ld_load ld_dc st_dc ld_dc_st_dc ld_load_st_dc ld_load_st_st; do d base $v; done

# focused 0x68000 +0x900 tile-grid line for every size/format run (the core Q1 evidence)
echo "=== tile-grid summary (0x68000 @+0x900) ===" > hex/TILEGRID.txt
tg() { # tg LABEL
  f=$(ls caps/$1/*va68000_*.hex 2>/dev/null | head -1)
  if [ -n "$f" ]; then
    l900=$(grep '^00000900:' "$f" 2>/dev/null)
    printf "%-12s %s\n" "$1" "$l900" >> hex/TILEGRID.txt
  else
    printf "%-12s (no 68000 BO)\n" "$1" >> hex/TILEGRID.txt
  fi
}
for v in base rt1 rt31 rt32 rt33 rt63 rt65 rt512 rt1024 rt2048 rt1000 rt777 \
         rt2048x32 rt32x2048 rt96x1000 rt1000x96 \
         fmt_rgba8 fmt_r8 fmt_r32f fmt_rgb10a2 fmt_rgba16f fmt_rgba32f fmt32f_512 \
         m4_32f m4_32f_128 m4_16f dc dc_512 \
         msaa2 msaa4 mrt2 mrt4 mrt8; do tg $v; done

# curated hexdumps of key control BOs
keep() { # keep LABEL VA OUT   (VA is the hex suffix in the filename, e.g. 68000)
  f=$(ls caps/$1/*va$2_*.hex 2>/dev/null | head -1)
  [ -n "$f" ] && head -300 "$f" > "hex/$3.hex" 2>/dev/null || true
}
keep base       68000        base_68000
keep base       10000110000  base_attach
keep base       58000        base_58000
keep rt2048     68000        rt2048_68000
keep rt2048x32  68000        rt2048x32_68000
keep fmt_rgba32f 68000       fmt32f_68000
keep fmt_rgba32f 10000110000 fmt32f_attach
keep m4_32f     68000        m4_32f_68000
keep m4_32f     10000018200  m4_32f_tilerheap
keep mrt4       10000018200  mrt4_tilerheap
keep mrt8       10000018200  mrt8_tilerheap
keep mrt8_32f   10000018200  mrt8_32f_tilerheap
keep mrt4_mix   10000018200  mrt4_mix_tilerheap
keep mrt8_mix   10000018200  mrt8_mix_tilerheap
keep mrt2_mixA  10000018200  mrt2_mixA_tilerheap
keep mrt2_mixB  10000018200  mrt2_mixB_tilerheap
keep msaa2      10000018200  msaa2_tilerheap
keep msaa4      10000018200  msaa4_tilerheap
keep msaa4      68000        msaa4_68000
keep msaa4_col  10000018200  msaa4_col_tilerheap
keep msaa4_mlcol 10000018200 msaa4_mlcol_tilerheap
keep mlcol1x    10000110000  mlcol1x_attach
keep base       10000110000  base_attach_full
keep depth_priv 10000110000  depth_attach
keep depth_ml   10000110000  depthml_attach
keep depth_priv 10000030000  depth_dsurf
keep depth_ml   10000030000  depthml_dsurf
keep nocolor    68000        nocolor_68000

# list every BO for the structurally interesting captures
for v in base mrt8 mrt8_mix msaa4 msaa8 mlcol1x depth_priv nocolor m4_32f; do
  python3 dumpscan.py caps/$v --list > analysis/list_$v.txt 2>&1 || true
done

# pipeline-fail summary (8x/16x MSAA rejection + any budget rejects)
echo "=== PIPELINE_FAIL / status summary ===" > analysis/status_summary.txt
for f in caps/*.stdout; do
  lbl=$(basename "$f" .stdout)
  pf=$(grep -E 'PIPELINE_FAIL|SUBMIT.*done status' "$f" | head -1)
  printf "%-14s %s\n" "$lbl" "$pf" >> analysis/status_summary.txt
done
# capability probe
grep -E '^PROBE' caps/probe.stdout >> analysis/status_summary.txt 2>/dev/null || true

echo "=== done ==="
echo "TILEGRID:"; cat hex/TILEGRID.txt
echo "STATUS:"; cat analysis/status_summary.txt
ls analysis | wc -l
ls hex | wc -l
