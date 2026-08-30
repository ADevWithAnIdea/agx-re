#!/usr/bin/env python3
"""Device-free stand-in for `agxrun_persist`, so DEF-0178-1 can be proved fixed with NO
GPU, NO Metal and NO device -- and without burning device time to test host-side plumbing.

UPSTREAMED 2026-08-30 by EXP-0185, merging `EXP-0178-.../harness/fakerunner.py` and
`EXP-0179-.../harness/fakechild.py` (our own code, this repository).

It speaks the same line protocol as `agxrun_persist`:

    READY <device>                                            # once, at startup
    request:  <id> <archive> <grid> <tg> <nin> [idx:file ...] <nout> [idx:nbytes ...]
    response: REQ <id> / STATUS ... / [GPUTIME_NS n] / [OUT idx hex ...] / DONE <id>

Behaviour is selected by `--mode` or `AGXTEST_FAKE_MODE`:

  good        normal responses (`STATUS OK`, a full `OUT idx <hex>` per requested buffer).
  truncate    emits `OUT <idx>` with the hex payload MISSING -- the exact shape the racing
              reader produces. The SHARED parser turns this into
              `ValueError: not enough values to unpack (expected 3, got 2)`; a fixed runner
              must record it as `MALFORMED` and keep the raw lines. Starts at request
              `AGXTEST_FAKE_TRUNCATE_FROM` (default 1).
  hang_first  the FIRST request EVER -- across child restarts, tracked in the file named by
              `--state` / `AGXTEST_FAKE_STATE` -- never answers, i.e. a genuine watchdog
              timeout. Every later request, including in the REPLACEMENT child the runner
              spawns, is normal. This is the cascade test: the only thing that can corrupt
              the requests AFTER the hang is the runner itself.
  eof_first   the child EXITS after the first request instead of answering (DEF-0153-2:
              `readline()` then returns `""` forever; an exited child must be reported as a
              wedge, never as an empty line the parser falls through).

Any other command-line arguments (`--source`, `--function`, `--no-fast-math`, ...) are
accepted and ignored, so a runner class can spawn this exactly as it spawns the real one.

Clean-room: our own code, no Apple binary involved.
"""
import os
import sys
import time

argv = sys.argv[1:]
MODE = os.environ.get("AGXTEST_FAKE_MODE", "good")
STATE = os.environ.get("AGXTEST_FAKE_STATE", "")
TRUNC_FROM = int(os.environ.get("AGXTEST_FAKE_TRUNCATE_FROM", "1"))
DEVICE = os.environ.get("AGXTEST_FAKE_DEVICE", "FakeDevice")

i = 0
while i < len(argv):                      # tolerant: pick ours, ignore the runner's
    if argv[i] == "--mode" and i + 1 < len(argv):
        MODE = argv[i + 1]
        i += 1
    elif argv[i] == "--state" and i + 1 < len(argv):
        STATE = argv[i + 1]
        i += 1
    i += 1

sys.stdout.write("READY %s\n" % DEVICE)
sys.stdout.flush()

n = 0
for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    n += 1
    t = line.split()
    rid = t[0]

    # <id> <archive> <grid> <tg> <nin> [idx:file]*nin <nout> [idx:nbytes]*nout
    try:
        nin = int(t[4])
        j = 5 + nin
        nout = int(t[j])
        specs = t[j + 1:j + 1 + nout]
    except (IndexError, ValueError):
        specs = ["0:8"]

    if MODE == "hang_first":
        # once, GLOBALLY -- so the replacement child does not hang again
        if not STATE or not os.path.exists(STATE):
            if STATE:
                open(STATE, "w").write("hung")
            time.sleep(3600)              # never answers: a genuine watchdog timeout

    if MODE == "eof_first" and n == 1:
        sys.exit(0)                       # child dies without answering

    sys.stdout.write("REQ %s\n" % rid)
    sys.stdout.write("STATUS OK\n")
    sys.stdout.write("GPUTIME_NS 4242\n")
    first = True
    for sp in specs:
        idx, nb = sp.split(":")
        nb = int(nb)
        if MODE == "truncate" and n >= TRUNC_FROM and first:
            sys.stdout.write("OUT %s\n" % idx)          # the malformed shape
        else:
            sys.stdout.write("OUT %s %s\n" % (idx, "a5" * nb))
        first = False
    sys.stdout.write("DONE %s\n" % rid)
    sys.stdout.flush()
