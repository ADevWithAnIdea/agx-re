#!/bin/sh
# Wait (bounded) for MTLCompilerService to come back, then capture the gate pair.
cd "$(dirname "$0")/.."
i=0
while [ $i -lt 120 ]; do
    if python3 work/pilot/health.py > work/pilot/health.log 2>&1; then
        echo "COMPILER RECOVERED $(date +%H:%M:%S)"
        sleep 20
        ./harness/capture.sh m4_20260828_run06
        exit 0
    fi
    i=$((i+1))
    sleep 20
done
echo "GAVE UP: compiler still down after 40 min"
