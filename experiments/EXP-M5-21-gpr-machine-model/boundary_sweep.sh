#!/bin/sh
# boundary_sweep.sh — A18-style GPR hard-boundary probe on M5. Splices the m5_load
# index-register field (byte+5 = file offset 0x0d) of our own `out[gid]=in[gid]` kernel
# to a range of register selectors and records STATUS. The OK->fault transition marks the
# physical register-file boundary (content-independent validation fault, as on A18/RT-7).
# CLEAN-ROOM: splice-and-observe on OUR OWN compiled shader. No Apple binary introspected.
cd ~/cleanroom_work/EXP-M5-21 || exit 1
AGX=~/cleanroom_work/tools/agxtest/agxtest.py
SHD=~/cleanroom_work/tools/shdump/shdump
OFF=0x0d
for V in "$@"; do
  HEX=$(printf '%02x' "$V")
  R=$(perl -e 'alarm(shift); exec @ARGV' 25 python3 $AGX --source kernels/ld.metal --function k --int \
        --grid 8 --tg 8 --buf 1=1,2,3,4,5,6,7,8 --out 0=8 --shdump $SHD --run-timeout 10 \
        --splice _agc.main@$OFF=$HEX 2>&1)
  ST=$(echo "$R" | grep -oE 'STATUS [A-Z_]+' | head -1)
  O0=$(echo "$R" | grep -oE 'OUT 0 [0-9a-f]+' | head -1 | cut -c7-22)
  [ -z "$ST" ] && ST="STATUS ??(timeout/err)"
  printf 'byte+5=0x%02x (dec %3d)  %-22s out0=%s\n' "$V" "$V" "$ST" "$O0"
done
