#!/bin/bash
# EXP-0168 -- push authored harness/kernels to the neo (A18 Pro / G17P) and pull
# raw evidence back.
#
# NEVER CONTAINS A CREDENTIAL. `SSHPASS` must be exported by the caller; it is
# not written to this file, to any log, or to any command line.
#
#   export SSHPASS='...'; harness/sync.sh push
#   export SSHPASS='...'; harness/sync.sh pull <run_id>
#
# `push` also pins a PRIVATE COPY of the toolchain under ~/agxre/EXP-0168/tools
# so that a sibling agent editing the shared ~/agxre/tools cannot change what
# this experiment ran against. EXP-0144's frozen matrix hash stopped reproducing
# for exactly that reason: its case labels were read from a db.json that later
# moved. (Template: EXP-0160/harness/sync.sh.)
set -u
NEO="${NEO:-192.168.10.243}"
EXPDIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$EXPDIR/../.." && pwd)"
REMOTE="agxre/EXP-0168"
SSHOPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=15"

run() { perl -e 'alarm shift; exec @ARGV' "$@"; }

case "${1:-}" in
push)
  run 120 sshpass -e ssh $SSHOPTS "user@$NEO" \
      "mkdir -p ~/$REMOTE/harness ~/$REMOTE/kernels ~/$REMOTE/analysis ~/$REMOTE/raw ~/$REMOTE/work ~/$REMOTE/tools"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/harness/*.py "user@$NEO:$REMOTE/harness/"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/kernels/*.metal "user@$NEO:$REMOTE/kernels/"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/analysis/*.py "user@$NEO:$REMOTE/analysis/"
  run 300 sshpass -e scp $SSHOPTS -r "$REPO/tools/agx-isa" "$REPO/tools/shdump" \
      "$REPO/tools/agxtest" "user@$NEO:$REMOTE/tools/"
  ;;
build)
  run 600 sshpass -e ssh $SSHOPTS "user@$NEO" "cd ~/$REMOTE/tools && \
      xcrun clang -fobjc-arc -O2 -framework Metal -framework Foundation \
        -o shdump/shdump shdump/shdump.m && \
      xcrun clang -fobjc-arc -O2 -framework Metal -framework Foundation \
        -o agxtest/agxrun_persist agxtest/agxrun_persist.m && \
      echo BUILD_OK"
  ;;
frozen)
  # pull the EXACT db.json/isadb.py the hardware will run against into
  # work/frozen/, so verdicts are re-keyed against the descriptor the device
  # actually saw and never against a later repo state
  mkdir -p "$EXPDIR/work/frozen"
  run 300 sshpass -e scp $SSHOPTS \
      "user@$NEO:$REMOTE/tools/agx-isa/db.json" \
      "user@$NEO:$REMOTE/tools/agx-isa/isadb.py" \
      "$EXPDIR/work/frozen/"
  shasum -a 256 "$EXPDIR"/work/frozen/*
  ;;
pull)
  RUN="${2:?run id}"
  mkdir -p "$EXPDIR/raw/$RUN"
  run 900 sshpass -e scp $SSHOPTS -r "user@$NEO:$REMOTE/raw/$RUN/." "$EXPDIR/raw/$RUN/"
  ;;
pullwork)
  mkdir -p "$EXPDIR/work"
  run 300 sshpass -e scp $SSHOPTS \
      "user@$NEO:$REMOTE/work/anchors/anchor_report.json" \
      "user@$NEO:$REMOTE/work/anchors/anchor_index.json" \
      "user@$NEO:$REMOTE/work/casematrix.json" "$EXPDIR/work/"
  ;;
sh)
  shift
  run "${ALARM:-300}" sshpass -e ssh $SSHOPTS "user@$NEO" "$@"
  ;;
*) echo "usage: $0 push | build | frozen | pull <run_id> | pullwork | sh <cmd>" >&2; exit 2;;
esac
