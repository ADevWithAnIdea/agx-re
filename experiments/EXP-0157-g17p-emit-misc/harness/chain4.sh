#!/bin/bash
# EXP-0157 chain 4 (run ON THE NEO under nohup).
#
# WHY THIS EXISTS. chain2's fault-confirmation pass never ran: at the moment it
# invoked ~/agxre/gpulease.sh, that shared script was mid-rewrite by another
# agent and bash could not parse it ("unexpected EOF while looking for matching
# `'`" at line 48). It parses cleanly again now. The pass is therefore retried
# here, over ALL THREE gated captures rather than chain3's restricted subset.
#
#   1. wait for run03 to finish
#   2. stop chain3 so its narrower reval02 does not also queue for the lease
#   3. ONE full fault/hang confirmation, 5x per case, under the lease
#      (FIELD-SWEEP-PROTOCOL 7A)
set -u
cd "$HOME/agxre/EXP-0157"
export AGX_TOOLS="$HOME/agxre/tools"

while pgrep -f "run.py --run-id g17p_run03" >/dev/null; do sleep 20; done
echo "[chain4] run03 finished $(date -u +%FT%TZ)"
pkill -f "harness/chain3.sh" 2>/dev/null || true

cat raw/g17p_run01/sweep.jsonl raw/g17p_run02/sweep.jsonl raw/g17p_run03/sweep.jsonl \
    > work/gated_all3.jsonl 2>/dev/null
bash -n "$HOME/agxre/gpulease.sh" || { echo "[chain4] gpulease.sh is not parseable; aborting"; exit 1; }
"$HOME/agxre/gpulease.sh" EXP-0157 3000 -- \
  python3 -B harness/run.py --run-id g17p_reval03 --bin-dir bin --work work/w_reval3 \
    --raw raw/g17p_reval03 --arms R,S,H --replay raw/g17p_run01/00_cases.json \
    --revalidate work/gated_all3.jsonl --revalidate-outcomes fault,hang,nondeterministic \
    --repeats 5 > work/reval03.log 2>&1
echo "[chain4] reval03 finished $(date -u +%FT%TZ) rc=$?"
