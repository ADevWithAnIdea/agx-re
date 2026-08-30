#!/bin/bash
# EXP-0179 -- push authored harness/kernels to the neo (A18 Pro / G17P) and pull
# raw evidence back.
#
# NEVER CONTAINS A CREDENTIAL. `SSHPASS` must be exported by the caller; it is
# not written to this file, to any log, or to any command line.
#
#   export SSHPASS='...'; harness/sync.sh push
#
# `push` pins a PRIVATE COPY of the toolchain under ~/agxre/EXP-0179/tools and
# copies work/frozen/{db.json,isadb.py} -- the sha256-pinned snapshot the harness
# resolves EXCLUSIVELY (isa_helpers._find_isadb has NO fallback). The neo's
# SHARED ~/agxre/tools/agx-isa/db.json is STALE and a path-search fallback
# silently resolved it for another experiment on 2026-08-30.
set -u
NEO="${NEO:-192.168.10.243}"
EXPDIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$EXPDIR/../.." && pwd)"
REMOTE="agxre/EXP-0179"
SSHOPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=15"

run() { perl -e 'alarm shift; exec @ARGV' "$@"; }

case "${1:-}" in
push)
  run 120 sshpass -e ssh $SSHOPTS "user@$NEO" \
      "mkdir -p ~/$REMOTE/harness ~/$REMOTE/kernels/census ~/$REMOTE/analysis ~/$REMOTE/raw/prefreeze ~/$REMOTE/work/frozen ~/$REMOTE/tools"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/harness/*.py "$EXPDIR"/harness/*.m "user@$NEO:$REMOTE/harness/"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/kernels/*.metal "user@$NEO:$REMOTE/kernels/"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/kernels/census/*.metal "user@$NEO:$REMOTE/kernels/census/"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/work/frozen/db.json "$EXPDIR"/work/frozen/isadb.py \
      "user@$NEO:$REMOTE/work/frozen/"
  run 600 sshpass -e scp $SSHOPTS -r "$REPO/tools/agx-isa" "$REPO/tools/shdump" \
      "$REPO/tools/agxtest" "user@$NEO:$REMOTE/tools/"
  ;;
pushh)
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/harness/*.py "user@$NEO:$REMOTE/harness/"
  ;;
pusha)
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/analysis/*.py "user@$NEO:$REMOTE/analysis/"
  ;;
pushk)
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/kernels/*.metal "user@$NEO:$REMOTE/kernels/"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/kernels/census/*.metal "user@$NEO:$REMOTE/kernels/census/"
  ;;
build)
  run 900 sshpass -e ssh $SSHOPTS "user@$NEO" "cd ~/$REMOTE && \
      xcrun clang -fobjc-arc -O2 -framework Metal -framework Foundation \
        -o tools/shdump/shdump tools/shdump/shdump.m && \
      xcrun clang -fobjc-arc -O2 -framework Metal -framework Foundation \
        -o tools/agxtest/agxrun_persist tools/agxtest/agxrun_persist.m && \
      xcrun clang -fobjc-arc -O2 -framework Metal -framework Foundation \
        -o harness/fndump harness/fndump.m && \
      echo BUILD_OK"
  ;;
verify)
  run 120 sshpass -e ssh $SSHOPTS "user@$NEO" \
      "cd ~/$REMOTE && shasum -a 256 work/frozen/db.json work/frozen/isadb.py harness/*.py"
  ;;
pull)
  RUN="${2:?run id}"
  mkdir -p "$EXPDIR/raw/$RUN"
  run 1800 sshpass -e scp $SSHOPTS -r "user@$NEO:$REMOTE/raw/$RUN/." "$EXPDIR/raw/$RUN/"
  ;;
pullpre)
  RUN="${2:?run id}"
  mkdir -p "$EXPDIR/raw/prefreeze/$RUN"
  run 1800 sshpass -e scp $SSHOPTS -r "user@$NEO:$REMOTE/raw/prefreeze/$RUN/." \
      "$EXPDIR/raw/prefreeze/$RUN/"
  ;;
pullwork)
  run 300 sshpass -e scp $SSHOPTS "user@$NEO:$REMOTE/work/addendum.json" "$EXPDIR/work/addendum.json"
  ;;
sh)
  shift
  run "${ALARM:-300}" sshpass -e ssh $SSHOPTS "user@$NEO" "$@"
  ;;
*) echo "usage: $0 push|pushh|pusha|pushk|build|verify|pull <id>|pullpre <id>|pullwork|sh <cmd>" >&2; exit 2;;
esac
