#!/usr/bin/env python3
"""EXP-0180 offline stub for the agxrun_persist line protocol -- NO Metal, NO GPU.

Its only purpose is to prove `harness/saferunner.py` handles a TRUNCATED response the way
DEF-0178-1 requires: as `MALFORMED` -> outcome `measurement_failed`, with the raw lines
kept, never as a crash and never as a `hang`. Used by harness/selftest.py gate G9.

This is a CODE test. It is NOT evidence for any hardware claim.
"""
import sys


def main():
    truncate = "--truncate" in sys.argv
    print("READY FakeDevice", flush=True)
    for line in sys.stdin:
        parts = line.split()
        if not parts:
            continue
        n_ins = int(parts[4])
        j = 5 + n_ins
        n_outs = int(parts[j])
        outs = [p.split(":") for p in parts[j + 1:j + 1 + n_outs]]
        print("STATUS OK", flush=True)
        print("GPUTIME_NS 1234", flush=True)
        for idx, nbytes in outs:
            if truncate:
                print("OUT %s" % idx, flush=True)          # payload missing: DEF-0178-1
            else:
                print("OUT %s %s" % (idx, "ef" * int(nbytes)), flush=True)
        print("DONE %s" % parts[0], flush=True)


if __name__ == "__main__":
    main()
