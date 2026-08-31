#!/bin/sh
# EXP-0213 -- RUNS ON THE NEO.  Same as drive_one.sh, but the wall-clock cap kills the
# WHOLE capture, not just the shell in front of it.
#
#   sh drive_cap.sh <out_prefix> <sample_seconds> <label> <cap_seconds> <command...>
#
# WHY THIS EXISTS (AMENDMENT-01, frozen before stage 6A's first dispatch).  drive_one.sh caps
# a capture with `perl -e 'alarm N; exec @ARGV' sh -c "<cmd>"`.  An alarm timer survives
# execve, so SIGALRM reaches the `sh -c` -- and ONLY that shell.  Its `python3 run.py` child
# is ORPHANED and keeps sweeping the GPU after the driver believes the capture was stopped.
# Phases 1-3 finish in ~1 s of device time and never approach their alarms, so drive_one.sh
# is left exactly as it was for them; stage 6A/6B/6C are the captures where the cap is
# load-bearing (EXP-0206's run.py deliberately has NO abort path and NO hang budget, and that
# is not changed -- the cap is external, which is the only place it can live).
#
# On a cap hit: the run.py child is SIGTERMed, then SIGKILLed, then any dispatch runner still
# alive is reaped by run-id and by name.  Captures in this experiment are strictly sequential
# and this agent owns the device, so a by-name reap cannot take a sibling's runner.
# A cap hit is reported as __DRIVE_RC=142 and the partial capture is RETAINED, never reused.
OUT="$1" ; SECS="$2" ; LABEL="$3" ; CAP="$4" ; shift 4
mkdir -p "$(dirname "$OUT")"
E=$HOME/agxre/EXP-0213

python3 "$E/gpusnap.py" pre > "$OUT.gpu.jsonl"
python3 "$E/quietsample.py" --out "$OUT.quiet.jsonl" --seconds "$SECS" --label "$LABEL" &
WPID=$!
sleep 2
echo "__DRIVE_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sh -c "$*" > "$OUT.log" 2>&1 &
CPID=$!
END=$(( $(date +%s) + CAP ))
CAPPED=0
while kill -0 "$CPID" 2>/dev/null; do
  if [ "$(date +%s)" -ge "$END" ]; then
    CAPPED=1
    echo "__DRIVE_CAP_HIT ${CAP}s" >> "$OUT.log"
    pkill -TERM -P "$CPID" 2>/dev/null
    kill -TERM "$CPID" 2>/dev/null
    sleep 5
    pkill -KILL -P "$CPID" 2>/dev/null
    kill -KILL "$CPID" 2>/dev/null
    pkill -KILL -f 'agxrun_persist' 2>/dev/null
    pkill -KILL -f 'gfrun4' 2>/dev/null
    break
  fi
  sleep 3
done
wait "$CPID" 2>/dev/null
RC=$?
[ "$CAPPED" = "1" ] && RC=142
echo "__DRIVE_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
tail -30 "$OUT.log"
sleep 2
kill "$WPID" 2>/dev/null
wait "$WPID" 2>/dev/null
python3 "$E/gpusnap.py" post >> "$OUT.gpu.jsonl"
echo "__DRIVE_CAPPED=$CAPPED"
echo "__DRIVE_RC=$RC"
