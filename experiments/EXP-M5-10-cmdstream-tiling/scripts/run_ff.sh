#!/bin/sh
# run_ff.sh — full fixed-function 0x58000 pool sweep on M5. Launched detached; poll progress.log.
cd ~/cleanroom_work/EXP-M5-10
IT=../tools/iotrace
clang -fobjc-arc -O0 -arch arm64e -framework Metal -framework Foundation scripts/ffstate.m -o ffstate 2>build_ff.err
if [ ! -x ffstate ]; then echo "BUILD_FAIL" >progress.log; cat build_ff.err >>progress.log; exit 1; fi
echo "BUILD_OK" >progress.log
KEEP="va58000_ va18000_ va68000_ va10000000000_ va10000108000_ va10000118000_ va10000128000_"
run(){ NAME="$1"; shift; rm -rf m_$NAME; mkdir -p m_$NAME
  IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR=m_$NAME DYLD_INSERT_LIBRARIES=$IT/iotrace.dylib \
    ./ffstate "$@" --dump >r_$NAME.txt 2>&1
  # prune to BOs of interest
  for f in m_$NAME/bo_*; do b=$(basename "$f"); k=0; for K in $KEEP; do case "$b" in *$K*) k=1;; esac; done; [ $k -eq 0 ] && rm -f "$f"; done
  echo "$NAME $(grep -oE 'STATUS=[0-9]+|COMPILE_FAIL|PIPELINE_FAIL' r_$NAME.txt|head -1)" >>progress.log
}
run base
# --- depth ---
run d_on --depth
for n in 0 1 2 3 4 5 6 7; do run dcmp$n --dcmp $n; done
run dwr0 --depth --dwrite 0
run dwr1 --depth --dwrite 1
run dclip_clip --depth --dclip 0
run dclip_clamp --depth --dclip 1
run dbias --depth --dbias
# --- stencil ---
for n in 0 1 2 3 4 5 6 7; do run scmp$n --sten --scmp $n; done
for n in 0 1 2 3 4 5 6 7; do run sfail$n --sten --sfail $n; done
for n in 0 1 2 3 4 5 6 7; do run szfail$n --sten --szfail $n; done
for n in 0 1 2 3 4 5 6 7; do run spass$n --sten --spass $n; done
run sref0 --sten --sref 0
run sref55 --sten --sref 0x55
run srefAA --sten --sref 0xaa
run srm0f --sten --srmask 0x0f
run swm0f --sten --swmask 0x0f
run stenB --sten --scmp 7 --scmpB 2 --spassB 5
# --- blend (programmable test + side flags) ---
run bl_on --blend
run bl_f1 --blend --srgb 4 --drgb 5
run bl_f2 --blend --srgb 2 --drgb 3
run bl_add --blend --brgb 0
run bl_sub --blend --brgb 1
run bl_rev --blend --brgb 2
run bl_min --blend --brgb 3
run bl_max --blend --brgb 4
run bl_col --blend --srgb 11 --drgb 12 --bcol
run bl_dual --dual
run wm_f --wmask 15
run wm_0 --wmask 0
run wm_r --wmask 8
run wm_a --wmask 1
run wm_rg --wmask 12
run a2c --a2c
run a2o --a2o
# --- raster ---
run cull_none --cull 0
run cull_front --cull 1
run cull_back --cull 2
run wind_cw --wind 0
run wind_ccw --wind 1
run cull_back_ccw --cull 2 --wind 1
run fill_fill --fill 0
run fill_lines --fill 1
echo "SWEEP_DONE" >>progress.log
# --- diffs vs base on the 0x58000 pool ---
{
echo "=== 0x58000 pool diffs vs base (va58000) ==="
for d in m_*; do n=${d#m_}; [ "$n" = "base" ] && continue
  echo "--- $n ---"; python3 scripts/pooldiff.py m_base "$d" 58000 0x800
done
} >ff_pool_diffs.txt 2>&1
echo "POOLDIFF_DONE" >>progress.log
# --- blend-programmable: shader BO + VDM diffs ---
{
echo "=== bl_f1 vs bl_f2 shader BO (va10000000000) — expect MANY diffs if blend is FS-compiled ==="
python3 scripts/pooldiff.py m_bl_f1 m_bl_f2 10000000000 0x8000
echo "=== bl_f1 vs bl_f2 pool (va58000) — expect FEW/none ==="
python3 scripts/pooldiff.py m_bl_f1 m_bl_f2 58000 0x800
echo "=== bl_on vs base shader BO ==="
python3 scripts/pooldiff.py m_base m_bl_on 10000000000 0x8000
} >ff_blend_prog.txt 2>&1
echo "ALL_DONE" >>progress.log
