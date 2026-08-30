#!/bin/bash
# EXP-0200 push/build/pull between the repo (on the M4, the evidence store) and
# the A18 Pro / G17P neo (a compute target only).
#
#   export SSHPASS='...'    # SSHPASS ONLY -- never written to any file
#   harness/sync200.sh push | build | pull | shell '<cmd>'
#
# Nothing on the neo is evidence until it is pulled back into raw/ here.
#
# `verify_remote200.py` exists as a SEPARATE step and MUST NOT be chained behind
# the push it checks: SUBAGENT_BRIEF records two failures on 2026-08-30 where a
# state-changing step behind `&&` silently did not run while the exit code
# looked clean, and EXP-0179 burned a run id executing a stale harness that way.
set -euo pipefail
NEO="${NEO:-192.168.170.254}"
USER_="${NEO_USER:-user}"
REMOTE="\$HOME/agxre/EXP-0200"
EXP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSHOPT=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
        -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=3)

case "${1:-}" in
push)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" \
    "mkdir -p $REMOTE/harness $REMOTE/kernels $REMOTE/analysis $REMOTE/work/bin \
              $REMOTE/raw $REMOTE/t1/harness $REMOTE/t1/kernels \
              $REMOTE/t1/analysis $REMOTE/t1/pinned $REMOTE/t1/work/bin \
              $REMOTE/t1/raw"
  for d in harness kernels analysis; do
    sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/$d/" "$USER_@$NEO:agxre/EXP-0200/$d/"
  done
  for d in harness kernels analysis pinned; do
    sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/t1/$d/" "$USER_@$NEO:agxre/EXP-0200/t1/$d/"
  done
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/run200.py" "$EXP/CAPTURE_CONTRACT.json" \
      "$USER_@$NEO:agxre/EXP-0200/"
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/t1/run.py" "$EXP/t1/CAPTURE_CONTRACT.json" \
      "$USER_@$NEO:agxre/EXP-0200/t1/"
  ;;
build)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" bash -lc "'
    set -e; cd \$HOME/agxre/EXP-0200/work/bin
    clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation \
        -o shdump             ../../t1/pinned/shdump.m
    clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation \
        -o agxrun_persist_as  ../../t1/harness/agxrun_persist_as.m
    cd \$HOME/agxre/EXP-0200/t1/work/bin
    clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation \
        -o shdump             ../../pinned/shdump.m
    clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation \
        -o shdump_mesh        ../../pinned/shdump_mesh.m
    clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation \
        -o agxrun_persist_as  ../../harness/agxrun_persist_as.m
    ls -l \$HOME/agxre/EXP-0200/work/bin \$HOME/agxre/EXP-0200/t1/work/bin'"
  ;;
pull)
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$USER_@$NEO:agxre/EXP-0200/raw/" "$EXP/raw/"
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$USER_@$NEO:agxre/EXP-0200/t1/raw/" "$EXP/t1/raw/"
  ;;
pullarms)
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$USER_@$NEO:agxre/EXP-0200/harness/arms200.json" "$EXP/harness/arms200.json"
  ;;
shell)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" bash -lc "'${2}'"
  ;;
*)
  echo "usage: SSHPASS=... $0 push|build|pull|pullarms|shell '<cmd>'" >&2
  exit 2;;
esac
