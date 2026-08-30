#!/bin/bash
# EXP-0202 AMENDMENT v3 gated-run wrapper -- RUNS ON THE NEO.
#
#   bash harness/gated2.sh <run_id> <forward|reverse>
#
# Gate E: the confirmation pair must differ in case ORDER, so an order-dependent
# artefact cannot pass as cross-run agreement. `gpuwatch.py` attaches to the run
# directory AFTER run2.py creates it -- run2.py refuses an existing run id, so a
# `mkdir` ahead of it burns the id (it already cost this experiment run01).
set -u
cd "$(dirname "$0")/.."
RUN="$1"; ORDER="${2:-forward}"
python3 run2.py --run-id "$RUN" --arms harness/arms202b.json --order "$ORDER" \
    > "work/${RUN}.stdout" 2> "work/${RUN}.stderr" &
SWEEP=$!
sleep 2
python3 harness/gpuwatch.py --run "$RUN" --interval 2 > /dev/null 2>&1 &
WATCH=$!
wait $SWEEP
RC=$?
sleep 1
kill $WATCH 2>/dev/null
wait $WATCH 2>/dev/null
echo "sweep_rc=$RC order=$ORDER"
tail -2 "work/${RUN}.stdout"
tail -5 "work/${RUN}.stderr"
wc -l "raw/${RUN}/sweep.jsonl" "raw/${RUN}/gpuwatch.jsonl"
