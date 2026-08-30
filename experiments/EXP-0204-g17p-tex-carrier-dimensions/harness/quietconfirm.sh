#!/bin/sh
# EXP-0204 GATE E helper -- run the confirmation pair ONLY in a genuinely quiet
# window.  RE_EXPERIMENT_PROCESS_CORRECTIONS Gate E: "Promotion/confirmation runs
# may not rely on a busy machine sweep."  This polls the device process table and
# fires the pair the moment no OTHER experiment's GPU processes are running; if no
# window appears inside the budget it EXITS NONZERO and the experiment reports
# Gate E as NOT MET rather than passing off a busy pair as a confirmation.
#   usage: sh harness/quietconfirm.sh <budget_seconds> <consecutive_quiet_samples>
BUDGET=${1:-1500}
NEED=${2:-3}
cd "$(dirname "$0")/.."
END=$(( $(date +%s) + BUDGET ))
Q=0
while [ "$(date +%s)" -lt "$END" ]; do
  N=$(ps -eo pid,command \
      | grep -Ei 'gfrun|agxrun|rendersweep|persistrun|rsdrv|run\.py' \
      | grep -v grep | grep -v 'EXP-0204' | grep -v quietconfirm | wc -l | tr -d ' ')
  if [ "$N" = "0" ]; then Q=$((Q+1)); else Q=0; fi
  echo "$(date -u +%H:%M:%S) foreign=$N quiet_streak=$Q"
  if [ "$Q" -ge "$NEED" ]; then
    echo "QUIET WINDOW -- firing the confirmation pair"
    python3 -B run.py --run-id g17p_20260830_C1 --mnem tex_sample,tex_write \
        --order shuffle --seed 11 --deadline-s 900 && \
    python3 -B run.py --run-id g17p_20260830_C2 --mnem tex_sample,tex_write \
        --order reverse --deadline-s 900
    exit 0
  fi
  sleep 5
done
echo "NO QUIET WINDOW WITHIN ${BUDGET}s -- GATE E NOT MET"
exit 3
