#!/bin/sh
# EXP-0144 capture driver: ONE PROCESS PER INSTRUMENT.
#
# The M4 host took MTLCompilerService down host-wide mid-run05 (three concurrent
# GPU experiments), which killed a 22k-case single-process capture at 8,412 cases
# and would have killed it again. Sharding by instrument means a wedge, a cascade,
# or a compiler-service outage costs ONE instrument, not the whole run, and the
# lost shard can be re-captured under a NEW id without topping anything up.
#
#   ./harness/capture.sh <run-group>
set -u
GROUP="$1"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
# priority order: the two pack/unpack instruments first, the dangerous
# synthesised packed_half2_hi last.
for I in pack_convert unpack_convert cvt_i2f cvt_i2f_src cvt_f2i \
         cvt_f2h cvt_f2h_dst cvt_bf16 packed_half2_hi; do
    ID="${GROUP}__${I}"
    if [ -d "raw/$ID" ]; then echo "SKIP $ID (exists)"; continue; fi
    echo "=== $ID ==="
    python3 harness/run.py --run-id "$ID" --run-group "$GROUP" --only "$I" \
        >> "work/${GROUP}.log" 2>&1
    echo "   exit=$?"
    sleep 20        # settle gap: never start a capture inside the previous one's recovery
done
echo "GROUP $GROUP DONE"
