#!/bin/bash
# EXP-0156 remote capture driver, run ON the neo.
#   drive.sh <lease|free> <run_id> <arm-prefix-csv>
# Takes the GPU lease only for the hang-prone groups, per the orchestrator's
# 2026-08-29 policy; MEM and bf16 run free and concurrent.
set -u
cd "$(dirname "$0")/.."
export EXP0156_GIT_REV=7dc67d768ada3c016771923bffd5b9647dd14813
export EXP0156_GIT_DIRTY=1
MODE="$1"; RUN="$2"; ONLY="$3"; shift 3
echo "=== $RUN  mode=$MODE  only=$ONLY  $(date -u +%FT%TZ)"
if [ "$MODE" = "lease" ]; then
  ~/agxre/gpulease.sh EXP-0156 900 -- python3 harness/run.py --run "$RUN" --only "$ONLY" "$@"
else
  python3 harness/run.py --run "$RUN" --only "$ONLY" "$@"
fi
