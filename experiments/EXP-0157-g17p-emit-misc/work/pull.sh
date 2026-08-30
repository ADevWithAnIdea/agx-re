#!/bin/bash
set -e
cd "$(dirname "$0")/.."
NEO="${NEO:-192.168.10.243}"
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 -o LogLevel=ERROR"
perl -e 'alarm 600; exec @ARGV' sshpass -e ssh $SSHOPT user@$NEO 'cd ~/agxre/EXP-0157 && tar czf /tmp/raw_0157.tgz raw work/*.log work/op04_candidates.json 2>/dev/null; echo tarred'
perl -e 'alarm 600; exec @ARGV' sshpass -e scp $SSHOPT user@$NEO:/tmp/raw_0157.tgz work/
tar xzf work/raw_0157.tgz -C . && rm -f work/raw_0157.tgz
echo "pulled:"; du -sh raw; ls raw
