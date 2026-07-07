#!/bin/bash
# RT-ISA-FIX device harness: build each MSL kernel with shdump (--no-fast-math),
# extract the compute _agc.main AGX bytes. Run on the A18 Pro device under
# ~/cleanroom_work/isafix (shdump/agxrun/agxrun_persist/agxtest.py/agxparse.py present).
set -e
cd ~/cleanroom_work/isafix
for f in k/*.metal; do
  name=$(basename "$f" .metal)
  ./shdump --no-fast-math -o k/$name.bin "$f" >/dev/null 2>k/$name.err
  echo "$name $(python3 agxparse.py k/$name.bin --stage compute --extract-hex 2>/dev/null)"
done
