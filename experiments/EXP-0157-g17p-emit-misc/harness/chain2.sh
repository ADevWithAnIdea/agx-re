#!/bin/bash
# EXP-0157 capture chain, revision 2 (run ON THE NEO under nohup).
# run01 is fault-heavy (a quarter of the `h_coord_hi` arm faults, and every
# fault costs three confirmation attempts plus innocent-victim retries), so
# serialising run02 behind it would cost hours for no evidentiary gain: the two
# gated runs are INDEPENDENT captures of the same frozen case list and nothing
# requires them to be sequential. run02 therefore starts immediately, replaying
# run01's already-written resolved case list.
#   1. run02 (concurrent with run01)
#   2. wait for BOTH
#   3. lease-confirm every fault/hang of both runs, 5x each, under the GPU lease
#      (FIELD-SWEEP-PROTOCOL 7A: majority-of-3 unlocked is NOT sufficient)
set -u
cd "$HOME/agxre/EXP-0157"
export AGX_TOOLS="$HOME/agxre/tools"

python3 -B harness/run.py --run-id g17p_run02 --bin-dir bin --work work/w_run02 \
    --raw raw/g17p_run02 --arms R,S,H --max-anchors 12 --sweep-anchors 1 \
    --replay raw/g17p_run01/00_cases.json > work/run02.log 2>&1
echo "[chain2] run02 finished $(date -u +%FT%TZ)"

while pgrep -f "run.py --run-id g17p_run01" >/dev/null; do sleep 20; done
echo "[chain2] run01 finished $(date -u +%FT%TZ)"

cat raw/g17p_run01/sweep.jsonl raw/g17p_run02/sweep.jsonl > work/gated_all.jsonl
"$HOME/agxre/gpulease.sh" EXP-0157 2700 -- \
  python3 -B harness/run.py --run-id g17p_reval01 --bin-dir bin --work work/w_reval \
    --raw raw/g17p_reval01 --arms R,S,H --replay raw/g17p_run01/00_cases.json \
    --revalidate work/gated_all.jsonl --revalidate-outcomes fault,hang,nondeterministic \
    --repeats 5 > work/reval01.log 2>&1
echo "[chain2] reval finished $(date -u +%FT%TZ) rc=$?"
