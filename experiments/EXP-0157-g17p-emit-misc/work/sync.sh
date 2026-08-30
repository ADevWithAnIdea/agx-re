#!/bin/bash
# push authored sources to the neo (never binaries, never raw/)
set -e
cd "$(dirname "$0")/.."
NEO="${NEO:-192.168.10.243}"
SSHOPT="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=15 -o LogLevel=ERROR"
perl -e 'alarm 300; exec @ARGV' sshpass -e ssh $SSHOPT user@$NEO 'mkdir -p ~/agxre/EXP-0157/{harness,kernels,analysis,work,raw,bin}'
perl -e 'alarm 300; exec @ARGV' sshpass -e scp $SSHOPT harness/*.py harness/*.m harness/*.sh user@$NEO:~/agxre/EXP-0157/harness/
perl -e 'alarm 300; exec @ARGV' sshpass -e scp $SSHOPT kernels/* user@$NEO:~/agxre/EXP-0157/kernels/
perl -e 'alarm 300; exec @ARGV' sshpass -e scp $SSHOPT analysis/*.py user@$NEO:~/agxre/EXP-0157/analysis/
echo synced
