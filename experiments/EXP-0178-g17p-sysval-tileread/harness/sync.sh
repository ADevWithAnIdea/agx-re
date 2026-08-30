#!/bin/bash
# EXP-0178 push/pull between the repo (on the M4, the evidence store) and the
# A18 Pro / G17P neo (a compute target only).
#
# SSHPASS ONLY -- the password is never written to any file, here or anywhere.
#   export SSHPASS='...' ; harness/sync.sh push|pull|build|shell '<cmd>'
#
# Nothing on the neo is evidence until it is pulled back into raw/ here.
set -euo pipefail
NEO="${NEO:-192.168.10.243}"
USER_="${NEO_USER:-user}"
REMOTE="\$HOME/agxre/EXP-0178"
EXP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SSHOPT=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null
        -o ConnectTimeout=15 -o ServerAliveInterval=10 -o ServerAliveCountMax=3)

case "${1:-}" in
push)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" "mkdir -p $REMOTE/{harness,kernels,analysis,pinned,work/bin,raw}"
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/harness/" "$USER_@$NEO:agxre/EXP-0178/harness/"
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/kernels/" "$USER_@$NEO:agxre/EXP-0178/kernels/"
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/analysis/" "$USER_@$NEO:agxre/EXP-0178/analysis/"
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/pinned/" "$USER_@$NEO:agxre/EXP-0178/pinned/"
  # the persistent compute runner source, unmodified from tools/agxtest
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$EXP/../../tools/agxtest/agxrun_persist.m" "$EXP/../../tools/agxtest/persistrun.py" \
      "$USER_@$NEO:agxre/EXP-0178/work/bin/"
  ;;
build)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" bash -lc "'
    set -e; cd \$HOME/agxre/EXP-0178/work/bin
    clang -fobjc-arc -framework Metal -framework Foundation -o shdump2      ../../harness/shdump2.m
    clang -fobjc-arc -framework Metal -framework Foundation -o rendersweep  ../../harness/rendersweep.m
    clang -fobjc-arc -framework Metal -framework Foundation -o agxrun_persist agxrun_persist.m
    cp ../../harness/rsdrv.py . 2>/dev/null || true
    ls -l shdump2 rendersweep agxrun_persist'"
  ;;
pull)
  sshpass -e rsync -az -e "ssh ${SSHOPT[*]}" \
      "$USER_@$NEO:agxre/EXP-0178/raw/" "$EXP/raw/"
  ;;
pullwork)
  sshpass -e rsync -az --exclude 'arch_*' --exclude 'bin' -e "ssh ${SSHOPT[*]}" \
      "$USER_@$NEO:agxre/EXP-0178/work/" "$EXP/work/"
  ;;
shell)
  sshpass -e ssh "${SSHOPT[@]}" "$USER_@$NEO" bash -lc "'${2}'"
  ;;
*)
  echo "usage: SSHPASS=... $0 push|build|pull|pullwork|shell '<cmd>'" >&2; exit 2;;
esac
