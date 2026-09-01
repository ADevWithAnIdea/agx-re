#!/bin/sh
set -u
RUN="$1"; CAP="${2:-120}"
EXP="$HOME/agxre/EXP-0232-iadd-register-reach"
OLD="$HOME/agxre/EXP-0220"
cd "$EXP" || exit 1
mkdir -p work raw
python3 "$OLD/harness/quietsample.py" --out "work/quiet_$RUN.jsonl" \
        --seconds "$CAP" --interval 0.5 --label "$RUN" >/dev/null 2>&1 &
QPID=$!
sleep 5
python3 "$OLD/harness/gpusnap.py" pre > "work/gpu_pre_$RUN.json" 2>&1
set +e
python3 harness/run232.py --run "$RUN" --order canonical --slots 0,1,2 \
        --arms H --hazard --outroot "$EXP/raw" --timeout 20 --hang-budget 0 \
        > "work/log_$RUN.txt" 2>&1
RC=$?
set -e
python3 "$OLD/harness/gpusnap.py" post > "work/gpu_post_$RUN.json" 2>&1
sleep 5
kill "$QPID" 2>/dev/null || true
sleep 1
if [ -d "raw/$RUN" ]; then
    cp "work/quiet_$RUN.jsonl" "raw/$RUN/procs.jsonl"
    cp "work/gpu_pre_$RUN.json" "raw/$RUN/gpu_pre.json"
    cp "work/gpu_post_$RUN.json" "raw/$RUN/gpu_post.json"
    cp "work/log_$RUN.txt" "raw/$RUN/03_stdout.txt"
    shasum -a 256 harness/run232.py harness/capture232_hazard.sh \
        harness/base_run221.py harness/prog221.py harness/synth221.py \
        harness/runner221.py work/frozen/db.json work/frozen/isadb.py \
        work/frozen/shdump.m work/frozen/agxrun_persist.m \
        work/frozen/agxparse.py > "raw/$RUN/06_harness_sha256.txt"
fi
echo "capture rc=$RC"
tail -20 "work/log_$RUN.txt"
exit "$RC"
