#!/bin/bash
# EXP-0205 push/build/pull between the repo (on the M4, the evidence store) and
# the A18 Pro / G17P neo (a compute target only).
#
#   export SSHPASS='...'      # SSHPASS ONLY -- never written into any file
#   harness/sync.sh push | build | pull | pullharness | pullwork | shell '<cmd>'
#
# Nothing on the neo is evidence until it is pulled back into raw/ here.
#
# DO NOT CHAIN A CAPTURE BEHIND `sync.sh push && ...`.  EXP-0179's push returned
# non-zero inside a chained command and a gated pass executed against the STALE
# harness -- 6 cases instead of 8 -- burning a run id.  Push, then run
# `harness/verify_remote.py` as its OWN step and check its exit code.
set -euo pipefail
NEO="${NEO:-192.168.170.254}"
USER_="${NEO_USER:-user}"
EXP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSHOPT=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
        -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=3)

case "${1:-}" in
push)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" \
    'mkdir -p $HOME/agxre/EXP-0205/{harness,kernels,analysis,pinned,work/bin,raw}'
  for d in harness kernels analysis pinned; do
    sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/$d/" "$USER_@$NEO:agxre/EXP-0205/$d/"
  done
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/run.py" "$USER_@$NEO:agxre/EXP-0205/"
  ;;
pushcontract)
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/CAPTURE_CONTRACT.json" "$USER_@$NEO:agxre/EXP-0205/"
  ;;
build)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" bash -lc "'
    set -e; cd \$HOME/agxre/EXP-0205/work/bin
    clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation \
        -o shdump         ../../pinned/shdump.m
    clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation \
        -o agxrun_persist ../../pinned/agxrun_persist.m
    ls -l shdump agxrun_persist'"
  ;;
pull)
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$USER_@$NEO:agxre/EXP-0205/raw/" "$EXP/raw/"
  ;;
pullharness)
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$USER_@$NEO:agxre/EXP-0205/harness/arms205.json" "$EXP/harness/arms205.json"
  ;;
pullwork)
  sshpass -e rsync -az --exclude 'bin' --exclude 'arch' --exclude 'splice' \
      -e "ssh ${SSHOPT[*]}" \
      "$USER_@$NEO:agxre/EXP-0205/work/" "$EXP/work/"
  ;;
shell)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" bash -lc "'${2}'"
  ;;
*)
  echo "usage: SSHPASS=... $0 push|pushcontract|build|pull|pullharness|pullwork|shell '<cmd>'" >&2
  exit 2;;
esac
