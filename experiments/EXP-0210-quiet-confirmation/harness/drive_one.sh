#!/bin/sh
# EXP-0210 -- runs ON THE NEO.  Wraps ONE confirmation capture in a quiet-window sample.
#
#   sh drive_one.sh <sample_out> <sample_seconds> <label> <command>
#
# The sampler is started BEFORE the capture and killed AFTER it, so the sample window
# strictly contains the capture.  The capture's exit status is echoed as __DRIVE_RC so a
# non-zero status can never be swallowed by a shell chain (SUBAGENT_BRIEF: the `&&` hazard).
OUT="$1" ; SECS="$2" ; LABEL="$3" ; shift 3
mkdir -p "$(dirname "$OUT")"
python3 "$HOME/agxre/EXP-0210/quietsample.py" --out "$OUT" --seconds "$SECS" --label "$LABEL" &
WPID=$!
sleep 2
echo "__DRIVE_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sh -c "$*"
RC=$?
echo "__DRIVE_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sleep 2
kill $WPID 2>/dev/null
wait $WPID 2>/dev/null
echo "__DRIVE_RC=$RC"
