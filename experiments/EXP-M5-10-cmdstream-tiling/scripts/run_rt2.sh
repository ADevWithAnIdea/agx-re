#!/bin/sh
# run_rt2.sh — unpruned second pass: sample positions, PBE/storage-image, tiling pattern,
# USC bind grammar, indirect/mesh/tess. Keep ALL BOs (needed to locate tables).
cd ~/cleanroom_work/EXP-M5-10
IT=../tools/iotrace
: >progress_rt2.log
for S in usc indir; do
  clang -fobjc-arc -O0 -arch arm64e -framework Metal -framework Foundation scripts/$S.m -o $S 2>build_$S.err
  [ -x $S ] || { echo "BUILD_FAIL $S"; cat build_$S.err; } >>progress_rt2.log
done
echo "BUILD done" >>progress_rt2.log
runbin(){ BIN="$1";NAME="$2";shift 2; rm -rf u_$NAME; mkdir -p u_$NAME
  IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR=u_$NAME DYLD_INSERT_LIBRARIES=$IT/iotrace.dylib \
    ./$BIN "$@" --dump >ru_$NAME.txt 2>&1
  # drop only the very large BOs to save space
  find u_$NAME -type f -size +2000k -delete 2>/dev/null
  echo "$NAME $(grep -oE 'STATUS=[0-9]+|COMPILE_FAIL|PIPELINE_FAIL|UNKNOWN' ru_$NAME.txt | head -1)" >>progress_rt2.log
}
# ---- sample positions (need 0x100000e* BOs) ----
runbin rtvar msaa4b --msaa 4
runbin rtvar msaa4sp --msaa 4 --samplepos
runbin rtvar msaa2b --msaa 2
runbin rtvar msaa2sp --msaa 2 --samplepos
# ---- storage-image / PBE descriptor ----
runbin imgwrite iw_w --mode write --fmt rgba8
runbin imgwrite iw_w256 --mode write --fmt rgba8 --w 256 --h 128
runbin imgwrite iw_wr32 --mode write --fmt r32u --w 256 --h 128
runbin imgwrite iw_rw --mode readwrite --fmt rgba8
runbin imgwrite iw_r --mode read --fmt rgba8
# ---- tiling pattern (writable r32u backing) ----
runbin texpat tp192 --fmt r32u --w 192 --h 192 --write
runbin texpat tp128 --fmt r32u --w 128 --h 128 --write
# ---- USC bind grammar (compute) ----
runbin usc uc_t1 --compute --tex 1 --samp 1 --buf 1
runbin usc uc_t3 --compute --tex 3 --samp 1 --buf 1
runbin usc uc_s3 --compute --tex 1 --samp 3 --buf 1
runbin usc uc_b4 --compute --tex 1 --samp 1 --buf 4
# ---- USC bind grammar (graphics fragment) ----
runbin usc ug_t1 --tex 1 --samp 1 --buf 1
runbin usc ug_t3 --tex 3 --samp 1 --buf 1
runbin usc ug_b4 --tex 1 --samp 1 --buf 4
# ---- indirect / mesh / tessellation ----
runbin indir in_disp --mode dispatch
runbin indir in_idisp --mode idispatch
runbin indir in_draw --mode idraw
runbin indir in_drawidx --mode idrawidx
runbin indir in_mesh --mode mesh
runbin indir in_tess --mode tess
echo "RT2_DONE" >>progress_rt2.log
