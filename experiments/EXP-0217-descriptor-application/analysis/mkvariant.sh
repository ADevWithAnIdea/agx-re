#!/bin/bash
# EXP-0217 -- build an isolated copy of tools/agx-isa with one edit group applied,
# so a match change can be measured against the own-MSL corpus and against the
# committed record sets WITHOUT touching the live tree.
# Usage: bash analysis/mkvariant.sh <name> --only GROUP[,GROUP...]
# (identical in shape to EXP-0212/analysis/mkvariant.sh, which is the precedent.)
set -eu
cd "$(dirname "$0")/../../.."
N="$1"; shift
D="experiments/EXP-0217-descriptor-application/work/var_$N"
rm -rf "$D"; mkdir -p "$D"
cp tools/agx-isa/isadb.py tools/agx-isa/agxisa.py "$D/" 2>/dev/null || cp tools/agx-isa/isadb.py "$D/"
python3 experiments/EXP-0217-descriptor-application/analysis/apply_db_edits.py \
    tools/agx-isa/db.json "$D/db.json" "$@" >/dev/null
echo "$D"
