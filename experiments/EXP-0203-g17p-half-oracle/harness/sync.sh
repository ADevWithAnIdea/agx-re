#!/bin/sh
# EXP-0203 push/pull to the neo (A18 Pro / G17P).
#
# The password is taken from the SSHPASS environment variable ONLY. It is never written to
# this file, to any other file, or to any committed artifact.
#
# After every push, harness/verify_remote.py MUST be run: a push that silently fails inside
# a `&&` chain is indistinguishable from success in the exit code, and that has already cost
# this project a gated run against a stale harness (EXP-0179).
set -e
NEO="${NEO:-192.168.170.254}"
REM="agxre/EXP-0203"
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

case "$1" in
  push)
    sshpass -e ssh $SSHOPT "user@$NEO" "mkdir -p $REM/harness $REM/kernels $REM/analysis $REM/work/frozen $REM/work/stub $REM/raw"
    sshpass -e scp $SSHOPT "$HERE"/harness/*.py       "user@$NEO:$REM/harness/"
    sshpass -e scp $SSHOPT "$HERE"/kernels/*.metal    "user@$NEO:$REM/kernels/"
    sshpass -e scp $SSHOPT "$HERE"/analysis/*.py      "user@$NEO:$REM/analysis/"
    sshpass -e scp $SSHOPT "$HERE"/work/frozen/db.json "$HERE"/work/frozen/isadb.py "user@$NEO:$REM/work/frozen/"
    sshpass -e scp $SSHOPT "$HERE"/work/stub/fakerunner.py "user@$NEO:$REM/work/stub/"
    ;;
  pull)
    test -n "$2" || { echo "usage: sync.sh pull <run_id>"; exit 2; }
    mkdir -p "$HERE/raw/$2"
    sshpass -e scp $SSHOPT "user@$NEO:$REM/raw/$2/*" "$HERE/raw/$2/"
    ;;
  *) echo "usage: sync.sh push | sync.sh pull <run_id>"; exit 2;;
esac
