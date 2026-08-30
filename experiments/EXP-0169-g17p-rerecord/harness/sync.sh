#!/bin/bash
# EXP-0169 -- push authored harness/kernels to the neo (A18 Pro / G17P) and pull
# raw evidence back. NEVER contains a credential: `SSHPASS` must be exported by
# the caller (NEO-TARGET-BRIEF.md). Nothing on the neo is evidence until it is
# pulled back here, so pull after every milestone.
#
#   export SSHPASS='...'; harness/sync.sh push
#   export SSHPASS='...'; harness/sync.sh pull <run_id>
set -u
NEO="${NEO:-192.168.10.243}"
EXPDIR="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="agxre/EXP-0169"
SSHOPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"

run() { perl -e 'alarm shift; exec @ARGV' "$@"; }

case "${1:-}" in
push)
  run 120 sshpass -e ssh $SSHOPTS "user@$NEO" \
      "mkdir -p ~/$REMOTE/harness ~/$REMOTE/kernels ~/$REMOTE/raw ~/$REMOTE/work"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/harness/*.py "user@$NEO:$REMOTE/harness/"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/kernels/*.metal "user@$NEO:$REMOTE/kernels/"
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
      "user@$NEO:$REMOTE/work/anchors/arm_resolution.json" \
      "$EXPDIR/work/anchors/"
  run 300 sshpass -e scp $SSHOPTS "user@$NEO:$REMOTE/work/calib.json" \
      "$EXPDIR/work/" || true
  ;;
frozen)
  # pull the EXACT db.json / isadb.py the hardware ran against, so verdicts are
  # keyed to the descriptor the device actually saw and not to a drifting repo
  # copy (EXP-0165 is editing tools/agx-isa/db.json concurrently).
  mkdir -p "$EXPDIR/work/frozen"
  run 300 sshpass -e scp $SSHOPTS \
      "user@$NEO:agxre/tools/agx-isa/db.json" \
      "user@$NEO:agxre/tools/agx-isa/isadb.py" \
      "$EXPDIR/work/frozen/"
  ;;
*) echo "usage: $0 push | pull <run_id> | pullwork | frozen" >&2; exit 2;;
esac
