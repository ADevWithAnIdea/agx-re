#!/bin/bash
# EXP-0201 gated run wrapper -- RUNS ON THE NEO.
#
#   bash harness/gated_run.sh <run_id> [extra run.py args...]
#
# Starts the sweep, then attaches `harness/gpuwatch.py` to the SAME run
# directory so concurrent GPU activity is sampled for the whole duration and
# lands in `raw/<run_id>/gpuwatch.jsonl` beside the sweep.
#
# Order matters: `run.py` REFUSES a run id whose directory already exists (run
# ids are never reused, and a partial capture is retained rather than topped
# up), so the sampler must attach AFTER run.py has created the directory, not
# before. It is killed when the sweep finishes.
#
# FIELD-SWEEP-PROTOCOL section 7: a confirmation run needs a quiet machine, and
# "the machine was quiet" must be a MEASUREMENT rather than a claim. Nothing
# here serializes anything -- there is no lease, and sweeps stay unlocked.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
RUN_ID="${1:?usage: gated_run.sh <run_id> [run.py args]}"
shift || true

python3 run.py --run-id "$RUN_ID" "$@" > "work/${RUN_ID}.stdout" 2>&1 &
SWEEP=$!

for _ in $(seq 1 60); do
  [ -d "raw/${RUN_ID}" ] && break
  sleep 0.2
done
python3 harness/gpuwatch.py "raw/${RUN_ID}/gpuwatch.jsonl" 3600 \
    > "work/${RUN_ID}.watch" 2>&1 &
WATCH=$!

wait "$SWEEP"; RC=$?
kill "$WATCH" 2>/dev/null
wait "$WATCH" 2>/dev/null
tail -3 "work/${RUN_ID}.stdout"
echo "gated_run: run.py exit=$RC  samples=$(wc -l < "raw/${RUN_ID}/gpuwatch.jsonl" 2>/dev/null || echo 0)"
exit "$RC"
