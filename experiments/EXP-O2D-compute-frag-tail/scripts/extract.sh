#!/bin/bash
# EXP-O2D device-side extractor: compile each compute kernel function, carve
# _agc.main + constant_program, emit hex. CLEAN-ROOM: OWN-SHADER only.
set -u
cd "$(dirname "$0")/.."
mkdir -p out raw
OUT=raw/mains.txt
echo "# EXP-O2D _agc.main hex extraction ($(date))" > $OUT
for src in "$@"; do
    base=$(basename "$src" .metal)
    fns=$(grep "kernel void" kernels/$base.metal | sed 's/.*kernel void \([a-zA-Z0-9_]*\).*/\1/')
    for f in $fns; do
        ./shdump -o out/${base}_$f.bin -f $f kernels/$base.metal 2> out/${base}_$f.err
        if [ $? -ne 0 ]; then
            echo "$base $f COMPILE_FAIL: $(grep -m1 -i error out/${base}_$f.err | head -c 160)" | tee -a $OUT
            continue
        fi
        main=$(python3 agxparse.py out/${base}_$f.bin --stage compute --extract-hex --symbol _agc.main 2>/dev/null)
        cp=$(python3 agxparse.py out/${base}_$f.bin --stage compute --extract-hex --symbol _agc.main.constant_program 2>/dev/null)
        echo "$base $f MAIN $main" | tee -a $OUT
        echo "$base $f CPROG $cp" >> $OUT
    done
done
echo "=== DONE ==="
