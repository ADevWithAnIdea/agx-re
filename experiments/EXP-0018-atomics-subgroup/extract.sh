#!/bin/bash
# EXP-0018 device-side extractor: compile each atomics/simd/quad kernel, carve
# _agc.main, emit hex. Runs on the A18 target under ~/cleanroom_work/exp0018.
# CLEAN-ROOM: OWN-SHADER only. No Apple binary disassembled.
set -u
cd "$(dirname "$0")"
mkdir -p out raw

echo "# EXP-0018 _agc.main hex extraction" > raw/mains.txt
for src in atomics simd quad; do
    fns=$(grep "kernel void" kernels/$src.metal | sed 's/.*kernel void \([a-zA-Z0-9_]*\).*/\1/')
    for f in $fns; do
        ./shdump -o out/${src}_$f.bin -f $f kernels/$src.metal 2> out/${src}_$f.err
        if [ $? -ne 0 ]; then echo "$src $f COMPILE_FAIL: $(grep -m1 error: out/${src}_$f.err)"; continue; fi
        hex=$(python3 agxparse.py out/${src}_$f.bin --stage compute --extract-hex --symbol _agc.main 2>/dev/null)
        echo "$src $f $hex" | tee -a raw/mains.txt
    done
done
echo "=== DONE ==="
