#!/bin/sh
# EXP-0156 push/pull helper for the G17P test target (the "neo").
#
# Credentials are taken from the ENVIRONMENT ONLY ($SSHPASS, $NEO) and are never
# written into this repository (NEO-TARGET-BRIEF.md).  Every remote call is
# wrapped in a hard timeout so a wedged neo cannot hang the dispatch.
#
#   NEO=192.168.10.243 SSHPASS=... harness/sync.sh push
#   NEO=192.168.10.243 SSHPASS=... harness/sync.sh pull <run_id>
#   NEO=192.168.10.243 SSHPASS=... harness/sync.sh sh '<remote command>'
set -e
EXP="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$EXP/../.." && pwd)"
NAME="$(basename "$EXP")"
RD="agxre/experiments/$NAME"
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10"
T() { perl -e 'alarm shift; exec @ARGV' "$1" shift 2>/dev/null; }
rsh() { perl -e 'alarm 600; exec @ARGV' sshpass -e ssh $SSHOPT "user@$NEO" "$@"; }
rscp() { perl -e 'alarm 900; exec @ARGV' sshpass -e scp $SSHOPT "$@"; }

case "$1" in
push)
  rsh "mkdir -p $RD/harness $RD/kernels $RD/analysis $RD/raw $RD/work"
  rscp -q "$EXP"/harness/*.py "$EXP"/harness/*.sh "user@$NEO:$RD/harness/"
  rscp -q "$EXP"/kernels/*.metal "user@$NEO:$RD/kernels/"
  rscp -q "$EXP"/PRE_REGISTRATION.md "user@$NEO:$RD/" 2>/dev/null || true
  rscp -q "$EXP"/CAPTURE_CONTRACT.json "user@$NEO:$RD/" 2>/dev/null || true
  echo "PUSHED -> $RD"
  ;;
pull)
  mkdir -p "$EXP/raw"
  rscp -q -r "user@$NEO:$RD/raw/$2" "$EXP/raw/"
  echo "PULLED raw/$2"
  ;;
sh)
  shift; rsh "$@"
  ;;
*) echo "usage: sync.sh push|pull <run>|sh <cmd>" >&2; exit 2;;
esac
