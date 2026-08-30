#!/bin/bash
# EXP-0174 -- push authored harness/kernels to the neo (A18 Pro / G17P) and pull
# raw evidence back.
#
# NEVER CONTAINS A CREDENTIAL. `SSHPASS` must be exported by the caller; it is
# not written to this file, to any log, or to any command line.
#
#   export SSHPASS='...'; harness/sync.sh push
#
# `push` pins a PRIVATE COPY of the toolchain under ~/agxre/EXP-0174/tools, and
# copies work/frozen/{db.json,isadb.py} -- the sha256-pinned snapshot the
# harness resolves EXCLUSIVELY (isa_helpers._find_isadb has no fallback). The
# neo's SHARED ~/agxre/tools/agx-isa/db.json is STALE (1036 fields vs 1062).
set -u
NEO="${NEO:-192.168.10.243}"
EXPDIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$EXPDIR/../.." && pwd)"
REMOTE="agxre/EXP-0174"
SSHOPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=15"

run() { perl -e 'alarm shift; exec @ARGV' "$@"; }

case "${1:-}" in
push)
  run 120 sshpass -e ssh $SSHOPTS "user@$NEO" \
      "mkdir -p ~/$REMOTE/harness ~/$REMOTE/kernels ~/$REMOTE/analysis ~/$REMOTE/raw ~/$REMOTE/work/frozen ~/$REMOTE/tools"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/harness/*.py "user@$NEO:$REMOTE/harness/"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/kernels/*.metal "user@$NEO:$REMOTE/kernels/"
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/work/frozen/db.json "$EXPDIR"/work/frozen/isadb.py \
      "user@$NEO:$REMOTE/work/frozen/"
  run 300 sshpass -e scp $SSHOPTS -r "$REPO/tools/agx-isa" "$REPO/tools/shdump" \
      "$REPO/tools/agxtest" "user@$NEO:$REMOTE/tools/"
  ;;
pusha)
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/analysis/*.py "user@$NEO:$REMOTE/analysis/"
  ;;
pushh)
  run 300 sshpass -e scp $SSHOPTS "$EXPDIR"/harness/*.py "user@$NEO:$REMOTE/harness/"
  ;;
build)
  run 900 sshpass -e ssh $SSHOPTS "user@$NEO" "cd ~/$REMOTE/tools && \
      xcrun clang -fobjc-arc -O2 -framework Metal -framework Foundation \
        -o shdump/shdump shdump/shdump.m && \
      xcrun clang -fobjc-arc -O2 -framework Metal -framework Foundation \
        -o agxtest/agxrun_persist agxtest/agxrun_persist.m && \
      echo BUILD_OK"
  ;;
verify)
  run 120 sshpass -e ssh $SSHOPTS "user@$NEO" \
      "cd ~/$REMOTE && shasum -a 256 work/frozen/db.json work/frozen/isadb.py"
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
sh)
  shift
  run "${ALARM:-300}" sshpass -e ssh $SSHOPTS "user@$NEO" "$@"
  ;;
*) echo "usage: $0 push | pusha | pushh | build | verify | pull <id> | pullpre <id> | sh <cmd>" >&2; exit 2;;
esac
