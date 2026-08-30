#!/bin/sh
# EXP-0210 -- run a SOURCE EXPERIMENT's own analysis script over a quiet pair, WITHOUT
# leaving its committed verdict files modified.
#
#   sh harness/run_analysis.sh <exp_dir> <tag> <command ...>
#
# Several experiments' `analysis/verdicts.py` write `analysis/field_verdicts*.json` in place.
# This experiment must not alter any existing verdict file (dispatch constraint; §9 of
# RE_EXPERIMENT_PROCESS_CORRECTIONS: a confirmation ADDS evidence, it never rewrites it).
# So: run, copy whatever the script rewrote into this experiment's own analysis/out/ under
# <tag>, then `git checkout --` every TRACKED file it modified.  Untracked files (the new raw
# run directories) are left alone.
set -u
EXPDIR="$1"; TAG="$2"; shift 2
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$(cd "$(dirname "$0")/.." && pwd)/analysis/out"
mkdir -p "$OUT"
( cd "$ROOT/$EXPDIR" && "$@" ) 2>&1 | tail -80
cd "$ROOT"
MOD=$(git status --porcelain -- "$EXPDIR" | awk '$1=="M"{print $2}')
for f in $MOD; do
  b=$(basename "$f")
  cp "$ROOT/$f" "$OUT/${TAG}__${b}"
  echo "PRESERVED-AND-RESTORED: $f -> analysis/out/${TAG}__${b}"
done
if [ -n "$MOD" ]; then git checkout -- $MOD; fi
git status --porcelain -- "$EXPDIR" | awk '$1=="M"{print "STILL MODIFIED (BAD): "$2}'
