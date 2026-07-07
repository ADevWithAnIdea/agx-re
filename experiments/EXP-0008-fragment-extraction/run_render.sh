#!/bin/bash
# run_render.sh -- EXP-0008 device-side driver (runs on the A18 target).
#
# For every render shader pair in kernels/:
#   * compile+serialize the RENDER pipeline THREE times (determinism check),
#   * parse each container with our own agxparse.py (--stage vertex|fragment),
#   * extract _agc.main / _agc.main.constant_program / whole __text as hex
#     for BOTH the vertex and the fragment stage,
#   * record sha256 of each extracted AGX region across the three runs.
#
# All Apple containers stay on the device (out/, never pulled). Only hex/text
# reports are produced under raw/ to be pulled back to the repo.
#
# CLEAN-ROOM: OWN-SHADER. Only our own MSL is compiled; only our own compiled
# shader bytes are inspected. No Apple binary is disassembled.
set -u
cd "$(dirname "$0")"
ROOT="$PWD"
OUT="$ROOT/out"
RAW="$ROOT/raw"
mkdir -p "$OUT" "$RAW"
rm -f "$RAW"/*.hex "$RAW"/*.info.txt "$RAW"/manifest.txt "$RAW"/determinism.txt 2>/dev/null

if [ ! -x ./shdump ]; then
    echo "building shdump..."
    clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m || exit 1
fi

sha() { python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$1"; }

echo "shader           stage     main_len cprog_len text_len" > "$RAW/manifest.txt"
echo "determinism: sha256 of extracted _agc.main across 3 independent compilations" > "$RAW/determinism.txt"

for k in kernels/*.metal; do
    name=$(basename "$k" .metal)
    echo "=== $name ==="
    for stage in vertex fragment; do
        s1=""; s2=""; s3=""
        for run in 1 2 3; do
            bin="$OUT/${name}.run${run}.bin"
            if [ "$stage" = "vertex" ]; then
                ./shdump -o "$bin" --render --vertex v_main --fragment f_main "$k" \
                    2> "$OUT/${name}.run${run}.stderr" || { echo "  shdump FAILED"; continue; }
            fi
            python3 agxparse.py "$bin" --stage "$stage" --extract-bin \
                "$OUT/${name}.${stage}.run${run}.main.bin" --symbol _agc.main >/dev/null 2>&1
            h=$(sha "$OUT/${name}.${stage}.run${run}.main.bin" 2>/dev/null)
            eval "s${run}=\$h"
        done

        # Hex from run 1.
        bin="$OUT/${name}.run1.bin"
        python3 agxparse.py "$bin" --stage "$stage" --extract-hex --symbol _agc.main \
            > "$RAW/${name}.${stage}.main.hex" 2>/dev/null
        python3 agxparse.py "$bin" --stage "$stage" --extract-hex \
            --symbol _agc.main.constant_program > "$RAW/${name}.${stage}.cprog.hex" 2>/dev/null
        python3 agxparse.py "$bin" --stage "$stage" --extract-hex --whole-text \
            > "$RAW/${name}.${stage}.text.hex" 2>/dev/null

        mlen=$(python3 -c "print(len(open('$RAW/${name}.${stage}.main.hex').read().strip())//2)")
        clen=$(python3 -c "print(len(open('$RAW/${name}.${stage}.cprog.hex').read().strip())//2)")
        tlen=$(python3 -c "print(len(open('$RAW/${name}.${stage}.text.hex').read().strip())//2)")
        printf "%-16s %-8s %8s %9s %8s\n" "$name" "$stage" "$mlen" "$clen" "$tlen" >> "$RAW/manifest.txt"

        if [ "$s1" = "$s2" ] && [ "$s2" = "$s3" ]; then verdict="STABLE"; else verdict="UNSTABLE"; fi
        printf "%-16s %-8s %s  [%s]\n" "$name" "$stage" "$s1" "$verdict" >> "$RAW/determinism.txt"
        if [ "$verdict" = "UNSTABLE" ]; then
            printf "    run2=%s\n    run3=%s\n" "$s2" "$s3" >> "$RAW/determinism.txt"
        fi
    done
    # Structural report (run1) for the record.
    python3 agxparse.py "$OUT/${name}.run1.bin" > "$RAW/${name}.info.txt" 2>&1
done

echo
echo "=== manifest ==="; cat "$RAW/manifest.txt"
echo; echo "=== determinism ==="; cat "$RAW/determinism.txt"
