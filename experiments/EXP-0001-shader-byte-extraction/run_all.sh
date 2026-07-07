#!/bin/bash
# run_all.sh — EXP-0001 device-side driver (runs on the A18 target).
#
# For every kernel in kernels/:
#   * compile+serialize the pipeline THREE times (determinism check),
#   * parse each container with our own agxparse.py,
#   * extract _agc.main / _agc.main.constant_program / whole __text as hex,
#   * record sha256 of the extracted AGX bytes across the three runs.
#
# All Apple containers stay on the device (out/, gitignored). Only hex/text
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
rm -f "$RAW"/*.hex "$RAW"/*.report.txt "$RAW"/determinism.txt "$RAW"/manifest.txt "$RAW"/*.info.txt 2>/dev/null

if [ ! -x ./shdump ]; then
    echo "building shdump..."
    clang -fobjc-arc -framework Metal -framework Foundation -o shdump shdump.m || exit 1
fi

sha() { python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" "$1"; }

echo "kernel                 main_len cprog_len text_len" > "$RAW/manifest.txt"
echo "determinism: sha256 of extracted _agc.main across 3 independent compilations" > "$RAW/determinism.txt"

for k in kernels/*.metal; do
    name=$(basename "$k" .metal)
    echo "=== $name ==="
    m1=""; m2=""; m3=""
    for run in 1 2 3; do
        bin="$OUT/${name}.run${run}.bin"
        ./shdump -o "$bin" "$k" 2> "$OUT/${name}.run${run}.stderr" || { echo "  shdump FAILED"; continue; }
        # extract the three regions
        python3 agxparse.py "$bin" --extract-bin "$OUT/${name}.run${run}.main.bin"  --symbol _agc.main >/dev/null 2>&1
        python3 agxparse.py "$bin" --extract-bin "$OUT/${name}.run${run}.cprog.bin" --symbol _agc.main.constant_program >/dev/null 2>&1
        python3 agxparse.py "$bin" --extract-bin "$OUT/${name}.run${run}.text.bin"  --whole-text >/dev/null 2>&1
        h=$(sha "$OUT/${name}.run${run}.main.bin" 2>/dev/null)
        eval "m${run}=\$h"
    done

    # Report + hex from run 1.
    cp "$OUT/${name}.run1.stderr" "$RAW/${name}.info.txt"
    python3 agxparse.py "$OUT/${name}.run1.bin" >> "$RAW/${name}.info.txt" 2>&1
    python3 agxparse.py "$OUT/${name}.run1.bin" --extract-hex --symbol _agc.main > "$RAW/${name}.main.hex" 2>/dev/null
    python3 agxparse.py "$OUT/${name}.run1.bin" --extract-hex --symbol _agc.main.constant_program > "$RAW/${name}.cprog.hex" 2>/dev/null
    python3 agxparse.py "$OUT/${name}.run1.bin" --extract-hex --whole-text > "$RAW/${name}.text.hex" 2>/dev/null

    mlen=$(python3 -c "print(len(open('$RAW/${name}.main.hex').read().strip())//2)")
    clen=$(python3 -c "print(len(open('$RAW/${name}.cprog.hex').read().strip())//2)")
    tlen=$(python3 -c "print(len(open('$RAW/${name}.text.hex').read().strip())//2)")
    printf "%-22s %8s %9s %8s\n" "$name" "$mlen" "$clen" "$tlen" >> "$RAW/manifest.txt"

    if [ "$m1" = "$m2" ] && [ "$m2" = "$m3" ]; then verdict="STABLE"; else verdict="UNSTABLE"; fi
    printf "%-22s %s  [%s]\n" "$name" "$m1" "$verdict" >> "$RAW/determinism.txt"
    if [ "$verdict" = "UNSTABLE" ]; then
        printf "    run2=%s\n    run3=%s\n" "$m2" "$m3" >> "$RAW/determinism.txt"
    fi
done

echo
echo "=== manifest ==="; cat "$RAW/manifest.txt"
echo; echo "=== determinism ==="; cat "$RAW/determinism.txt"
