#!/bin/bash
# EXP-0161 -- push the authored harness/kernels to the neo, or pull raw/ back.
#   SSHPASS=... harness/sync.sh push|pull
set -euo pipefail
NEO="${NEO:-192.168.10.243}"
EXPD="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="~/agxre/EXP-0161"
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15"
case "${1:-push}" in
  push)
    perl -e 'alarm 120; exec @ARGV' sshpass -e ssh $SSHOPT user@"$NEO" "mkdir -p $REMOTE/{harness,kernels,analysis,raw,work/frozen}"
    perl -e 'alarm 300; exec @ARGV' sshpass -e scp $SSHOPT -q \
        "$EXPD"/harness/*.py "$EXPD"/harness/*.sh user@"$NEO":"$REMOTE"/harness/
    perl -e 'alarm 300; exec @ARGV' sshpass -e scp $SSHOPT -q \
        "$EXPD"/kernels/*.metal user@"$NEO":"$REMOTE"/kernels/
    perl -e 'alarm 300; exec @ARGV' sshpass -e scp $SSHOPT -q \
        "$EXPD"/work/frozen/db.json "$EXPD"/work/frozen/isadb.py \
        "$EXPD"/work/frozen/validation.json user@"$NEO":"$REMOTE"/work/frozen/
    ;;
  pull)
    mkdir -p "$EXPD/raw" "$EXPD/work"
    perl -e 'alarm 900; exec @ARGV' sshpass -e scp $SSHOPT -qr \
        user@"$NEO":"$REMOTE"/raw/. "$EXPD"/raw/ || true
    perl -e 'alarm 900; exec @ARGV' sshpass -e scp $SSHOPT -q \
        user@"$NEO":"$REMOTE"/work/anchors/anchor_report.json "$EXPD"/work/ 2>/dev/null || true
    ;;
  *) echo "usage: sync.sh push|pull" >&2; exit 2;;
esac
echo "sync $1 ok"
