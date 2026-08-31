#!/bin/sh
# EXP-0213 -- pull EXACTLY ONE remote run directory back into the repo.
#
#   sh harness/pull_run.sh <remote_exp> <run_id> <local_exp_dir>
#
# EXP-0210 disclosed that a TREE-WIDE `rsync`/`tar` pull overwrote a committed raw
# file (an orphaned sampler on the neo had been appending to it).  This pulls ONE
# named directory and REFUSES if that directory already exists locally, so a pull
# can never touch an existing committed capture.
set -u
REMOTE_EXP="$1"; RUN_ID="$2"; LOCAL_EXP="$3"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
DST="$LOCAL_EXP/raw/$RUN_ID"
if [ -e "$DST" ]; then
  echo "PULL REFUSED: $DST already exists -- run ids are never reused or topped up" >&2
  exit 3
fi
mkdir -p "$DST"
ALARM=600 sh "$HERE/harness/neo.sh" sh \
  "cd ~/agxre/$REMOTE_EXP/raw && tar czf - '$RUN_ID'" 2>/dev/null \
  | tar xzf - -C "$LOCAL_EXP/raw"
RC=$?
echo "pull_run rc=$RC  ->  $DST"
ls -la "$DST" 2>/dev/null | head -20
exit $RC
