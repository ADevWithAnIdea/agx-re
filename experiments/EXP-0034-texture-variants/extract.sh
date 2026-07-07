#!/bin/bash
# EXP-0034 device-side extractor: compile each texture-variant kernel (compute +
# render), carve _agc.main, emit hex. Runs on the A18 target under ~/cleanroom_work/exp0034.
# CLEAN-ROOM: OWN-SHADER only. No Apple binary disassembled.
set -u
cd "$(dirname "$0")"
mkdir -p out raw

COMP_FNS="b_sample_lod b_gather g_x g_y g_z g_w g_off10 g_off01 g_off33 s_off \
sc_lod sc_ref sc_off gc gc_off lod_c lod_u s_array s_cube s_cube_array s_3d r_ms_s"
FRAG_FNS="f_scmp f_scmp_off f_gcmp f_sample f_gather_z f_gather_w f_sample_off"

echo "# EXP-0034 _agc.main hex extraction" > raw/mains.txt

for f in $COMP_FNS; do
    ./shdump -o out/comp_$f.bin -f $f kernels/tv_comp.metal 2> out/comp_$f.err
    if [ $? -ne 0 ]; then echo "COMP $f COMPILE_FAIL: $(tail -1 out/comp_$f.err)" | tee -a raw/mains.txt; continue; fi
    hex=$(python3 agxparse.py out/comp_$f.bin --stage compute --extract-hex --symbol _agc.main 2>/dev/null)
    echo "COMP $f $hex" | tee -a raw/mains.txt
done

for f in $FRAG_FNS; do
    ./shdump -o out/frag_$f.bin --render --vertex v_main --fragment $f kernels/tv_frag.metal 2> out/frag_$f.err
    if [ $? -ne 0 ]; then echo "FRAG $f COMPILE_FAIL: $(tail -1 out/frag_$f.err)" | tee -a raw/mains.txt; continue; fi
    hex=$(python3 agxparse.py out/frag_$f.bin --stage fragment --extract-hex --symbol _agc.main 2>/dev/null)
    echo "FRAG $f $hex" | tee -a raw/mains.txt
done

echo "# --- texture atomics probe (expected COMPILE_FAIL) ---" | tee -a raw/atomics.txt
for f in a_add a_buf; do
    ./shdump -o out/atom_$f.bin -f $f kernels/tv_atomic.metal 2> out/atom_$f.err
    if [ $? -ne 0 ]; then echo "ATOMIC $f COMPILE_FAIL: $(cat out/atom_$f.err | tr '\n' ' ' | cut -c1-400)" | tee -a raw/atomics.txt;
    else echo "ATOMIC $f COMPILED (unexpected!)" | tee -a raw/atomics.txt; fi
done
echo "=== DONE ==="
