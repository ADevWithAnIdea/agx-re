#!/bin/sh
# A separate transaction from push227.sh: compare the remote authored inputs
# and frozen dependencies against the local hashes.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
REMOTE="agxre/EXP-0227-low9-length"
NEOHELP="$HERE/../EXP-0220-canonical-recipes/harness/neo.sh"

LOCAL="$(mktemp)"
REMOTE_HASH="$(mktemp)"
trap 'rm -f "$LOCAL" "$REMOTE_HASH"' EXIT HUP INT TERM
( cd "$HERE" && shasum -a 256 harness/*.py harness/*.sh kernels/*.metal \
    work/frozen/db.json work/frozen/isadb.py work/frozen/shdump.m \
    work/frozen/agxrun_persist.m work/frozen/agxparse.py | sort -k2 ) > "$LOCAL"
ALARM=180 sh "$NEOHELP" sh \
    "cd ~/$REMOTE && shasum -a 256 harness/*.py harness/*.sh kernels/*.metal work/frozen/db.json work/frozen/isadb.py work/frozen/shdump.m work/frozen/agxrun_persist.m work/frozen/agxparse.py | sort -k2" \
    > "$REMOTE_HASH" || exit 1
diff -u "$LOCAL" "$REMOTE_HASH"
echo "EXP-0227 remote hashes verified"
