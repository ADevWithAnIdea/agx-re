#!/bin/bash
# EXP-0148 -- run the frozen metric set against one variant tree.
# Usage: analysis/ab_run.sh <variant-dir-name>   (e.g. isa_copy, variant_h1_lo9)
set -u
D="work/$1"
mkdir -p "raw/ab/$1"
python3 tools/rt_shim.py "$D" > "raw/ab/$1/roundtrip.txt" 2>&1
OK=$(grep -c "\[OK\]" "raw/ab/$1/roundtrip.txt")
FAIL=$(grep -c "\[FAIL\]" "raw/ab/$1/roundtrip.txt")
S=$(python3 analysis/tokenize_corpus.py "$D" "raw/ab/$1/tokens_strict.jsonl" "raw/ab/$1/strict.json")
R=$(python3 analysis/tokenize_corpus.py "$D" "raw/ab/$1/tokens_resync.jsonl" "raw/ab/$1/resync.json" --resync)
echo "{\"variant\":\"$1\",\"roundtrip_ok\":$OK,\"roundtrip_fail\":$FAIL,\"strict\":$S,\"resync\":$R}" \
  | tee "raw/ab/$1/metrics.json"
