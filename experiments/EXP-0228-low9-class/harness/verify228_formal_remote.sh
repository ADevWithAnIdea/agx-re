#!/bin/sh
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"; REMOTE="agxre/EXP-0228-low9-class"
NEOHELP="$HERE/../EXP-0220-canonical-recipes/harness/neo.sh"; L="$(mktemp)"; R="$(mktemp)"
trap 'rm -f "$L" "$R"' EXIT HUP INT TERM
( cd "$HERE" && shasum -a 256 harness/*.py harness/*.sh analysis/*.py kernels/*.metal work/frozen/* | sort -k2 ) > "$L"
ALARM=180 sh "$NEOHELP" sh "cd ~/$REMOTE && shasum -a 256 harness/*.py harness/*.sh analysis/*.py kernels/*.metal work/frozen/* | sort -k2" > "$R" || exit 1
diff -u "$L" "$R"
echo "EXP-0228 formal remote hashes verified"
