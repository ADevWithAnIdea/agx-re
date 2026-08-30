#!/bin/sh
# EXP-0210 serial queue 1: EXP-0201 then EXP-0199.  STRICTLY one capture at a time.
set -u
cd "$(dirname "$0")/.."
HERE="$(pwd)"
log(){ echo "[$(date -u +%FT%TZ)] $*"; }

log "=== EXP-0201: push"
( cd ../EXP-0201-g17p-float-alu-sixfield && perl -e 'alarm 400; exec @ARGV' bash harness/sync.sh push ) > work/push201.txt 2>&1
log "push rc=$?"
log "=== EXP-0201: verify against its OWN frozen contract (separate step)"
( cd ../EXP-0201-g17p-float-alu-sixfield && perl -e 'alarm 400; exec @ARGV' python3 harness/verify_remote.py ) > work/v201.txt 2>&1
log "verify_remote rc=$?"; tail -3 work/v201.txt
log "=== EXP-0201: verify repo==neo"
( cd ../EXP-0201-g17p-float-alu-sixfield && FILES=$(find harness kernels analysis pinned -type f ! -path '*__pycache__*' 2>/dev/null | sort; echo run.py) && python3 "$HERE/harness/verify_repo_eq_neo.py" . agxre/EXP-0201 $FILES ) > work/repoeq201.txt 2>&1
tail -3 work/repoeq201.txt

log "=== EXP-0201 capture 1/2 (forward)"
sh harness/capture.sh e0201_q01 1200 1500 'cd ~/agxre/EXP-0201 && bash harness/gated_run.sh g17p_quiet01 --order forward'
log "=== EXP-0201 capture 2/2 (reverse)"
sh harness/capture.sh e0201_q02 1200 1500 'cd ~/agxre/EXP-0201 && bash harness/gated_run.sh g17p_quiet02 --order reverse'
log "=== EXP-0201 pull"
( cd ../EXP-0201-g17p-float-alu-sixfield && perl -e 'alarm 600; exec @ARGV' bash harness/sync.sh pull ) > work/pull201.txt 2>&1
log "pull rc=$?"
wc -l ../EXP-0201-g17p-float-alu-sixfield/raw/g17p_quiet01/sweep.jsonl ../EXP-0201-g17p-float-alu-sixfield/raw/g17p_quiet02/sweep.jsonl 2>&1

log "=== EXP-0199: verify repo==neo (no sync.sh exists; the neo tree IS the harness)"
( cd ../EXP-0199-g17p-instruction-level && python3 "$HERE/harness/verify_repo_eq_neo.py" . agxre/EXP-0199 conf.py run.py ) > work/repoeq199.txt 2>&1
tail -2 work/repoeq199.txt
log "=== EXP-0199 capture 1/2 (shuffle)"
sh harness/capture.sh e0199_q01 1500 1800 'cd ~/agxre/EXP-0199 && python3 conf.py g17p_quietconf01 shuffle'
log "=== EXP-0199 capture 2/2 (reverse)"
sh harness/capture.sh e0199_q02 1500 1800 'cd ~/agxre/EXP-0199 && python3 conf.py g17p_quietconf02 reverse'
log "=== EXP-0199 pull"
mkdir -p ../EXP-0199-g17p-instruction-level/raw/g17p_quietconf01 ../EXP-0199-g17p-instruction-level/raw/g17p_quietconf02
for r in g17p_quietconf01 g17p_quietconf02; do
  ALARM=600 sh harness/neo.sh put "user@192.168.170.254:agxre/EXP-0199/raw/$r/*" "../EXP-0199-g17p-instruction-level/raw/$r/" 2>&1 | grep -v Warning
done
wc -l ../EXP-0199-g17p-instruction-level/raw/g17p_quietconf01/sweep.jsonl ../EXP-0199-g17p-instruction-level/raw/g17p_quietconf02/sweep.jsonl 2>&1
log "=== QUEUE 1 COMPLETE"
