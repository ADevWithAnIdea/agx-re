#!/bin/sh
# EXP-0183 -- rebuild the candidate agx-isa trees the A/B gate runs against.
#
# Only each candidate's db.json is committed: the rest of the tree is a verbatim copy of
# work/base_live/ (the frozen snapshot of tools/agx-isa at this experiment's start, which is
# byte-identical to commit 8b857847's). Committing eight copies of the same 2,500-line
# isadb.py would be noise, not evidence.
#
#   sh work/rebuild_trees.sh   # from the experiment directory
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
for c in "$HERE"/cand_*; do
    [ -d "$c" ] || continue
    for f in "$HERE"/base_live/*.py; do
        cp "$f" "$c/"
    done
    # validation.json is not used by the gate but keeps the tree loadable by other tools
    cp "$HERE"/base_live/validation.json "$c/" 2>/dev/null || true
    cp "$HERE"/base_live/match_overlap.json "$c/" 2>/dev/null || true
done
echo "rebuilt: $(ls -d "$HERE"/cand_* | wc -l | tr -d ' ') candidate trees"
