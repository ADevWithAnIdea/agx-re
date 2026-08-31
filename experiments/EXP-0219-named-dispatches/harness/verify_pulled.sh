#!/bin/sh
# EXP-0219 -- verify every PULLED raw directory is byte-identical to the neo's.
# SUBAGENT_BRIEF: after any transfer whose output you then depend on, VERIFY IT
# SEPARATELY.  Prints LOCAL then REMOTE sha256 of every sweep.jsonl.
set -u
HERE="$(cd "$(dirname "$0")/.." && pwd)"
echo "--- LOCAL"
( cd "$HERE/raw" && find . -name 'sweep.jsonl' | sort | xargs shasum -a 256 )
echo "--- REMOTE"
ALARM=300 sh "$HERE/harness/neo.sh" sh \
  "cd ~/agxre/EXP-0219/raw && find . -name 'sweep.jsonl' | sort | xargs shasum -a 256"
