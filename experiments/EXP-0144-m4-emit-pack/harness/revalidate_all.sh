#!/bin/sh
# EXP-0144 revalidation driver: ONE PROCESS PER INSTRUMENT, majority-of-3(->5).
#   ./harness/revalidate_all.sh <run-group>
set -u
GROUP="$1"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
for I in pack_convert unpack_convert cvt_i2f cvt_i2f_src cvt_f2i \
         cvt_f2h cvt_f2h_dst cvt_bf16 packed_half2_hi; do
    ID="${GROUP}__${I}"
    if [ -d "raw/$ID" ]; then echo "SKIP $ID (exists)"; continue; fi
    echo "=== $ID $(date +%H:%M:%S) ==="
    python3 harness/revalidate.py --run-id "$ID" --run-group "$GROUP" --only "$I" \
        --reps 3 --max-reps 5 >> "work/${GROUP}.log" 2>&1
    echo "   exit=$?  $(date +%H:%M:%S)"
    sleep 15
done
echo "GROUP $GROUP DONE $(date +%H:%M:%S)"
