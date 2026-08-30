#!/bin/bash
# EXP-0156 remote capture driver, run ON the neo.
#   drive.sh <lease|free> <run_id> <arm-prefix-csv> [lease_wait_s] [extra run.py args...]
# Takes the GPU lease only for the hang-prone groups, per the orchestrator's
# 2026-08-29 policy; MEM and bf16 run free and concurrent.
set -u
cd "$(dirname "$0")/.."
export EXP0156_GIT_REV=7dc67d768ada3c016771923bffd5b9647dd14813
export EXP0156_GIT_DIRTY=1
MODE="$1"; RUN="$2"; ONLY="$3"; shift 3
WAIT=900
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then WAIT="$1"; shift; fi
echo "=== $RUN  mode=$MODE  only=$ONLY  wait=${WAIT}s  $(date -u +%FT%TZ)"
if [ "$MODE" = "lease" ]; then
  ~/agxre/gpulease.sh EXP-0156 "$WAIT" -- python3 harness/run.py --run "$RUN" --only "$ONLY" "$@"
else
  python3 harness/run.py --run "$RUN" --only "$ONLY" "$@"
fi
echo "--- $RUN exit=$? $(date -u +%FT%TZ)"
