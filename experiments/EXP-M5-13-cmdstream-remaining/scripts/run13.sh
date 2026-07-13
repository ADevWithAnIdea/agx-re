#!/bin/sh
# run13.sh — EXP-M5-13 full sweep. Runs on the M5 device, detached. Poll progress.log.
# Builds 5 own-MSL harnesses, runs parametric probes under the iotrace interposer,
# prunes each capture to the command-stream BOs of interest, then diffs.
# Clean-room: own MSL/API only; iotrace logs non-copyrightable BO bytes from our own process.
cd ~/cleanroom_work/EXP-M5-13 || exit 1
IT=~/cleanroom_work/tools/iotrace
: >progress.log
tmo(){ t=$1; shift; perl -e 'alarm(shift); exec @ARGV' "$t" "$@"; }

echo "=== BUILD ===" >>progress.log
for h in ppp mesh usc ffstate cvar_compute; do
  clang -fobjc-arc -O0 -arch arm64e -framework Metal -framework Foundation scripts/$h.m -o $h 2>build_$h.err
  if [ -x $h ]; then echo "build $h OK" >>progress.log; else echo "build $h FAIL:" >>progress.log; cat build_$h.err >>progress.log; fi
done

# run NAME BIN [args...]  — dump + prune to $KEEP
run(){ NAME="$1"; BIN="$2"; shift 2; rm -rf m_$NAME; mkdir -p m_$NAME
  tmo 45 env IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR=m_$NAME IOTRACE_MAX_MAP=262144 \
    DYLD_INSERT_LIBRARIES=$IT/iotrace.dylib ./$BIN "$@" --dump >r_$NAME.txt 2>&1
  if [ -d m_$NAME ]; then for f in m_$NAME/bo_*; do [ -e "$f" ] || continue; b=$(basename "$f"); k=0
    for K in $KEEP; do case "$b" in *$K*) k=1;; esac; done; [ $k -eq 0 ] && rm -f "$f"; done; fi
  echo "$NAME: $(grep -oE 'STATUS=[0-9]+|COMPILE_FAIL[^\"]*|PIPELINE_FAIL[^\"]*|PIXEL.*' r_$NAME.txt | head -2 | tr '\n' ' ')" >>progress.log
}

########## TASK 3: MESH (run first — riskiest) ##########
KEEP="_va18000_ _va58000_ _va68000_ _va10000000000_ _va100000f8000_ _va10000018000_ _va100000b0000_"
echo "=== TASK3 mesh ===" >>progress.log
run mesh_on   mesh
# ordinary draw baseline for the same tiler stream, from ppp base
KEEP2="$KEEP"

########## TASK 2: PPP output-select ##########
KEEP="_va18000_ _va58000_ _va68000_ _va10000000000_"
echo "=== TASK2 ppp ===" >>progress.log
run ppp_base  ppp --mode base
run ppp_psize ppp --mode psize
run ppp_vpidx ppp --mode vpidx
run ppp_rtidx ppp --mode rtidx
for n in 1 2 3 4 5 6 7 8; do run ppp_clip$n ppp --mode clip --nclip $n; done

########## TASK 5: FF write-mask per-channel packing ##########
KEEP="_va58000_ _va18000_ _va10000000000_"
echo "=== TASK5 wmask ===" >>progress.log
for m in 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do run wm$m ffstate --wmask $m; done

########## TASK 4: CDM config constants ##########
KEEP="_va100000b0000_ _va10000090000_ _va10000000000_"
echo "=== TASK4 cdm ===" >>progress.log
run cdm_base   cvar_compute --grid 64 --tg 32
run cdm_g256   cvar_compute --grid 256 --tg 32
run cdm_g1024  cvar_compute --grid 1024 --tg 64
run cdm_tg1    cvar_compute --grid 64 --tg 1
run cdm_tg256  cvar_compute --grid 256 --tg 256
run cdm_tgm256 cvar_compute --grid 64 --tg 32 --tgmem 256
run cdm_tgm16k cvar_compute --grid 64 --tg 32 --tgmem 16384
run cdm_heavy  cvar_compute --grid 64 --tg 32 --heavy

########## TASK 1: USC graphics bind grammar ##########
KEEP="_va18000_ _va58000_ _va68000_ _va10000"
echo "=== TASK1 usc ===" >>progress.log
run usc_t1s1b1 usc --tex 1 --samp 1 --buf 1
run usc_t2s1b1 usc --tex 2 --samp 1 --buf 1
run usc_t1s2b1 usc --tex 1 --samp 2 --buf 1
run usc_t1s1b2 usc --tex 1 --samp 1 --buf 2
run usc_t3s3b1 usc --tex 3 --samp 3 --buf 1
run usc_t0s0b0 usc --tex 0 --samp 0 --buf 0
run usc_t0s0b2 usc --tex 0 --samp 0 --buf 2

echo "SWEEP_DONE" >>progress.log

########## DIFFS ##########
echo "=== DIFF task2 ppp vs base (0x58000, 0x68000, 0x18000) ===" >diffs.txt
for d in ppp_psize ppp_vpidx ppp_rtidx ppp_clip1 ppp_clip2 ppp_clip3 ppp_clip4 ppp_clip5 ppp_clip6 ppp_clip7 ppp_clip8; do
  echo "--- $d vs ppp_base ---" >>diffs.txt
  for VA in 58000 68000 18000; do python3 scripts/pooldiff.py m_ppp_base m_$d $VA 0x800 >>diffs.txt 2>&1; done
done
echo "=== DIFF task5 wmask (0x58000 +0x180..+0x1a0 focus) vs wm15 (full) ===" >>diffs.txt
for m in 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14; do
  echo "--- wm$m vs wm15 ---" >>diffs.txt
  python3 scripts/pooldiff.py m_wm15 m_wm$m 58000 0x800 >>diffs.txt 2>&1
done
echo "=== DIFF task4 cdm vs base (0x100000b0000) ===" >>diffs.txt
for d in cdm_g256 cdm_g1024 cdm_tg1 cdm_tg256 cdm_tgm256 cdm_tgm16k cdm_heavy; do
  echo "--- $d vs cdm_base ---" >>diffs.txt
  python3 scripts/pooldiff.py m_cdm_base m_$d 100000b0000 0x80 >>diffs.txt 2>&1
done
echo "=== DIFF task1 usc all-BO (t1s1b1 vs variants) ===" >>diffs.txt
for d in usc_t2s1b1 usc_t1s2b1 usc_t1s1b2 usc_t3s3b1 usc_t0s0b0 usc_t0s0b2; do
  echo "--- $d vs usc_t1s1b1 (all BOs) ---" >>diffs.txt
  python3 scripts/alldiff.py m_usc_t1s1b1 m_$d 0x2000 >>diffs.txt 2>&1
done
echo "DIFF_DONE" >>progress.log
echo "ALL_DONE" >>progress.log
