#!/bin/bash
# EXP-0206 push/build/pull between the repo (on the M4, the evidence store) and
# the A18 Pro / G17P neo (a compute target only).
#
#   export SSHPASS='...'    # SSHPASS ONLY -- never written to any file
#   harness/sync.sh push | build | pull | pullharness | shell '<cmd>'
#
# Nothing on the neo is evidence until it is pulled back into raw/ here.
#
# DO NOT chain a capture behind `sync.sh push && ...`. EXP-0179's push returned
# non-zero inside a chained command and a gated pass executed against the STALE
# pre-amendment harness -- 6 cases instead of 8, burning a run id. Push, then run
# `python3 harness/verify_remote.py ...` on its own and read its exit code.
set -euo pipefail
NEO="${NEO:-192.168.170.254}"
USER_="${NEO_USER:-user}"
REMOTE="\$HOME/agxre/EXP-0206"
EXP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSHOPT=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
        -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=3)

case "${1:-}" in
push)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" \
    "mkdir -p $REMOTE/harness $REMOTE/kernels $REMOTE/analysis $REMOTE/pinned $REMOTE/work/bin $REMOTE/raw"
  for d in harness kernels analysis pinned; do
    sshpass -e rsync -az --exclude '__pycache__' -e "ssh ${SSHOPT[*]}" \
      "$EXP/$d/" "$USER_@$NEO:agxre/EXP-0206/$d/"
  done
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/run.py" "$USER_@$NEO:agxre/EXP-0206/"
  if [ -f "$EXP/CAPTURE_CONTRACT.json" ]; then
    sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/CAPTURE_CONTRACT.json" "$USER_@$NEO:agxre/EXP-0206/"
  fi
  ;;
build)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" bash -lc "'
    set -e; cd \$HOME/agxre/EXP-0206/work/bin
    clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation \
        -o shdump         ../../pinned/shdump.m
    clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation \
        -o agxrun_persist ../../pinned/agxrun_persist.m
    ls -l shdump agxrun_persist'"
  ;;
pull)
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$USER_@$NEO:agxre/EXP-0206/raw/" "$EXP/raw/"
  ;;
pullharness)
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$USER_@$NEO:agxre/EXP-0206/harness/arms206.json" "$EXP/harness/arms206.json"
  ;;
shell)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" bash -lc "'${2}'"
  ;;
*)
  echo "usage: SSHPASS=... $0 push|build|pull|pullharness|shell '<cmd>'" >&2
  exit 2;;
esac
