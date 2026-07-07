#!/bin/sh
cd ~/cleanroom_work/exp0014
CTRL="0x18000 0x28000 0x38000 0x48000 0x58000 0x68000 0x10000040000 0x10000100000 0x10000110000 0x10000120000 0x10000130000"
for l in "$@"; do
  echo "########## $l ##########"
  for va in $CTRL; do
    out=$(python3 bodiff.py caps/base caps/$l --va $va --maxlen 0x800 2>/dev/null | grep "[+]0x0")
    if [ -n "$out" ]; then echo "-- BO $va --"; echo "$out"; fi
  done
done
