#!/bin/sh
# EXP-O2B driver — runs on the A18 device under ~/cleanroom_work/exp_o2b.
# Builds the parametric resource-feature harness (rvar.m) + the bindless sampler-heap harness
# (heaparg.m) + the read-only iotrace interposer, captures registered GPU BOs for a matrix of
# one-Metal-parameter-changed compute dispatches, and extracts/diffs the appended descriptor
# blocks (auto-locating the Tier-2 arg buffer via argx.py). Pulls back text only.
# Clean-room: DATA-TRACE + OWN-SHADER + HW-PROBE. No Apple binary disassembled.
set -u
cd "$(dirname "$0")"

echo "=== build ==="
clang -dynamiclib -o iotrace.dylib iotrace.c -framework IOKit -framework CoreFoundation
clang -fobjc-arc -framework Metal -framework Foundation -o rvar    rvar.m
clang -fobjc-arc -framework Metal -framework Foundation -o heaparg heaparg.m
clang -fobjc-arc -framework Metal -framework Foundation -o probe   probe.m
echo built

DYL=./iotrace.dylib
rm -rf caps; mkdir -p caps analysis raw

cap() {  # cap LABEL -- <rvar args...>
  label="$1"; shift; [ "$1" = "--" ] && shift
  d="caps/$label"; rm -rf "$d"; mkdir -p "$d"
  IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./rvar "$@" --dump > "caps/$label.out" 2>&1 || true
  ok=$(grep -c 'SUBMIT status=4' "caps/$label.out" 2>/dev/null || echo 0)
  echo "  cap $label ok=$ok : $*"
  grep -E '^(CB_ERROR|.*_FAIL)' "caps/$label.out" 2>/dev/null || true
}
tex() { python3 argx.py "caps/$1" --tlen 0x20 --slen 0x10 | sed -n '/TEXDESC/,$p'; }

# ========== CAPABILITY BASELINE ==========
./probe > raw/probe.txt 2>&1

# ========== (2) USAGE / RENDER-TARGET (PBE) — small (uncompressed) + large (compressed) ==========
for u in read readrt readwrite readpix; do
  cap us4_$u  -- --fmt rgba8unorm --usage $u --heap none --w 4   --h 4
  cap us256_$u -- --fmt rgba8unorm --usage $u --heap none --w 256 --h 256
done

# ========== (1) SPARSE / PLACEMENT HEAP ==========
cap std256    -- --fmt rgba8unorm --usage read      --heap none      --w 256 --h 256
cap std256_rw -- --fmt rgba8unorm --usage readwrite --heap none      --w 256 --h 256
cap plc256    -- --fmt rgba8unorm --usage read      --heap placement --w 256 --h 256
cap sp256     -- --fmt rgba8unorm --usage read      --heap sparse    --w 256 --h 256
cap sp256_map -- --fmt rgba8unorm --usage read      --heap sparse    --w 256 --h 256 --map
cap sp256_rw  -- --fmt rgba8unorm --usage readwrite --heap sparse    --w 256 --h 256
cap sp256_r32f -- --fmt r32float  --usage read      --heap sparse    --w 256 --h 256
cap std256_r32f -- --fmt r32float --usage read      --heap none      --w 256 --h 256

# ========== (3) 32-BIT FLOAT FILTERING ==========
cap ff_r32_near -- --fmt r32float --usage read --heap none --storage shared --grad --filter nearest --w 2 --h 2
cap ff_r32_lin  -- --fmt r32float --usage read --heap none --storage shared --grad --filter linear  --w 2 --h 2

echo "=== extract descriptors (auto-located arg buffer) ==="
for d in caps/*/ ; do l=$(basename "$d")
  python3 argx.py "$d" --words --tlen 0x20 --slen 0x10 > "raw/desc_$l.txt" 2>&1 || true
  python3 argx.py "$d"          --tlen 0x20 --slen 0x10 > "analysis/hex_$l.txt" 2>&1 || true
done

echo "=== diffs ==="
dcmp(){ echo "### $2 vs $1"; diff "analysis/hex_$1.txt" "analysis/hex_$2.txt" || true; }
{
  echo "===== USAGE 4x4 (base us4_read) — is RenderTarget/PBE a descriptor bit? ====="
  for v in readrt readwrite readpix; do dcmp us4_read us4_$v; done
  echo "===== USAGE 256 (base us256_read) — usage vs compression ====="
  for v in readrt readwrite readpix; do dcmp us256_read us256_$v; done
} > analysis/diff_usage.txt 2>&1
{
  echo "===== SPARSE (base std256) — sparse-tier flag ====="
  dcmp std256 sp256
  echo "===== SPARSE map vs nomap — is tile residency in the descriptor? ====="
  dcmp sp256 sp256_map
  echo "===== SPARSE rw vs std rw (isolate sparse flag w/o compression) ====="
  dcmp std256_rw sp256_rw
  echo "===== SPARSE r32float vs std r32float ====="
  dcmp std256_r32f sp256_r32f
  echo "===== PLACEMENT heap vs standalone (base std256) ====="
  dcmp std256 plc256
} > analysis/diff_sparse_heap.txt 2>&1
{
  echo "===== FLOAT FILTER r32float nearest vs linear (texture + sampler desc) ====="
  dcmp ff_r32_near ff_r32_lin
  echo "--- sampled readback (nearest quantized vs linear interpolated) ---"
  grep '^SAMPLES' caps/ff_r32_near.out; grep '^SAMPLES' caps/ff_r32_lin.out
} > analysis/diff_floatfilter.txt 2>&1

echo "=== (4) bindless sampler-heap layout ==="
for K in 4 8 64; do ./heaparg --k $K > raw/heaparg_k$K.txt 2>&1; done

# curated raw hex of the key descriptors
{
  echo "# EXP-O2B key texture descriptors (32B, at argBO+0x14c0). word convention: EXP-0015."
  for l in us4_read us256_read us256_readwrite std256 std256_rw plc256 sp256 sp256_map sp256_rw sp256_r32f std256_r32f ff_r32_near ff_r32_lin; do
    echo "== $l =="; tex $l | head -5
  done
} > raw/key_descriptors.txt 2>&1

echo "=== done. see analysis/ raw/ ==="
