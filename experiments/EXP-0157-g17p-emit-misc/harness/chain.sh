#!/bin/bash
# EXP-0157 capture chain, run ON THE NEO under nohup.
#   1. wait for run01 to finish
#   2. run02 = an independent capture of run01's RESOLVED case list (--replay),
#      so the two gated runs compare like with like even though anchors are
#      discovered on target
#   3. lease-confirm every fault/hang of BOTH runs, 5x each, under
#      ~/agxre/gpulease.sh  (FIELD-SWEEP-PROTOCOL section 7A: majority-of-3 in an
#      unlocked run is NOT sufficient for a fault verdict)
set -u
cd "$HOME/agxre/EXP-0157"
export AGX_TOOLS="$HOME/agxre/tools"

while pgrep -f "run.py --run-id g17p_run01" >/dev/null; do sleep 20; done
echo "[chain] run01 finished at $(date -u +%FT%TZ)"

python3 -B harness/run.py --run-id g17p_run02 --bin-dir bin --work work/w_run02 \
    --raw raw/g17p_run02 --arms R,S,H --max-anchors 12 --sweep-anchors 1 \
    --replay raw/g17p_run01/00_cases.json > work/run02.log 2>&1
echo "[chain] run02 finished at $(date -u +%FT%TZ)"

cat raw/g17p_run01/sweep.jsonl raw/g17p_run02/sweep.jsonl > work/gated_all.jsonl
$HOME/agxre/gpulease.sh EXP-0157 2400 -- \
  python3 -B harness/run.py --run-id g17p_reval01 --bin-dir bin --work work/w_reval \
    --raw raw/g17p_reval01 --arms R,S,H --replay raw/g17p_run01/00_cases.json \
    --revalidate work/gated_all.jsonl --revalidate-outcomes fault,hang,nondeterministic \
    --repeats 5 > work/reval01.log 2>&1
echo "[chain] reval finished at $(date -u +%FT%TZ) rc=$?"
