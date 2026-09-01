#!/bin/sh
# EXP-0224 V3 -- one formal G17P capture. Run on the Neo.
set -u
RUN="$1"
ORDER="$2"
SEED="$3"
CAP="${4:-180}"
EXP="$HOME/agxre/EXP-0224-falu3-canonical"
OLD="$HOME/agxre/EXP-0220"
OUTROOT="$EXP/raw"
cd "$EXP" || exit 1
mkdir -p work raw

python3 "$OLD/harness/quietsample.py" --out "work/quiet_$RUN.jsonl" \
        --seconds "$CAP" --interval 2.0 --label "$RUN" >/dev/null 2>&1 &
QPID=$!
python3 "$OLD/harness/gpusnap.py" pre > "work/gpu_pre_$RUN.json" 2>&1
set +e
( python3 harness/run224.py --run "$RUN" --order "$ORDER" --seed "$SEED" \
        --slots 0,1,2 --arms V3 --outroot "$OUTROOT" \
        --timeout 20 > "work/log_$RUN.txt" 2>&1 ) &
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
kill "$QPID" 2>/dev/null || true
sleep 1
if [ -d "raw/$RUN" ]; then
    cp "work/quiet_$RUN.jsonl" "raw/$RUN/procs.jsonl"
    cp "work/gpu_pre_$RUN.json" "raw/$RUN/gpu_pre.json"
    cp "work/gpu_post_$RUN.json" "raw/$RUN/gpu_post.json"
    cp "work/log_$RUN.txt" "raw/$RUN/03_stdout.txt"
    shasum -a 256 harness/run224.py \
        "$HOME/agxre/EXP-0223-isel-canonical/harness/run223_pilot.py" \
        "$OLD/harness/run220.py" "$OLD/harness/prog220.py" \
        "$OLD/harness/synth220.py" > "raw/$RUN/06_harness_sha256.txt"
fi
echo "capture rc=$RC"
tail -4 "work/log_$RUN.txt"
exit "$RC"
