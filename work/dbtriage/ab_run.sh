#!/bin/bash
# DB-defect triage -- run the frozen metric set against one class-(c) variant tree.
# Usage: bash work/dbtriage/ab_run.sh <variant-name>
# Reports the two numbers EXP-0148 gated on: clean files + strict leftover bytes,
# plus the round-trip pass/fail count. Never touches tools/agx-isa/.
set -u
cd "$(dirname "$0")/../.." || exit 1
V="$1"
D="work/dbtriage/cvar/$V"
R="work/dbtriage/ab/$V"
mkdir -p "$R"
python3 work/dbtriage/rt_shim.py "$D" > "$R/roundtrip.txt" 2>&1
OK=$(grep -c "\[OK\]"   "$R/roundtrip.txt")
FAIL=$(grep -c "\[FAIL\]" "$R/roundtrip.txt")
CRASH=$(grep -c "Traceback" "$R/roundtrip.txt")
S=$(python3 work/dbtriage/tokenize_corpus.py "$D" "$R/strict.json")
echo "{\"variant\":\"$V\",\"roundtrip_ok\":$OK,\"roundtrip_fail\":$FAIL,\"roundtrip_crash\":$CRASH,\"strict\":$S}" \
  | tee "$R/metrics.json"
