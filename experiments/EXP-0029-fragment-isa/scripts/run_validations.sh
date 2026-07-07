#!/bin/bash
# EXP-0029 consolidated HW validations -> raw logs. Run on device in exp0029/.
cd ~/cleanroom_work/exp0029 || exit 1
R(){ ./agxrender_ext "$@" 2>&1 | grep -E "STATUS|PIPELINE_SOURCE|PIXEL"; }
S(){ python3 splice_render.py "$@" 2>&1 | grep -E "STATUS|PIXEL"; }

{
echo "### 1. Interpolation-mode baselines (4x4) — flat=constant, others=gradient"
for k in interp_flat interp_noperspective interp_smooth interp_centroid interp_sample; do
  echo "--- $k ---"; R --archive out/$k.bin --source kernels/$k.metal --vertex v_main --fragment f_main --width 4 --height 4 --clear 0,0,0,0
done

echo; echo "### 2. Perspective geometry (6x6 corners) — persp != linear != flat"
for k in persp_smooth persp_nopersp persp_flat; do
  echo "--- $k ---"; ./agxrender_ext --archive out/$k.bin --source kernels/$k.metal --vertex v_main --fragment f_main --width 6 --height 6 --clear 0,0,0,0 2>&1 | grep -E "PIXEL 5 0|PIXEL 3 3|PIXEL 0 5"
done

echo; echo "### 3. SPLICE: interp op byte+5 (source varying-slot) 0x00->0x02 (red x-grad -> y-grad)"
echo "-- baseline noperspective corners --"; R --archive out/interp_noperspective.bin --source kernels/interp_noperspective.metal --vertex v_main --fragment f_main --width 4 --height 4 --clear 0,0,0,0 | grep -E "PIXEL 0 0|PIXEL 3 0|PIXEL 0 3|PIXEL 3 3"
echo "-- spliced byte+5=0x02 --"; S out/interp_noperspective.bin kernels/interp_noperspective.metal v_main f_main 4 4 fragment 0x05=02 | grep -E "PIXEL 0 0|PIXEL 3 0|PIXEL 0 3|PIXEL 3 3"

echo; echo "### 4. Programmable-blend tilebuffer read (0x67 0e) vs clear colour: out = src*0.5 + clear*0.5"
for c in "0,0,0,0" "1,1,1,1" "0.4,0.6,0.8,1.0"; do
  echo "-- clear=$c --"; R --archive out/blend_read.bin --source kernels/blend_read.metal --vertex v_main --fragment f_main --width 1 --height 1 --clear $c
done

echo; echo "### 5. discard_fragment (4x1): x<2 killed -> clear; x>=2 coloured"
R --archive out/out_discard2.bin --source kernels/out_discard2.metal --vertex v_main --fragment f_main --width 4 --height 1 --clear 0,0,0,0

echo; echo "### 6. SPLICE colour-store: byte+5 RT-index 0x00->0x02 (absent RT) => RT0 stays clear"
S out/out_const.bin kernels/out_const.metal v_main f_main 1 1 fragment 0x25=02
echo "-- byte+1 0x06->0x00 (break tile-store variant) => RT0 stays clear --"
S out/out_const.bin kernels/out_const.metal v_main f_main 1 1 fragment 0x21=00
} | tee raw/validations.log
