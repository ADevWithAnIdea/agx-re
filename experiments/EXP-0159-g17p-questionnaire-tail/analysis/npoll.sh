#!/bin/bash
# EXP-0159: poll a detached run.  usage: npoll.sh <run-id> [family]
NEO=${NEO:-192.168.10.243}
perl -e 'alarm 90; exec @ARGV' sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null user@$NEO \
  "pgrep -f 'run.py --run-id $1' >/dev/null && echo RUNNING || echo IDLE;
   wc -l ~/agxre/EXP-0159/raw/$1/*.jsonl 2>/dev/null; tail -2 ~/agxre/EXP-0159/raw/$1.*.out 2>/dev/null"
