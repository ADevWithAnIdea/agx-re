#!/bin/sh
# EXP-0094 harness build. Command Line Tools only, no `metal` CLI.
set -e
cd "$(dirname "$0")"
clang -fobjc-arc -O2 -framework Metal -framework Foundation -o texrender texrender.m
clang -fobjc-arc -O2 -framework Metal -framework Foundation -o texcompute texcompute.m
echo "built: texrender texcompute"
