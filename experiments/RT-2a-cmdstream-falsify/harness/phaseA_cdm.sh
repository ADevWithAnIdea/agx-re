#!/bin/sh
# RT-2a Phase A — falsify CDM compute launch descriptor (0x100000b0000, 0x2c-byte record).
# Claims under test: shader ptr = shaderVA>>6 @+0x08; grid xyz @+0x10/14/18 (in THREADS);
# threadgroup xyz @+0x1c/20/24; tgmem NOT in this record.
set -e
cd "$(dirname "$0")"
DYL=./iotrace.dylib
CAP=0x2000
rm -rf capsA analysisA; mkdir -p capsA analysisA
run(){ label="$1"; shift; d="capsA/$label"; mkdir -p "$d"
  IOTRACE_MAX_MAP=$CAP IOTRACE_LOG="capsA/$label.trace" IOTRACE_DUMP_DIR="$d" \
    DYLD_INSERT_LIBRARIES=$DYL ./cvar "$@" --dump > "capsA/$label.out" 2>&1 || true
  echo "  [$label] $(grep -E '^CONFIG' capsA/$label.out | head -1)"
}
# baseline + determinism
run base   --kernel add3 --gx 64 --tgx 32
run base2  --kernel add3 --gx 64 --tgx 32
# --- grid-field isolation (non-cube, distinct primes) ---
run g357   --kernel add3 --gx 3 --gy 5 --gz 7 --tgx 1 --tgy 1 --tgz 1
run gx65   --kernel add3 --gx 65 --tgx 1               # grid.x delta vs 64
run gxhuge --kernel add3 --gx 0x123456 --tgx 2         # huge grid.x = 0x123456
# --- THREADS-vs-THREADGROUPS falsification: two encodings, SAME total threads ---
# dispatchThreads(12,5,7) tg(4,5,7)   == 12x5x7 threads
run tds_1257 --kernel add3 --gx 12 --gy 5 --gz 7 --tgx 4 --tgy 5 --tgz 7
# dispatchThreadgroups(3,1,1) tg(4,5,7) == 12x5x7 threads (identical if grid=THREADS)
run grp_1257 --kernel add3 --groups --gx 3 --gy 1 --gz 1 --tgx 4 --tgy 5 --tgz 7
# --- threadgroup-size isolation (distinct primes) ---
run tg_235  --kernel add3 --groups --gx 1 --gy 1 --gz 1 --tgx 2 --tgy 3 --tgz 5
run tg_357  --kernel add3 --groups --gx 1 --gy 1 --gz 1 --tgx 3 --tgy 5 --tgz 7
# --- 1D vs 3D dispatch shape ---
run d1d --kernel add3 --gx 256 --tgx 64
run d3d --kernel add3 --gx 8 --gy 8 --gz 8 --tgx 8 --tgy 8 --tgz 8
# --- threadgroup-memory sizes (claim: NOT in CDM record) ---
run tgm256   --kernel tgmem --gx 64 --tgx 64 --tgmem 256
run tgm4096  --kernel tgmem --gx 64 --tgx 64 --tgmem 4096
run tgm32768 --kernel tgmem --gx 64 --tgx 64 --tgmem 32768
# --- shader-pointer tracking (pad shifts the shader VA) ---
run pad0 --kernel add3 --gx 64 --tgx 32 --pad 0
run pad3 --kernel add3 --gx 64 --tgx 32 --pad 3
# --- two distinct pipelines in one submit (two CDM records) ---
run two  --kernel add3 --k2 mul1 --gx 64 --tgx 32
# --- config-word / register tier ---
run heavy --kernel heavy --gx 64 --tgx 32

echo "=== diffs (CDM BO 0x100000b0000) ==="
D(){ python3 bodiff.py "capsA/$1" "capsA/$2" --va 0x100000b0000 --maxlen 0x80 > "analysisA/$3.txt" 2>&1 || true; }
D base base2 det
D base g357 grid357
D base gx65 gridx65
D base gxhuge gridxhuge
D tds_1257 grp_1257 threads_vs_groups
D tg_235 tg_357 tgsize
D d1d d3d shape
D base tgm256  tgmem256
D base tgm32768 tgmem32768
D tgm256 tgm32768 tgmem_delta
D base heavy configword
D pad0 pad3 shaderptr_pad
D base two twopipe
# also diff the shader BO 0x10000090000 for tgmem (claim: tgmem lives HERE not CDM)
python3 bodiff.py capsA/tgm256 capsA/tgm32768 --va 0x10000090000 --maxlen 0x80 > analysisA/tgmem_shaderbo.txt 2>&1 || true

echo "=== curated hex of CDM record ==="
mkdir -p hexA
kb(){ f=$(ls capsA/$1/*va$2_*.hex 2>/dev/null|head -1); [ -n "$f" ] && head -20 "$f" > "hexA/$3.hex" || echo "no $1 $2"; }
kb base 100000b0000 base_cdm
kb g357 100000b0000 g357_cdm
kb tds_1257 100000b0000 tds_cdm
kb grp_1257 100000b0000 grp_cdm
kb gxhuge 100000b0000 gxhuge_cdm
kb two 100000b0000 two_cdm
kb tgm32768 10000090000 tgm32768_shaderbo
kb base 10000090000 base_shaderbo
echo "=== VA lines ==="
grep -h '^VA ' capsA/base.out capsA/two.out capsA/pad0.out capsA/pad3.out 2>/dev/null
grep -h 'PSO ' capsA/*.out | sort -u
echo DONE_PHASE_A