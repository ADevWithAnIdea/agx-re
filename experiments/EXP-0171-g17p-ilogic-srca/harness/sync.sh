#!/bin/bash
# EXP-0171 -- push authored harness/kernels/frozen-db to the neo (A18 Pro /
# G17P) and pull raw evidence back. NEVER contains a credential: `SSHPASS` must
# be exported by the caller.
#
#   export SSHPASS='...'; harness/sync.sh push
#   export SSHPASS='...'; harness/sync.sh pull <run_id>
#   export SSHPASS='...'; harness/sync.sh pullwork
set -u
NEO="${NEO:-192.168.10.243}"
EXPDIR="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="agxre/EXP-0171"
SSHOPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=15"

run() { perl -e 'alarm shift; exec @ARGV' "$@"; }

case "${1:-}" in
push)
  run 120 sshpass -e ssh $SSHOPTS "user@$NEO" \
      "mkdir -p ~/$REMOTE/harness ~/$REMOTE/kernels ~/$REMOTE/raw ~/$REMOTE/work/frozen ~/$REMOTE/analysis"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/harness/*.py "user@$NEO:$REMOTE/harness/"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/kernels/*.metal "user@$NEO:$REMOTE/kernels/"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/work/frozen/* "user@$NEO:$REMOTE/work/frozen/"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/analysis/*.py "user@$NEO:$REMOTE/analysis/" || true
  ;;
pull)
  RUN="${2:?run id}"
  mkdir -p "$EXPDIR/raw/$RUN"
  run 900 sshpass -e scp $SSHOPTS -r "user@$NEO:$REMOTE/raw/$RUN/." "$EXPDIR/raw/$RUN/"
  ;;
pullwork)
  mkdir -p "$EXPDIR/work/anchors"
  run 300 sshpass -e scp $SSHOPTS \
      "user@$NEO:$REMOTE/work/anchors/anchor_report.json" \
      "$EXPDIR/work/anchors/anchor_report.json"
  ;;
*) echo "usage: $0 push | pull <run_id> | pullwork" >&2; exit 2;;
esac
