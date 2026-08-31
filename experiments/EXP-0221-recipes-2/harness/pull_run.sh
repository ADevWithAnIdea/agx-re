#!/bin/sh
# EXP-0221 -- pull EXACTLY ONE remote run directory back into the repo.
#   sh harness/pull_run.sh <remote_exp> <run_id> <local_exp_dir> [remote_subdir] [local_subdir]
# EXP-0210 disclosed that a TREE-WIDE pull overwrote a committed raw file.  This
# pulls ONE named directory and REFUSES if it already exists locally.
set -u
REMOTE_EXP="$1"; RUN_ID="$2"; LOCAL_EXP="$3"
RSUB="${4:-raw}"; LSUB="${5:-raw}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
DST="$LOCAL_EXP/$LSUB/$RUN_ID"
if [ -e "$DST" ]; then
  echo "PULL REFUSED: $DST already exists -- run ids are never reused or topped up" >&2
  exit 3
fi
mkdir -p "$LOCAL_EXP/$LSUB"
ALARM=900 sh "$HERE/harness/neo.sh" sh \
  "cd ~/agxre/$REMOTE_EXP/$RSUB && tar czf - '$RUN_ID'" 2>/dev/null \
  | tar xzf - -C "$LOCAL_EXP/$LSUB"
RC=$?
echo "pull_run rc=$RC  ->  $DST"
ls -la "$DST" 2>/dev/null | head -20
exit $RC
