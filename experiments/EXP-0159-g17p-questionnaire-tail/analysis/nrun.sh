#!/bin/bash
# EXP-0159: launch a family on the neo detached, so a long run survives the
# orchestrator's per-call timeout.  usage: nrun.sh <run-id> <family>
NEO=${NEO:-192.168.10.243}
perl -e 'alarm 90; exec @ARGV' sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null user@$NEO \
  "cd ~/agxre/EXP-0159/harness && nohup python3 run.py --run-id $1 --family $2 > ~/agxre/EXP-0159/raw/$1.$2.out 2>&1 &
   echo LAUNCHED $1 $2"
