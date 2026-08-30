#!/usr/bin/env python3
"""Offline stand-in for agxrun_persist: speaks the same line protocol so the
SafePersistRunner request/parse path can be exercised with NO GPU and NO device."""
import sys
print("READY FakeDevice", flush=True)
mode = sys.argv[-1]
n = 0
for line in sys.stdin:
    n += 1
    t = line.split()
    rid = t[0]
    outs = []
    i = t.index(t[4+int(t[4])+1]) if False else None
    nin = int(t[4]); j = 5 + nin
    nout = int(t[j]); specs = t[j+1:j+1+nout]
    print("REQ %s" % rid, flush=True)
    print("STATUS OK", flush=True)
    print("GPUTIME_NS 1234", flush=True)
    for sp in specs:
        idx, nb = sp.split(":")
        nb = int(nb)
        if mode == "--truncate" and n >= 2 and idx == "0":
            print("OUT %s" % idx, flush=True)          # the malformed shape
        else:
            print("OUT %s %s" % (idx, ("a5" * nb)), flush=True)
    print("DONE %s" % rid, flush=True)
