#!/bin/sh
# EXP-0210 serial queue 4: EXP-0206, the three carriers the dispatch named that are not
# blocked by the measured cf_nl2 hang wall.  One capture at a time.
set -u
cd "$(dirname "$0")/.."
log(){ echo "[$(date -u +%FT%TZ)] $*"; }
log "=== EXP-0206 capture 1/2 (forward: cl_atomic,cl_leaf,cl_chain)"
sh harness/capture.sh e0206_q02 2600 2900 'cd ~/agxre/EXP-0206 && python3 -B run.py --run-id g17p_quiet02 --order forward --carriers cl_atomic,cl_leaf,cl_chain'
log "=== EXP-0206 capture 2/2 (reversed: same three carriers)"
sh harness/capture.sh e0206_q03 2600 2900 'cd ~/agxre/EXP-0206 && python3 -B run.py --run-id g17p_quiet03 --order reversed --carriers cl_atomic,cl_leaf,cl_chain'
log "=== EXP-0206 pull (ONLY the new run dirs)"
for r in g17p_quiet02 g17p_quiet03; do
  mkdir -p "../EXP-0206-g17p-cf-scope/raw/$r"
  ALARM=600 sh harness/neo.sh put "user@192.168.170.254:agxre/EXP-0206/raw/$r/*" "../EXP-0206-g17p-cf-scope/raw/$r/" 2>&1 | grep -v Warning
  echo -n "$r "; wc -l < "../EXP-0206-g17p-cf-scope/raw/$r/sweep.jsonl" 2>/dev/null || echo "(none)"
done
( cd ../.. && git status --porcelain -- experiments/EXP-0206-g17p-cf-scope/raw | awk '$1=="M"{print "MODIFIED COMMITTED RAW: "$2}' )
log "=== QUEUE 4 COMPLETE"
