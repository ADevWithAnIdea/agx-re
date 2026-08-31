#!/bin/sh
# EXP-0213 -- RUNS ON THE NEO.  Wraps ONE capture in a measured quiet window and
# records the device reset/recovery counters immediately before and after it.
#
#   sh drive_one.sh <out_prefix> <sample_seconds> <label> <alarm_s> <command...>
#
# Writes:  <out_prefix>.quiet.jsonl   -- quietsample.py samples (2 s interval)
#          <out_prefix>.gpu.jsonl     -- pre/post device counter snapshots
#          <out_prefix>.log           -- the capture's own stdout+stderr
#
# The sampler starts BEFORE and is killed AFTER the capture, so the sample window
# strictly contains it.  The capture's exit status is echoed as __DRIVE_RC so a
# non-zero status can never be swallowed by a shell chain (SUBAGENT_BRIEF: the
# `&&` hazard).  The capture runs under a hard `alarm` wrapper so a wedged
# dispatch cannot hang the session; alarm-kill shows up as __DRIVE_RC=142.
OUT="$1" ; SECS="$2" ; LABEL="$3" ; ALRM="$4" ; shift 4
mkdir -p "$(dirname "$OUT")"
E=$HOME/agxre/EXP-0213

python3 "$E/gpusnap.py" pre > "$OUT.gpu.jsonl"
python3 "$E/quietsample.py" --out "$OUT.quiet.jsonl" --seconds "$SECS" --label "$LABEL" &
WPID=$!
sleep 2
echo "__DRIVE_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
perl -e 'alarm shift; exec @ARGV' "$ALRM" sh -c "$*" > "$OUT.log" 2>&1
RC=$?
echo "__DRIVE_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
tail -30 "$OUT.log"
sleep 2
kill $WPID 2>/dev/null
wait $WPID 2>/dev/null
python3 "$E/gpusnap.py" post >> "$OUT.gpu.jsonl"
echo "__DRIVE_RC=$RC"
