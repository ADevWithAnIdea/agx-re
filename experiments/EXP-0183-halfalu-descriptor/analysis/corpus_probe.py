#!/usr/bin/env python3
"""EXP-0183 corpus probe -- runs INSIDE a tree (cwd = the agx-isa tree) as a
SUBPROCESS, so no tree ever re-measures another tree's database.

DEF-0175-2 is the reason: EXP-0175's ab_gate ran the round trip in-process, so
`import isadb` resolved to the FIRST tree measured and every later candidate was
scored against the first tree's db.json -- it reported ALL PASS for a candidate
that crashed. EXP-0182's gate fixed the round trip but still loads isadb.py
in-process for the corpus half. This probe puts BOTH halves in a subprocess.

Usage:  cd <tree> && python3 corpus_probe.py <hexdir>   -> one JSON line on stdout
"""
import collections, json, os, sys

sys.path.insert(0, os.getcwd())
import isadb  # noqa: E402  (the tree's own copy, resolved from cwd)

HEXDIR = sys.argv[1]

clean = leftover = files = 0
firings = collections.Counter()
per_file = {}
for fn in sorted(os.listdir(HEXDIR)):
    if not fn.endswith(".hex"):
        continue
    files += 1
    buf = bytes.fromhex("".join(open(os.path.join(HEXDIR, fn)).read().split()))
    off, n = 0, len(buf)
    while off < n:
        try:
            rec, length = isadb.decode_one(buf, off)
        except Exception:
            break
        if not length:
            break
        firings[rec["mnemonic"]] += 1
        off += length
    leftover += n - off
    per_file[fn] = [off, n]
    if off == n:
        clean += 1

print(json.dumps({
    "isadb_file": os.path.abspath(isadb.__file__),
    "files": files, "clean": clean, "leftover": leftover,
    "tokens": sum(firings.values()),
    "firings": dict(firings),
    "per_file": per_file,
}))
