#!/bin/sh
set -u
RUN="$1"
ARMS="${2:-H1,CTL}"
EXP="$HOME/agxre/EXP-0226-ilogic-canonical"
OLD="$HOME/agxre/EXP-0220"
cd "$EXP" || exit 1
mkdir -p work/pilot
python3 "$OLD/harness/gpusnap.py" pre > "work/gpu_pre_$RUN.json" 2>&1
set +e
python3 harness/run226.py --run "$RUN" --order canonical --seed 0 \
    --slots 0,1,2 --arms "$ARMS" --outroot "$EXP/work/pilot" --timeout 20 \
    > "work/log_$RUN.txt" 2>&1
RC=$?
set -e
python3 "$OLD/harness/gpusnap.py" post > "work/gpu_post_$RUN.json" 2>&1
echo "pilot rc=$RC"
tail -8 "work/log_$RUN.txt"
exit "$RC"
