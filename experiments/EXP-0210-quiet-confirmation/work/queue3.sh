#!/bin/sh
# EXP-0210 serial queue 3: EXP-0204 only.  One capture at a time.
set -u
cd "$(dirname "$0")/.."
HERE="$(pwd)"
log(){ echo "[$(date -u +%FT%TZ)] $*"; }
log "=== EXP-0204: push"
( cd ../EXP-0204-g17p-tex-carrier-dimensions && perl -e 'alarm 400; exec @ARGV' sh harness/sync.sh push ) > work/push204.txt 2>&1
log "push rc=$?"
log "=== EXP-0204: verify repo==neo (this experiment has no verify_remote.py)"
( cd ../EXP-0204-g17p-tex-carrier-dimensions && FILES=$(find harness kernels analysis pinned -type f ! -path '*__pycache__*' 2>/dev/null | sort; echo run.py) && python3 "$HERE/harness/verify_repo_eq_neo.py" . agxre/EXP-0204 $FILES ) > work/repoeq204.txt 2>&1
tail -4 work/repoeq204.txt
log "=== EXP-0204 capture 1/4: tex_sample+tex_write, shuffle seed 11 (its own quietconfirm.sh recipe)"
sh harness/capture.sh e0204_c1 1300 1500 'cd ~/agxre/EXP-0204 && python3 -B run.py --run-id g17p_quiet_C1 --mnem tex_sample,tex_write --order shuffle --seed 11 --deadline-s 900'
log "=== EXP-0204 capture 2/4: same arms, reverse order"
sh harness/capture.sh e0204_c2 1300 1500 'cd ~/agxre/EXP-0204 && python3 -B run.py --run-id g17p_quiet_C2 --mnem tex_sample,tex_write --order reverse --deadline-s 900'
log "=== EXP-0204 capture 3/4: tex_deriv mapping pass, forward, 900 s budget"
sh harness/capture.sh e0204_d1 1300 1500 'cd ~/agxre/EXP-0204 && python3 -B run.py --run-id g17p_quiet_A2runD1 --mnem tex_deriv --order forward --deadline-s 900'
log "=== EXP-0204 capture 4/4: tex_deriv mapping pass, reverse, 900 s budget"
sh harness/capture.sh e0204_d2 1300 1500 'cd ~/agxre/EXP-0204 && python3 -B run.py --run-id g17p_quiet_A2runD2 --mnem tex_deriv --order reverse --deadline-s 900'
log "=== EXP-0204 pull (ONLY the new run dirs)"
for r in g17p_quiet_C1 g17p_quiet_C2 g17p_quiet_A2runD1 g17p_quiet_A2runD2; do
  mkdir -p "../EXP-0204-g17p-tex-carrier-dimensions/raw/$r"
  ALARM=600 sh harness/neo.sh put "user@192.168.170.254:agxre/EXP-0204/raw/$r/*" "../EXP-0204-g17p-tex-carrier-dimensions/raw/$r/" 2>&1 | grep -v Warning
  echo -n "$r "; wc -l < "../EXP-0204-g17p-tex-carrier-dimensions/raw/$r/sweep.jsonl" 2>/dev/null || echo "(none)"
done
( cd ../.. && git status --porcelain -- experiments/EXP-0204-g17p-tex-carrier-dimensions/raw | awk '$1=="M"{print "MODIFIED COMMITTED RAW: "$2}' )
log "=== QUEUE 3 COMPLETE"
