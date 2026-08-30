#!/bin/bash
# EXP-0207 push/pull between the repo (on the M4, the evidence store) and the
# A18 Pro / G17P neo (a compute target only).
#
# SSHPASS ONLY -- the password is never written to any file, here or anywhere.
#   export SSHPASS='...' ; harness/sync.sh push|build|pull|pullwork|shell '<cmd>'
#
# Nothing on the neo is evidence until it is pulled back into raw/ here.
set -euo pipefail
NEO="${NEO:-192.168.170.254}"
USER_="${NEO_USER:-user}"
REMOTE="\$HOME/agxre/EXP-0207"
EXP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSHOPT=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
        -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=3)

case "${1:-}" in
push)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" "mkdir -p $REMOTE/harness $REMOTE/kernels $REMOTE/analysis $REMOTE/pinned $REMOTE/work/bin $REMOTE/raw"
  for d in harness kernels analysis pinned; do
    sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" "$EXP/$d/" "$USER_@$NEO:agxre/EXP-0207/$d/"
  done
  # the persistent compute runner, unmodified from tools/agxtest
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/../../tools/agxtest/agxrun_persist.m" "$EXP/../../tools/agxtest/persistrun.py" \
      "$USER_@$NEO:agxre/EXP-0207/work/bin/"
  ;;
build)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" bash -lc "'
    set -e; cd \$HOME/agxre/EXP-0207/work/bin
    clang -fobjc-arc -framework Metal -framework Foundation -o shdump207       ../../harness/shdump207.m
    clang -fobjc-arc -framework Metal -framework Foundation -o shdump_mesh207  ../../harness/shdump_mesh207.m
    clang -fobjc-arc -framework Metal -framework Foundation -o rendersweep207  ../../harness/rendersweep207.m
    clang -fobjc-arc -framework Metal -framework Foundation -o meshsweep207    ../../harness/meshsweep207.m
    clang -fobjc-arc -framework Metal -framework Foundation -o agxrun_persist  agxrun_persist.m
    ls -l shdump207 shdump_mesh207 rendersweep207 meshsweep207 agxrun_persist'"
  ;;
pull)
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$USER_@$NEO:agxre/EXP-0207/raw/" "$EXP/raw/"
  ;;
pullwork)
  sshpass -e rsync -az --exclude 'arch_*' --exclude 'bin' -e "ssh ${SSHOPT[*]}" \
      "$USER_@$NEO:agxre/EXP-0207/work/" "$EXP/work/"
  ;;
shell)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" bash -lc "'${2}'"
  ;;
*)
  echo "usage: SSHPASS=... $0 push|build|pull|pullwork|shell '<cmd>'" >&2; exit 2;;
esac
