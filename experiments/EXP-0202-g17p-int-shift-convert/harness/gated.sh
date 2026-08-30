#!/bin/bash
# EXP-0202 gated run wrapper -- RUNS ON THE NEO.
#
#   bash harness/gated.sh <run_id>
#
# Starts the sweep, then attaches `gpuwatch.py` to the SAME run directory so the
# quiet-window claim is a measurement for the duration of the capture
# (FIELD-SWEEP-PROTOCOL section 7, amended 2026-08-30). run.py creates the run
# directory and REFUSES a run id that already exists, so gpuwatch must attach
# after it, never before -- a `mkdir` ahead of run.py burns the id.
set -u
cd "$(dirname "$0")/.."
RUN="$1"
python3 run.py --run-id "$RUN" > "work/${RUN}.stdout" 2> "work/${RUN}.stderr" &
SWEEP=$!
sleep 2
python3 harness/gpuwatch.py --run "$RUN" --interval 2 > /dev/null 2>&1 &
WATCH=$!
wait $SWEEP
RC=$?
sleep 1
kill $WATCH 2>/dev/null
wait $WATCH 2>/dev/null
echo "sweep_rc=$RC"
tail -3 "work/${RUN}.stdout"
tail -5 "work/${RUN}.stderr"
wc -l "raw/${RUN}/sweep.jsonl" "raw/${RUN}/gpuwatch.jsonl"
