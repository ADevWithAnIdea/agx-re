#!/bin/sh
set -e
cd "$(dirname "$0")/../.."
D=work/pilot
mkdir -p "$D/run" "$D/full" "$D/summ"
N=$(python3 -B -c "import sys; sys.path.insert(0,'analysis'); import casematrix as CM; print(len(CM.build_cases()))")
for i in $(seq 0 $((N-1))); do
  out="$D/summ/case_$(printf '%03d' $i).json"
  python3 -B harness/case_exec.py --case-index "$i" --run-dir "$D/run" --bin-dir "$D/bin" \
    --repo ../.. --full-dir "$D/full" --case-timeout 30 > "$out" 2> "$D/summ/case_$(printf '%03d' $i).err" || echo "CASE $i EXIT $?"
  python3 -B -c "
import json
d = json.load(open('$out'))
r = d['record']
line = f\"{$i:3d} {r['id']:40s} status={r['status']:10s}\"
for name,c in r.get('compared',{}).items():
    if 'error' in c:
        line += f\" {name}=ERR\"
    else:
        line += f\" {name}={c['match_count']}/{c['total']}\"
print(line)
"
done
