#!/usr/bin/env python3
"""A device-free stand-in for `agxrun_persist`, so DEF-0178-1 can be PROVEN
fixed without a GPU and without burning the exclusive window.

Speaks the same line protocol. Behaviour is selected by `EXP0179_FAKE_MODE`:
  good        -- normal responses
  truncate    -- emits `OUT 0` with the hex payload MISSING (the exact shape the
                 racing reader produces), which the SHARED parser turns into
                 `ValueError: not enough values to unpack`
  hang_first  -- the FIRST request never answers (a genuine watchdog timeout);
                 every later request is normal. This is the cascade test: under
                 the shared runner the abandoned reader attaches to the
                 replacement child and poisons the requests that follow.
"""
import os
import sys
import time

MODE = os.environ.get("EXP0179_FAKE_MODE", "good")

sys.stdout.write("READY FakeDevice\n")
sys.stdout.flush()

n = 0
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    n += 1
    rid = line.split()[0]
    if MODE == "hang_first" and n == 1:
        time.sleep(3600)                       # never answers
    sys.stdout.write("REQ %s\n" % rid)
    sys.stdout.write("STATUS OK\n")
    sys.stdout.write("GPUTIME_NS 4242\n")
    if MODE == "truncate":
        sys.stdout.write("OUT 0\n")            # payload missing
    else:
        sys.stdout.write("OUT 0 %s\n" % ("deadbeef" * 2))
    sys.stdout.write("DONE %s\n" % rid)
    sys.stdout.flush()
