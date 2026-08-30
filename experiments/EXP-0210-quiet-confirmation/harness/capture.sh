#!/bin/sh
# EXP-0210 -- take ONE confirmation capture under a measured quiet window.
#   sh harness/capture.sh <tag> <sample_seconds> <alarm_seconds> '<remote command>'
# Runs on the repo host.  SSHPASS must already be exported.
set -u
TAG="$1"; SECS="$2"; ALRM="$3"; CMD="$4"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HERE/raw/$TAG"
echo "=== $TAG  start $(date -u +%FT%TZ)"
ALARM="$ALRM" sh "$HERE/harness/neo.sh" sh \
  "sh ~/agxre/EXP-0210/drive_one.sh ~/agxre/EXP-0210/samples/$TAG.jsonl $SECS $TAG \"$CMD\"" \
  2>&1 | grep -v "^Warning: Permanently added"
echo "=== $TAG  end   $(date -u +%FT%TZ)"
ALARM=180 sh "$HERE/harness/neo.sh" put \
  "user@${NEO:-192.168.170.254}:agxre/EXP-0210/samples/$TAG.jsonl" \
  "$HERE/raw/$TAG/quiet.jsonl" 2>&1 | grep -v "^Warning: Permanently added"
python3 "$HERE/harness/quietcheck.py" "$HERE/raw/$TAG/quiet.jsonl" > "$HERE/raw/$TAG/quietcheck.json"
python3 -c "
import json,sys
d=json.load(open('$HERE/raw/$TAG/quietcheck.json'))
keep=('QUIET','samples','span_s','max_foreign_runner','max_foreign_legacy_incl_compiler_svc','Q1b_compiler_svc_max','Q1b_compiler_svc_all_new_since_start','Q2_recovery_stable','recovery_first_last','Q3_submitter_pids','Q4_sampler_alive','loadavg_max','busy_count_values','ioreg_errors')
print(json.dumps({k:d.get(k) for k in keep}))"
