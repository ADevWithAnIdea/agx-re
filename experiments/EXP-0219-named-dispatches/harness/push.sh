#!/bin/sh
# EXP-0219 -- push this experiment's authored inputs to the neo, then VERIFY the
# remote hashes SEPARATELY.  SUBAGENT_BRIEF: "after any push whose output you
# will then depend on, VERIFY IT SEPARATELY" -- a chained step that silently did
# not run is indistinguishable from success in the exit code, and EXP-0179 ran a
# gated pass against a STALE harness exactly that way.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="agxre/EXP-0219"
ALARM=120 sh "$HERE/harness/neo.sh" sh "mkdir -p ~/$REMOTE/harness ~/$REMOTE/kernels ~/$REMOTE/work/frozen ~/$REMOTE/raw ~/$REMOTE/analysis" || exit 1
ALARM=300 sh "$HERE/harness/neo.sh" put "$HERE"/harness/*.py "$HERE"/harness/*.sh "user@${NEO:-192.168.170.254}:$REMOTE/harness/" || exit 1
ALARM=300 sh "$HERE/harness/neo.sh" put "$HERE"/kernels/*.metal "user@${NEO:-192.168.170.254}:$REMOTE/kernels/" || exit 1
ALARM=300 sh "$HERE/harness/neo.sh" put "$HERE"/work/frozen/* "user@${NEO:-192.168.170.254}:$REMOTE/work/frozen/" || exit 1
echo "--- LOCAL"
( cd "$HERE" && shasum -a 256 harness/*.py kernels/*.metal work/frozen/db.json work/frozen/isadb.py work/frozen/persistrun.py | sort -k2 )
echo "--- REMOTE"
ALARM=180 sh "$HERE/harness/neo.sh" sh "cd ~/$REMOTE && shasum -a 256 harness/*.py kernels/*.metal work/frozen/db.json work/frozen/isadb.py work/frozen/persistrun.py | sort -k2"
