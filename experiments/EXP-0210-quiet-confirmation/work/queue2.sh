#!/bin/sh
# EXP-0210 serial queue 2: EXP-0206 then EXP-0204.  STRICTLY one capture at a time.
set -u
cd "$(dirname "$0")/.."
HERE="$(pwd)"
log(){ echo "[$(date -u +%FT%TZ)] $*"; }

log "=== EXP-0206: push"
( cd ../EXP-0206-g17p-cf-scope && perl -e 'alarm 400; exec @ARGV' bash harness/sync.sh push ) > work/push206.txt 2>&1
log "push rc=$?"
log "=== EXP-0206: its own verify_remote (separate step)"
( cd ../EXP-0206-g17p-cf-scope && perl -e 'alarm 400; exec @ARGV' python3 harness/verify_remote.py ) > work/v206.txt 2>&1
log "verify_remote rc=$?"; tail -4 work/v206.txt
log "=== EXP-0206: verify repo==neo"
( cd ../EXP-0206-g17p-cf-scope && FILES=$(find harness kernels analysis pinned -type f ! -path '*__pycache__*' 2>/dev/null | sort; echo run.py) && python3 "$HERE/harness/verify_repo_eq_neo.py" . agxre/EXP-0206 $FILES ) > work/repoeq206.txt 2>&1
tail -3 work/repoeq206.txt

log "=== EXP-0206 capture 1/2 (forward, ALL nine carriers)"
sh harness/capture.sh e0206_q01 2600 2900 'cd ~/agxre/EXP-0206 && python3 -B run.py --run-id g17p_quiet01 --order forward'
log "=== EXP-0206 capture 2/2 (reversed, ALL nine carriers)"
sh harness/capture.sh e0206_q02 2600 2900 'cd ~/agxre/EXP-0206 && python3 -B run.py --run-id g17p_quiet02 --order reversed'
log "=== EXP-0206 pull (ONLY the new run dirs -- never over the committed raw)"
for r in g17p_quiet01 g17p_quiet02; do
  mkdir -p "../EXP-0206-g17p-cf-scope/raw/$r"
  ALARM=900 sh harness/neo.sh put "user@192.168.170.254:agxre/EXP-0206/raw/$r/*" "../EXP-0206-g17p-cf-scope/raw/$r/" 2>&1 | grep -v Warning
done
wc -l ../EXP-0206-g17p-cf-scope/raw/g17p_quiet01/sweep.jsonl ../EXP-0206-g17p-cf-scope/raw/g17p_quiet02/sweep.jsonl 2>&1

log "=== EXP-0204: push"
( cd ../EXP-0204-g17p-tex-carrier-dimensions && perl -e 'alarm 400; exec @ARGV' sh harness/sync.sh push ) > work/push204.txt 2>&1
log "push rc=$?"
log "=== EXP-0204: verify repo==neo (no verify_remote.py in this experiment)"
( cd ../EXP-0204-g17p-tex-carrier-dimensions && FILES=$(find harness kernels analysis pinned -type f ! -path '*__pycache__*' 2>/dev/null | sort; echo run.py) && python3 "$HERE/harness/verify_repo_eq_neo.py" . agxre/EXP-0204 $FILES ) > work/repoeq204.txt 2>&1
tail -4 work/repoeq204.txt

log "=== EXP-0204 capture 1/2: tex_sample+tex_write, shuffle seed 11 (its OWN quietconfirm.sh recipe)"
sh harness/capture.sh e0204_c1 1300 1500 'cd ~/agxre/EXP-0204 && python3 -B run.py --run-id g17p_quiet_C1 --mnem tex_sample,tex_write --order shuffle --seed 11 --deadline-s 900'
log "=== EXP-0204 capture 2/2: same arms, reverse order"
sh harness/capture.sh e0204_c2 1300 1500 'cd ~/agxre/EXP-0204 && python3 -B run.py --run-id g17p_quiet_C2 --mnem tex_sample,tex_write --order reverse --deadline-s 900'
log "=== EXP-0204 capture 3/4: tex_deriv mapping pass, forward"
sh harness/capture.sh e0204_d1 2000 2300 'cd ~/agxre/EXP-0204 && python3 -B run.py --run-id g17p_quiet_A2runD1 --mnem tex_deriv --order forward --deadline-s 1500'
log "=== EXP-0204 capture 4/4: tex_deriv mapping pass, reverse"
sh harness/capture.sh e0204_d2 2000 2300 'cd ~/agxre/EXP-0204 && python3 -B run.py --run-id g17p_quiet_A2runD2 --mnem tex_deriv --order reverse --deadline-s 1500'
log "=== EXP-0204 pull (ONLY the new run dirs -- its sync.sh pull untars over raw/, which would overwrite committed evidence)"
for r in g17p_quiet_C1 g17p_quiet_C2 g17p_quiet_A2runD1 g17p_quiet_A2runD2; do
  mkdir -p "../EXP-0204-g17p-tex-carrier-dimensions/raw/$r"
  ALARM=900 sh harness/neo.sh put "user@192.168.170.254:agxre/EXP-0204/raw/$r/*" "../EXP-0204-g17p-tex-carrier-dimensions/raw/$r/" 2>&1 | grep -v Warning
done
ls ../EXP-0204-g17p-tex-carrier-dimensions/raw/
log "=== tracked-raw safety check (must print nothing)"
( cd ../.. && git status --porcelain -- experiments/EXP-0204-g17p-tex-carrier-dimensions/raw experiments/EXP-0206-g17p-cf-scope/raw | awk '$1=="M"{print "MODIFIED COMMITTED RAW: "$2}' )
log "=== QUEUE 2 COMPLETE"
