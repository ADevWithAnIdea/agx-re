#!/bin/sh
# run_rt.sh — RT attachment/MSAA/memoryless/sample-pos/occlusion + storage-image + tiling probes.
cd ~/cleanroom_work/EXP-M5-10
IT=../tools/iotrace
: >progress_rt.log
for S in rtvar imgwrite texpat; do
  clang -fobjc-arc -O0 -arch arm64e -framework Metal -framework Foundation scripts/$S.m -o $S 2>build_$S.err
  [ -x $S ] || { echo "BUILD_FAIL $S" >>progress_rt.log; cat build_$S.err >>progress_rt.log; }
done
echo "BUILD done" >>progress_rt.log
# keep attachment/tiler/state BOs, drop bulk code/heap
KEEP="va58000_ va68000_ va18000_ va28000_ va38000_ va48000_ va10000018 va10000100 va10000108 va10000110 va10000118 va10000120 va10000128 va10000130 va10000138"
runbin(){ BIN="$1";NAME="$2";shift 2; rm -rf m_$NAME; mkdir -p m_$NAME
  IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR=m_$NAME DYLD_INSERT_LIBRARIES=$IT/iotrace.dylib \
    ./$BIN "$@" --dump >r_$NAME.txt 2>&1
  for f in m_$NAME/bo_*; do b=$(basename "$f"); k=0; for K in $KEEP; do case "$b" in *$K*) k=1;; esac; done; [ $k -eq 0 ] && rm -f "$f"; done
  echo "$NAME $(grep -oE 'STATUS=[0-9]+|OCCL[^ ]* [0-9]+|allocatedSize=0x[0-9a-f]+|COMPILE_FAIL|PIPELINE_FAIL' r_$NAME.txt | tr '\n' ' ')" >>progress_rt.log
}
# ---- attachment format-word sweep (single RT) ----
for F in bgra8 rgba8 rgba8i rgba16f rgba32f r32f r8 rg8 rgb10a2 r16u r32u rg11b10; do runbin rtvar rt_$F --fmt $F; done
# ---- MRT / MSAA / memoryless / load-store / samplepos ----
runbin rtvar rt_mrt2 --mrt 2
runbin rtvar rt_mrt4 --mrt 4
runbin rtvar rt_msaa2 --msaa 2
runbin rtvar rt_msaa4 --msaa 4
runbin rtvar rt_msaa2_sp --msaa 2 --samplepos
runbin rtvar rt_msaa4_sp --msaa 4 --samplepos
runbin rtvar rt_msaa4_res --msaa 4 --store 2
runbin rtvar rt_memless --memoryless
runbin rtvar rt_load_dc --load 0
runbin rtvar rt_load_ld --load 1
runbin rtvar rt_store_dc --store 0
runbin rtvar rt_w128h64 --w 128 --h 64
runbin rtvar rt_w1920 --w 1920 --h 1080
# ---- occlusion query ----
runbin rtvar rt_occl_b --occl 0
runbin rtvar rt_occl_c --occl 1
runbin rtvar rt_occl_c64 --occl 1 --occloff 64
runbin rtvar rt_occl_c256 --occl 1 --occloff 256
# ---- storage-image (PBE) descriptor ----
runbin imgwrite iw_w --mode write --fmt rgba8
runbin imgwrite iw_w256 --mode write --fmt rgba8 --w 256 --h 128
runbin imgwrite iw_w_r32 --mode write --fmt r32u --w 256 --h 128
runbin imgwrite iw_rw --mode readwrite --fmt rgba8
runbin imgwrite iw_r --mode read --fmt rgba8
runbin imgwrite iw_w_bgra --mode write --fmt bgra8
echo "RT_SWEEP_DONE" >>progress_rt.log
# ---- tiling: allocatedSize matrix (no dump needed) ----
{
echo "=== texpat allocatedSize matrix ==="
for F in r8 r16u r32u rgba8 rgba16f rgba32f; do
  for D in 64 96 128 192 256 300 384 512; do
    ./texpat --fmt $F --w $D --h $D 2>&1 | grep -oE 'fmt=.*allocatedSize=0x[0-9a-f]+'
  done
done
echo "=== compression-eligible (nowrite) allocatedSize (aux included) ==="
for F in rgba8 rgba16f rgba32f; do
  for D in 8 15 16 17 64 256; do
    ./texpat --fmt $F --w $D --h $D --nowrite 2>&1 | grep -oE 'fmt=.*allocatedSize=0x[0-9a-f]+'
  done
done
} >tex_sizes.txt 2>&1
echo "TEXSIZE_DONE" >>progress_rt.log
# ---- tiling: pattern write for Morton inference (non-pow2 192 r32u) ----
runbin texpat tp_192 --fmt r32u --w 192 --h 192 --write
runbin texpat tp_128 --fmt r32u --w 128 --h 128 --write
echo "ALL_RT_DONE" >>progress_rt.log
