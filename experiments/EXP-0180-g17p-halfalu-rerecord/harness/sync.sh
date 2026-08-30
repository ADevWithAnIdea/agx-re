#!/bin/bash
# EXP-0180 push/pull. SSHPASS only -- the password is NEVER written to any file.
#   export SSHPASS='...' ; harness/sync.sh push
set -euo pipefail
NEO="${NEO:-192.168.10.243}"
USR="${NEO_USER:-user}"
EXPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE="agxre/EXP-0180"
S="sshpass -e ssh -o StrictHostKeyChecking=no -o ConnectTimeout=20"
SCP="sshpass -e scp -o StrictHostKeyChecking=no -o ConnectTimeout=20 -r"

case "${1:-}" in
  push)
    $S "$USR@$NEO" "mkdir -p $REMOTE/work $REMOTE/raw"
    $SCP "$EXPDIR/harness" "$EXPDIR/kernels" "$EXPDIR/analysis" "$USR@$NEO:$REMOTE/"
    # the PINNED ISA travels with the experiment; the neo's shared copy is never used
    $SCP "$EXPDIR/work/frozen" "$EXPDIR/work/stub" "$USR@$NEO:$REMOTE/work/"
    $SCP "$EXPDIR/work/target_rows.json" "$USR@$NEO:$REMOTE/work/"
    ;;
  pull)   $SCP "$USR@$NEO:$REMOTE/raw/${2:?run id}" "$EXPDIR/raw/" ;;
  pullwork) $SCP "$USR@$NEO:$REMOTE/work" "$EXPDIR/work_from_neo" ;;
  *) echo "usage: $0 {push|pull <run_id>|pullwork}" >&2; exit 2 ;;
esac
