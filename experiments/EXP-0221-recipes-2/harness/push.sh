#!/bin/sh
# EXP-0221 -- push this experiment's authored inputs to the neo, then VERIFY the
# remote hashes AS A SEPARATE STEP.  A chained step that silently did not run is
# indistinguishable from success in the exit code, and EXP-0179 ran a gated pass
# against a STALE harness exactly that way.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="agxre/EXP-0221"
NEOH="${NEO:-192.168.170.254}"
ALARM=120 sh "$HERE/harness/neo.sh" sh "mkdir -p ~/$REMOTE/harness ~/$REMOTE/kernels ~/$REMOTE/work/frozen ~/$REMOTE/work/pilot ~/$REMOTE/raw ~/$REMOTE/analysis" || exit 1
ALARM=300 sh "$HERE/harness/neo.sh" put "$HERE"/harness/*.py "$HERE"/harness/*.sh "user@$NEOH:$REMOTE/harness/" || exit 1
ALARM=300 sh "$HERE/harness/neo.sh" put "$HERE"/kernels/*.metal "user@$NEOH:$REMOTE/kernels/" || exit 1
ALARM=300 sh "$HERE/harness/neo.sh" put "$HERE"/work/frozen/* "user@$NEOH:$REMOTE/work/frozen/" || exit 1
echo "--- LOCAL"
( cd "$HERE" && shasum -a 256 harness/*.py kernels/*.metal work/frozen/* | sort -k2 )
echo "--- REMOTE"
ALARM=180 sh "$HERE/harness/neo.sh" sh "cd ~/$REMOTE && shasum -a 256 harness/*.py kernels/*.metal work/frozen/* | sort -k2"
