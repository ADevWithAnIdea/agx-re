#!/bin/bash
# EXP-0016 device-side extractor: compile each texture kernel (compute + render),
# carve _agc.main, emit hex. Runs on the A18 target under ~/cleanroom_work/exp0016.
# CLEAN-ROOM: OWN-SHADER only. No Apple binary disassembled.
set -u
cd "$(dirname "$0")"
mkdir -p out raw

FRAG_FNS="f_sample f_bias f_lod f_grad f_gather f_gather_y f_two_tex f_two_samp f_tex1 f_samp1 f_sample_x f_read f_read_lod f_width f_height f_nmips f_wh"
COMP_FNS="c_sample_lod c_sample_grad c_two_tex c_two_samp c_read c_read_lod c_write c_readwrite c_read_array c_read_3d c_sample_cube c_sample_array c_read_ms c_width c_height c_nmips c_nsamples c_warray c_depth_cmp"

echo "# EXP-0016 _agc.main hex extraction" > raw/mains.txt

for f in $FRAG_FNS; do
    ./shdump -o out/frag_$f.bin --render --vertex v_main --fragment $f kernels/tex_frag.metal \
        2> out/frag_$f.err
    if [ $? -ne 0 ]; then echo "frag $f COMPILE_FAIL:"; tail -1 out/frag_$f.err; continue; fi
    hex=$(python3 agxparse.py out/frag_$f.bin --stage fragment --extract-hex --symbol _agc.main 2>/dev/null)
    echo "FRAG $f $hex" | tee -a raw/mains.txt
done

for f in $COMP_FNS; do
    ./shdump -o out/comp_$f.bin -f $f kernels/tex_comp.metal 2> out/comp_$f.err
    if [ $? -ne 0 ]; then echo "comp $f COMPILE_FAIL:"; tail -1 out/comp_$f.err; continue; fi
    hex=$(python3 agxparse.py out/comp_$f.bin --stage compute --extract-hex --symbol _agc.main 2>/dev/null)
    echo "COMP $f $hex" | tee -a raw/mains.txt
done
echo "=== DONE ==="
