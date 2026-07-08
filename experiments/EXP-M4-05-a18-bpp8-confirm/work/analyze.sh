#!/bin/sh
cd ~/cleanroom_work/exp_bpp8
for cfg in "b8_96 rg32uint 96 96" "b8_160 rg32uint 160 160" "b8_288 rg32uint 288 288" \
           "b8_320 rg32uint 320 320" "b8_448 rg32uint 448 448" "b8_160x256 rg32uint 160 256" \
           "b4_160 r32uint 160 160" "b16_96 rgba32uint 96 96" "b16_160 rgba32uint 160 160"; do
  set -- $cfg; tag=$1; fmt=$2; W=$3; H=$4
  echo "########## $tag ($fmt ${W}x${H}) ##########"
  python3 tvcheck.py "maps_$tag" --fmt "$fmt" --w "$W" --h "$H" 2>&1
  echo
done
