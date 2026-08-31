#!/bin/sh
# EXP-0221 -- ONE gated capture, RUN ON THE NEO.
#   sh harness/capture.sh <run_id> <order> <seed> <cap_seconds> [outroot] [arms]
# Starts the quiet sampler FIRST (Gate E requires the machine to be MEASURED
# quiet, not claimed quiet), snapshots the device counters, runs the sweep under
# a wall-clock cap that kills the PROCESS GROUP, snapshots again.
set -u
RUN="$1"; ORDER="$2"; SEED="$3"; CAP="$4"; OUTROOT="${5:-raw}"; ARMS="${6:-}"
cd "$HOME/agxre/EXP-0221" || exit 1
mkdir -p work
python3 harness/quietsample.py --out "work/quiet_$RUN.jsonl" --seconds "$CAP" \
        --interval 2.0 --label "$RUN" >/dev/null 2>&1 &
QPID=$!
python3 harness/gpusnap.py > "work/gpu_pre_$RUN.json" 2>&1
set +e
( python3 harness/run221.py --run "$RUN" --order "$ORDER" --seed "$SEED" --carrier "${CARRIER:-carrier221.metal}" \
        --slots 0,1,2 --hazard --outroot "$OUTROOT" --arms "$ARMS" \
        > "work/log_$RUN.txt" 2>&1 ) &
RPID=$!
i=0
while kill -0 "$RPID" 2>/dev/null; do
  i=$((i+1))
  if [ "$i" -gt "$CAP" ]; then
    echo "__CAP_HIT after ${CAP}s -- killing the run's process group"
    kill -TERM "-$(ps -o pgid= -p $RPID | tr -d ' ')" 2>/dev/null
    sleep 3
    kill -KILL "-$(ps -o pgid= -p $RPID | tr -d ' ')" 2>/dev/null
    break
  fi
  sleep 1
done
wait "$RPID" 2>/dev/null
RC=$?
set -e
python3 harness/gpusnap.py > "work/gpu_post_$RUN.json" 2>&1
kill "$QPID" 2>/dev/null || true
sleep 1
D="$OUTROOT/$RUN"
[ -d "$D" ] && cp "work/quiet_$RUN.jsonl" "$D/procs.jsonl" 2>/dev/null
[ -d "$D" ] && cp "work/gpu_pre_$RUN.json" "$D/gpu_pre.json" 2>/dev/null
[ -d "$D" ] && cp "work/gpu_post_$RUN.json" "$D/gpu_post.json" 2>/dev/null
[ -d "$D" ] && cp "work/log_$RUN.txt" "$D/03_stdout.txt" 2>/dev/null
echo "capture rc=$RC"
tail -6 "work/log_$RUN.txt"
