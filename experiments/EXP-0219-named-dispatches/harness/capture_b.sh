#!/bin/sh
# EXP-0219 -- ONE part-B capture, RUN ON THE NEO.
#   sh harness/capture_b.sh <run_id> <phase> <order> <extra...> <cap_seconds>
# Same shape as capture_a.sh: quiet sampler first, device counters pre/post, the
# sweep under a wall-clock cap that kills the PROCESS GROUP.
set -u
RUN="$1"; PHASE="$2"; ORDER="$3"; EXTRA="$4"; CAP="$5"
cd "$HOME/agxre/EXP-0219" || exit 1
mkdir -p work
python3 harness/quietsample.py --out "work/quiet_$RUN.jsonl" --seconds "$CAP" \
        --interval 2.0 --label "$RUN" >/dev/null 2>&1 &
QPID=$!
python3 harness/gpusnap.py > "work/gpu_pre_$RUN.json" 2>&1
set +e
( python3 harness/run_b.py --run "$RUN" --phase "$PHASE" --order "$ORDER" $EXTRA \
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
[ -d "raw/$RUN" ] && cp "work/quiet_$RUN.jsonl" "raw/$RUN/procs.jsonl" 2>/dev/null
[ -d "raw/$RUN" ] && cp "work/gpu_pre_$RUN.json" "raw/$RUN/gpu_pre.json" 2>/dev/null
[ -d "raw/$RUN" ] && cp "work/gpu_post_$RUN.json" "raw/$RUN/gpu_post.json" 2>/dev/null
[ -d "raw/$RUN" ] && cp "work/log_$RUN.txt" "raw/$RUN/03_stdout.txt" 2>/dev/null
echo "capture rc=$RC"
tail -4 "work/log_$RUN.txt"
