#!/bin/sh
# EXP-0213 -- run the remaining planned phases strictly sequentially.
cd "$(dirname "$0")/.."
until [ "$(wc -l < work/phase4a.out)" -ge 8 ]; do sleep 10; done
python3 harness/drive.py work/plan_phase5.json  > work/phase5.out  2>&1
python3 harness/drive.py work/plan_phase4b.json > work/phase4b.out 2>&1
python3 harness/drive.py work/plan_phase4c.json > work/phase4c.out 2>&1
echo "CHAIN DONE $(date -u +%FT%TZ)" >> work/chain.done
