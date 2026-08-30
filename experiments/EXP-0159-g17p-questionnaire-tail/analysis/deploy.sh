#!/bin/bash
# EXP-0159 deploy: push authored sources to the neo and build the harnesses.
set -e
NEO=${NEO:-192.168.10.243}
R=~/agxre/EXP-0159
S() { perl -e 'alarm '"${2:-300}"'; exec @ARGV' sshpass -e ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null user@$NEO "$1"; }
S "mkdir -p $R/harness $R/kernels/fa $R/bin $R/work $R/raw" 90
perl -e 'alarm 300; exec @ARGV' sshpass -e scp -q -r -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    harness/. user@$NEO:agxre/EXP-0159/harness/
perl -e 'alarm 300; exec @ARGV' sshpass -e scp -q -r -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    kernels/. user@$NEO:agxre/EXP-0159/kernels/
S "cd $R/harness && for t in mslprobe bindtex sampheap texrun; do
     clang -fobjc-arc -O2 -framework Metal -framework Foundation -o $R/bin/\$t \$t.m || echo BUILD_FAIL \$t; done; ls -l $R/bin" 600
