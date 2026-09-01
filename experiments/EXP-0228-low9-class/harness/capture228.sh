#!/bin/sh
# Formal EXP-0228 Amendment-01 capture.
set -u
RUN="$1"; ORDER="$2"; SEED="$3"; CAP="${4:-180}"
EXP="$HOME/agxre/EXP-0228-low9-class"
OLD="$HOME/agxre/EXP-0220"
cd "$EXP" || exit 1
mkdir -p work raw
python3 "$OLD/harness/quietsample.py" --out "work/quiet_$RUN.jsonl" \
        --seconds "$CAP" --interval 0.25 --label "$RUN" >/dev/null 2>&1 &
QPID=$!
sleep 5
python3 "$OLD/harness/gpusnap.py" pre > "work/gpu_pre_$RUN.json" 2>&1
set +e
( python3 harness/run228_full.py --run "$RUN" --order "$ORDER" --seed "$SEED" \
        --slots 0,1,2 --arms FULL,CTL --outroot "$EXP/raw" --timeout 20 \
        --hang-budget 1 > "work/log_$RUN.txt" 2>&1 ) &
RPID=$!
i=0
while kill -0 "$RPID" 2>/dev/null; do
    i=$((i+1))
    if [ "$i" -gt "$CAP" ]; then
        PGID=$(ps -o pgid= -p "$RPID" | tr -d ' ')
        [ -n "$PGID" ] && kill -TERM "-$PGID" 2>/dev/null
        sleep 3
        [ -n "$PGID" ] && kill -KILL "-$PGID" 2>/dev/null
        break
    fi
    sleep 1
done
wait "$RPID" 2>/dev/null
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
    shasum -a 256 harness/run228.py harness/run228_full.py \
        harness/capture228.sh analysis/formal228.py work/frozen/db.json \
        work/frozen/isadb.py work/frozen/shdump.m \
        work/frozen/agxrun_persist.m work/frozen/agxparse.py \
        > "raw/$RUN/06_harness_sha256.txt"
fi
echo "capture rc=$RC"
tail -8 "work/log_$RUN.txt"
exit "$RC"
