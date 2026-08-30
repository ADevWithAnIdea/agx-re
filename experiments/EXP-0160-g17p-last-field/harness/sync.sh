#!/bin/bash
# EXP-0160 sync: push authored inputs to the neo, pull raw evidence back.
# Usage: SSHPASS=... harness/sync.sh push|pull [runid]
set -euo pipefail
NEO="${NEO:-192.168.10.243}"
EXPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE="agxre/EXP-0160"
SSH=(sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 "user@$NEO")
SCP=(sshpass -e scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 -r)
case "${1:?push|pull}" in
push)
  perl -e 'alarm 120; exec @ARGV' "${SSH[@]}" "mkdir -p ~/$REMOTE/{harness,kernels,analysis,work,raw} ~/$REMOTE/tools"
  perl -e 'alarm 300; exec @ARGV' "${SCP[@]}" "$EXPDIR/harness" "$EXPDIR/kernels" "$EXPDIR/analysis" "user@$NEO:$REMOTE/"
  # pin our own copy of the toolchain so a sibling agent editing the shared
  # ~/agxre/tools cannot change what this experiment ran against
  perl -e 'alarm 300; exec @ARGV' "${SCP[@]}" "$EXPDIR/../../tools/agx-isa" "$EXPDIR/../../tools/agxtest/persistrun.py" "user@$NEO:$REMOTE/tools/"
  ;;
pull)
  R="${2:?runid}"
  mkdir -p "$EXPDIR/raw/$R"
  perl -e 'alarm 600; exec @ARGV' "${SCP[@]}" "user@$NEO:$REMOTE/raw/$R/." "$EXPDIR/raw/$R/"
  ;;
esac
