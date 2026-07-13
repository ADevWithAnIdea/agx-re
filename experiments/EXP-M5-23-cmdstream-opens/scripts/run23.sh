#!/bin/sh
# run23.sh — EXP-M5-23 sweep on the M5 device (detached; poll progress.log).
# Builds 6 own-MSL harnesses, runs each probe under the iotrace interposer (dump ALL BOs),
# then diffs. Bulk BO snapshots stay on device (gitignored); only text analysis is pulled.
# Clean-room: own MSL/API only; iotrace logs non-copyrightable BO bytes from our own process.
cd ~/cleanroom_work/EXP-M5-23 || exit 1
IT=~/cleanroom_work/tools/iotrace
: >progress.log
tmo(){ t=$1; shift; perl -e 'alarm(shift); exec @ARGV' "$t" "$@"; }

echo "=== BUILD ===" >>progress.log
for h in mortondraw ratemap amp meshpayload usc icb; do
  clang -fobjc-arc -O0 -arch arm64e -framework Metal -framework Foundation scripts/$h.m -o $h 2>build_$h.err
  if [ -x $h ]; then echo "build $h OK" >>progress.log; else echo "build $h FAIL:" >>progress.log; sed -n '1,12p' build_$h.err >>progress.log; fi
done

# run NAME BIN [args...] : dump ALL BOs, no prune (VAs of interest unknown ahead of time)
run(){ NAME="$1"; BIN="$2"; shift 2; rm -rf m_$NAME; mkdir -p m_$NAME
  tmo 70 env IOTRACE_LOG=/dev/null IOTRACE_DUMP_DIR=m_$NAME IOTRACE_MAX_MAP=524288 \
    DYLD_INSERT_LIBRARIES=$IT/iotrace.dylib ./$BIN "$@" --dump >r_$NAME.txt 2>&1
  echo "$NAME: $(grep -oE 'STATUS=[0-9]+|COMPILE_FAIL.*|PIPELINE_FAIL.*|RRM[^ ]* [^\"]*|RRM_[A-Z_]*|physical=[0-9x]+|paramSize=0x[0-9a-f]+|paramVA=0x[0-9a-f]+|PIXEL[^\"]*|AMP_UNSUPPORTED [0-9]|CB_ERROR.*|MESHPAYLOAD.*' r_$NAME.txt | head -4 | tr '\n' ' ')" >>progress.log
}

echo "=== RUN ===" >>progress.log
run morton     mortondraw --w 192 --h 192      # TASK3
run rm_off     ratemap --rate 0                # TASK1
run rm_on      ratemap --rate 1                # TASK1
run amp1       amp --amp 1                      # TASK2 amplification
run amp2       amp --amp 2
run mesh_min   meshpayload                      # TASK2 mesh payload
run mesh_heavy meshpayload --heavy
run icb_draw1  icb --mode draw --n 1            # TASK2 ICB
run icb_draw4  icb --mode draw --n 4
run usc_b1     usc --tex 1 --samp 1 --buf 1     # TASK4 USC buffers
run usc_b2     usc --tex 1 --samp 1 --buf 2
run usc_b3     usc --tex 1 --samp 1 --buf 3
run usc_b4     usc --tex 1 --samp 1 --buf 4
echo SWEEP_DONE >>progress.log

echo "=== ANALYSIS ===" >>progress.log
{
echo "########## TASK3 MORTON (byte-verify vs A18 model) ##########"
python3 scripts/morton_verify.py m_morton 192 192 64 4
echo; echo "########## TASK1 RATEMAP: rate off vs on (all BO diffs) ##########"
python3 scripts/alldiff.py m_rm_off m_rm_on 0x1000
echo "--- BO list rm_on ---";  python3 scripts/dumpscan.py m_rm_on  --list
echo "--- BO list rm_off ---"; python3 scripts/dumpscan.py m_rm_off --list
echo; echo "########## TASK2 AMPLIFICATION: amp1 vs amp2 (all BO diffs) ##########"
python3 scripts/alldiff.py m_amp1 m_amp2 0x1000
echo; echo "########## TASK2 MESH payload: min vs heavy (all BO diffs) ##########"
python3 scripts/alldiff.py m_mesh_min m_mesh_heavy 0x1000
echo "--- BO list mesh_heavy ---"; python3 scripts/dumpscan.py m_mesh_heavy --list
echo "--- BO list mesh_min ---";   python3 scripts/dumpscan.py m_mesh_min   --list
echo; echo "########## TASK2 ICB draw records: n=1 vs n=4 ##########"
python3 scripts/alldiff.py m_icb_draw1 m_icb_draw4 0x1000
echo "--- icb_draw4 0x18000 first 0x120 bytes (records) ---"
for O in 0x00 0x04 0x08 0x0c 0x10 0x14 0x18 0x1c 0x20; do python3 scripts/shex.py m_icb_draw4/bo_sigusr1_h0_va18000_*.hex $O 4 2>/dev/null; done
echo; echo "########## TASK4 USC buffers: +0x610+k*8 slots ##########"
for d in usc_b1 usc_b2 usc_b3 usc_b4; do echo "--- $d ---"; python3 scripts/usc_find.py m_$d; done
} >captures/analysis.txt 2>&1
echo ANALYSIS_DONE >>progress.log
echo ALL_DONE >>progress.log
