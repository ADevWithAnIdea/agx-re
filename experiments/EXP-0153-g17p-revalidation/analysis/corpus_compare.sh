#!/bin/bash
# EXP-0153 arm G, step 3: reproduce every corpus number in RESULTS.md section 7.
# The M4 subset is rebuilt from the COMMITTED M4 hex rather than duplicated here.
set -euo pipefail
cd "$(dirname "$0")/.."
ISA=../../tools/agx-isa
M4=../EXP-M4-13-full-corpus/hex
SUB=work/hex_m4_subset
rm -rf "$SUB"; mkdir -p "$SUB"
for f in raw/g17p-corpus-hex/*.hex; do cp "$M4/$(basename "$f")" "$SUB/"; done
echo "== M4, full EXP-0148 corpus (the published reference)"
python3 analysis/tokenize_corpus.py "$ISA" "$M4"  - analysis/m4_corpus_summary.json
echo "== M4, the same 582 programs"
python3 analysis/tokenize_corpus.py "$ISA" "$SUB" - analysis/m4_subset_summary.json
echo "== G17P, the same 582 programs"
python3 analysis/tokenize_corpus.py "$ISA" raw/g17p-corpus-hex - analysis/g17p_corpus_summary.json
echo "== byte identity M4 vs G17P"
python3 analysis/tokenize_corpus.py --compare "$SUB" raw/g17p-corpus-hex analysis/byte_identity.json
