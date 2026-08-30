#!/bin/sh
# EXP-0204 device sync.  The password is passed ONLY through SSHPASS in the
# environment; it is never written into this file or any artifact.
# Usage:  SSHPASS=... sh harness/sync.sh push|pull|build|sh '<cmd>'
set -e
NEO=${NEO:-192.168.170.254}
RD=agxre/EXP-0204
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10"
HERE=$(cd "$(dirname "$0")/.." && pwd)
case "$1" in
push)
  sshpass -e ssh $SSHOPT user@$NEO "mkdir -p ~/$RD/work ~/$RD/raw"
  tar czf - -C "$HERE" kernels harness analysis pinned run.py PRE_REGISTRATION.md \
      CAPTURE_CONTRACT.json 2>/dev/null \
    | sshpass -e ssh $SSHOPT user@$NEO "tar xzf - -C ~/$RD"
  ;;
build)
  sshpass -e ssh $SSHOPT user@$NEO "cd ~/$RD && \
    clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation \
      harness/gfrun4.m -o work/gfrun4 && \
    clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation \
      harness/shdump.m -o work/shdump && ls -la work"
  ;;
pull)
  sshpass -e ssh $SSHOPT user@$NEO "cd ~/$RD && tar czf - raw" | tar xzf - -C "$HERE"
  ;;
sh)
  shift
  sshpass -e ssh $SSHOPT user@$NEO "cd ~/$RD && $*"
  ;;
*) echo "usage: sync.sh push|build|pull|sh <cmd>" >&2; exit 2;;
esac
