#!/bin/bash
# EXP-0198 -- regenerate every check output from the real validation.json, in
# dependency order (check_misc.py reads check_0140.json).
set -e
cd "$(dirname "$0")"
unset EXP0198_VALIDATION
for s in check_0139 check_0157 check_0162 check_0155 check_e0189_nonzero \
         check_0140 check_0138 check_0141 check_0147 check_fspecial \
         check_withheld check_misc check_b_alu10 classify; do
  echo "=== $s ==="
  python3 "$s.py"
done
