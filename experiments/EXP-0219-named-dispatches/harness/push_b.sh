#!/bin/sh
# EXP-0219 -- push part-B inputs and build gfrun4 IN THIS EXPERIMENT'S OWN TREE
# on the neo, then VERIFY the remote hashes SEPARATELY (SUBAGENT_BRIEF: never
# trust a chained step whose output you then depend on).
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
NEO="${NEO:-192.168.170.254}"
R=agxre/EXP-0219
ALARM=120 sh "$HERE/harness/neo.sh" sh "mkdir -p ~/$R/harness ~/$R/kernels ~/$R/pinned_b ~/$R/work ~/$R/raw" || exit 1
ALARM=300 sh "$HERE/harness/neo.sh" put "$HERE"/harness/*.py "$HERE"/harness/*.m "$HERE"/harness/*.sh "user@$NEO:$R/harness/" || exit 1
ALARM=300 sh "$HERE/harness/neo.sh" put "$HERE"/kernels/*.metal "user@$NEO:$R/kernels/" || exit 1
ALARM=300 sh "$HERE/harness/neo.sh" put "$HERE"/pinned_b/* "user@$NEO:$R/pinned_b/" || exit 1
ALARM=600 sh "$HERE/harness/neo.sh" sh "cd ~/$R && rm -rf harness/__pycache__ pinned_b/__pycache__ && clang -fobjc-arc -O2 -Wno-deprecated-declarations -framework Metal -framework Foundation harness/gfrun4.m -o work/gfrun4 && echo BUILD_OK && ls -la work/gfrun4"
echo "--- LOCAL"
( cd "$HERE" && shasum -a 256 harness/run_b.py harness/gfrun4.m harness/runner4.py harness/carriers.py harness/oracle.py harness/arms.py pinned_b/db.json pinned_b/isadb.py pinned_b/agxparse.py kernels/k_msread.metal kernels/k_mslodq.metal kernels/k_msread1.metal | sort -k2 )
echo "--- REMOTE"
ALARM=180 sh "$HERE/harness/neo.sh" sh "cd ~/$R && shasum -a 256 harness/run_b.py harness/gfrun4.m harness/runner4.py harness/carriers.py harness/oracle.py harness/arms.py pinned_b/db.json pinned_b/isadb.py pinned_b/agxparse.py kernels/k_msread.metal kernels/k_mslodq.metal kernels/k_msread1.metal | sort -k2"
