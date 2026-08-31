#!/bin/sh
# EXP-0213 -- one capture under a measured quiet window AND a process-group wall-clock cap.
# Identical to capture.sh except it drives drive_cap.sh (AMENDMENT-01).
#   sh harness/capture_cap.sh <tag> <sample_s> <cap_s> <remote_exp> '<remote command>'
set -u
TAG="$1"; SECS="$2"; CAP="$3"; REXP="$4"; CMD="$5"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$HERE/raw/$TAG"
echo "=== $TAG start $(date -u +%FT%TZ)  remote_exp=$REXP cap=${CAP}s"
SSHALARM=$(( CAP + 300 ))
ALARM=$SSHALARM sh "$HERE/harness/neo.sh" sh \
  "sh ~/agxre/EXP-0213/drive_cap.sh ~/agxre/EXP-0213/samples/$TAG $SECS $TAG $CAP \"cd ~/agxre/$REXP && $CMD\"" \
  2>&1 | grep -v "^Warning: Permanently added"
echo "=== $TAG end   $(date -u +%FT%TZ)"
ALARM=300 sh "$HERE/harness/neo.sh" sh \
  "cd ~/agxre/EXP-0213/samples && tar czf - $TAG.quiet.jsonl $TAG.gpu.jsonl $TAG.log" \
  2>/dev/null | tar xzf - -C "$HERE/raw/$TAG"
for f in quiet.jsonl gpu.jsonl log; do
  [ -f "$HERE/raw/$TAG/$TAG.$f" ] && mv "$HERE/raw/$TAG/$TAG.$f" "$HERE/raw/$TAG/$f"
done
python3 "$HERE/harness/quietcheck.py" "$HERE/raw/$TAG/quiet.jsonl" \
        --gpu "$HERE/raw/$TAG/gpu.jsonl" > "$HERE/raw/$TAG/quietcheck.json" 2>"$HERE/raw/$TAG/quietcheck.err"
python3 -c "
import json,sys
try: d=json.load(open('$HERE/raw/$TAG/quietcheck.json'))
except Exception as e:
    print('QUIETCHECK FAILED', e); sys.exit(0)
keep=('QUIET','samples','span_s','max_foreign_runner_live','max_foreign_runner_strict','compiler_svc_max','recovery_pre','recovery_post','recovery_delta','submitter_foreign','loadavg_max','ioreg_errors')
print('QUIETCHECK', json.dumps({k:d.get(k) for k in keep}))"
