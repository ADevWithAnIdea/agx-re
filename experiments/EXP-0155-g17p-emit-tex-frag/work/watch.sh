#!/bin/bash
export SSHPASS='Password_1'; NEO=192.168.10.243
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=20"
for i in $(seq 1 60); do
  out=$(perl -e 'alarm 120; exec @ARGV' sshpass -e ssh $SSHOPT user@$NEO 'cd ~/agxre/EXP-0155 && if [ -f raw/'"$1"'/05_run_manifest.json ]; then echo DONE; fi; python3 - <<PY
import json,collections,os
p="raw/'"$1"'/sweep.jsonl"
c=collections.Counter(); arms=set(); last=None; n=0
for ln in open(p):
    r=json.loads(ln); c[r["outcome"]]+=1; arms.add(r["carrier"]); last=r; n+=1
print("cases=%d arms=%d cur=%s/%s/%s hang=%d fault=%d foreign=%d" % (n,len(arms),last["carrier"],last["field"],last["value"],c["hang"],c["fault"],c["foreign"]))
PY' 2>&1 | tr '\n' ' ')
  echo "$out"
  case "$out" in *DONE*) exit 0;; esac
  sleep 150
done
