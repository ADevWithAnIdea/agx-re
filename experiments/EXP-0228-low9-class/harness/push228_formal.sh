#!/bin/sh
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"; REMOTE="agxre/EXP-0228-low9-class"
NEOH="${NEO:-192.168.170.254}"; NEOHELP="$HERE/../EXP-0220-canonical-recipes/harness/neo.sh"
ALARM=120 sh "$NEOHELP" sh "mkdir -p ~/$REMOTE/harness ~/$REMOTE/kernels ~/$REMOTE/work/frozen ~/$REMOTE/raw ~/$REMOTE/analysis" || exit 1
ALARM=300 sh "$NEOHELP" put "$HERE"/harness/*.py "$HERE"/harness/*.sh "user@$NEOH:$REMOTE/harness/" || exit 1
ALARM=300 sh "$NEOHELP" put "$HERE"/analysis/*.py "user@$NEOH:$REMOTE/analysis/" || exit 1
ALARM=300 sh "$NEOHELP" put "$HERE"/kernels/*.metal "user@$NEOH:$REMOTE/kernels/" || exit 1
ALARM=300 sh "$NEOHELP" put "$HERE"/work/frozen/db.json "$HERE"/work/frozen/isadb.py "$HERE"/work/frozen/shdump.m "$HERE"/work/frozen/agxrun_persist.m "$HERE"/work/frozen/agxparse.py "user@$NEOH:$REMOTE/work/frozen/" || exit 1
( cd "$HERE" && shasum -a 256 harness/*.py harness/*.sh analysis/*.py kernels/*.metal work/frozen/* | sort -k2 )
