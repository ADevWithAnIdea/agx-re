#!/bin/sh
# Disclosed, bounded EXP-0227 pilot. Run on the Neo after the pre-registration
# commit exists and the separately verified push has completed.
set -u
RUN="$1"
EXP="$HOME/agxre/EXP-0227-low9-length"
OLD="$HOME/agxre/EXP-0220"
cd "$EXP" || exit 1
mkdir -p work/pilot

python3 "$OLD/harness/quietsample.py" --out "work/quiet_$RUN.jsonl" \
        --seconds 90 --interval 2.0 --label "$RUN" >/dev/null 2>&1 &
QPID=$!
python3 "$OLD/harness/gpusnap.py" pre > "work/gpu_pre_$RUN.json" 2>&1

set +e
python3 harness/run227.py --run "$RUN" --order canonical --seed 0 \
    --slots 0,1,2 --arms H1,P1,CTL --outroot work/pilot --timeout 20 \
    --hang-budget 1 > "work/log_$RUN.txt" 2>&1
RC=$?
set -e

python3 "$OLD/harness/gpusnap.py" post > "work/gpu_post_$RUN.json" 2>&1
kill "$QPID" 2>/dev/null || true
sleep 1
if [ -d "work/pilot/$RUN" ]; then
    cp "work/quiet_$RUN.jsonl" "work/pilot/$RUN/procs.jsonl"
    cp "work/gpu_pre_$RUN.json" "work/pilot/$RUN/gpu_pre.json"
    cp "work/gpu_post_$RUN.json" "work/pilot/$RUN/gpu_post.json"
    cp "work/log_$RUN.txt" "work/pilot/$RUN/03_stdout.txt"
fi
echo "pilot rc=$RC"
tail -8 "work/log_$RUN.txt"
exit "$RC"
