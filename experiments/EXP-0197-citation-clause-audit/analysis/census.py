#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0197 -- per-value census of one field inside one experiment.

For every committed encoding of <mnem> found anywhere in experiments/<dir>, record
the value <field> takes, with the file and line where it first appears and how many
times it occurs.  Two extraction modes are reported separately:

  ANCHORED  the instruction appears in a clean tokenization of the blob from its
            start (strong: the byte offset is not guessed)
  MATCHFIT  db.json's own match constraints hold in some window (weak: an 8-bit
            match fits by chance; used only as corroboration, never alone)

Usage: census.py <exp-dir> <mnemonic> <field> [--under raw]
Read-only.
"""
import collections, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
sys.path.insert(0, HERE)
import scan as S  # noqa: E402


def census(expdir, mnem, field, under=None):
    specs = S.load_specs()
    spec = specs[mnem]
    L = spec["length"] or 4
    span = spec["fields"].get(field)
    root = os.path.join(ROOT, "experiments", expdir)
    if under:
        root = os.path.join(root, under)
    anch = collections.defaultdict(lambda: {"n": 0, "first": None, "encodings": set()})
    fit = collections.defaultdict(lambda: {"n": 0, "first": None, "encodings": set()})
    seen = set()
    nfiles = 0
    for p in S.iter_files(root):
        rel = os.path.relpath(p, ROOT)
        nfiles += 1
        try:
            data = open(p, errors="replace").read()
        except OSError:
            continue
        for ln, line in enumerate(data.splitlines(), 1):
            if len(line) > 400000:
                line = line[:400000]
            for h in S.blobs_from_strings([line], L):
                key = h
                if key in seen:
                    pass
                try:
                    buf = bytes.fromhex(h)
                except ValueError:
                    continue
                for off, fl in S.anchored_hits(buf, mnem):
                    if field not in fl:
                        continue
                    v = fl[field]
                    e = anch[v]
                    e["n"] += 1
                    e["encodings"].add(buf[off:off + L].hex())
                    if e["first"] is None:
                        e["first"] = {"file": rel, "line": ln, "offset": off,
                                      "enc": buf[off:off + L].hex()}
                if span:
                    st, w = span
                    for d, v0 in S.matchfit_hits(buf, spec):
                        v = (v0 >> st) & ((1 << w) - 1)
                        e = fit[v]
                        e["n"] += 1
                        e["encodings"].add(buf[d:d + L].hex())
                        if e["first"] is None:
                            e["first"] = {"file": rel, "line": ln, "offset": d,
                                          "enc": buf[d:d + L].hex()}
                seen.add(key)
    return nfiles, anch, fit


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    under = None
    if "--under" in sys.argv:
        under = sys.argv[sys.argv.index("--under") + 1]
        a = [x for x in a if x != under]
    expdir, mnem, field = a[0], a[1], a[2]
    nfiles, anch, fit = census(expdir, mnem, field, under)
    print("== %s  %s.%s   files=%d" % (expdir, mnem, field, nfiles))
    for tag, tbl in (("ANCHORED", anch), ("MATCHFIT", fit)):
        print("  %s: %d distinct values, %d occurrences, %d distinct encodings"
              % (tag, len(tbl), sum(e["n"] for e in tbl.values()),
                 len(set().union(*[e["encodings"] for e in tbl.values()]) if tbl else set())))
        for v in sorted(tbl)[:40]:
            e = tbl[v]
            print("    %-6s n=%-4d encs=%-3d first %s:%s off=%s enc=%s"
                  % (hex(v), e["n"], len(e["encodings"]), e["first"]["file"],
                     e["first"]["line"], e["first"]["offset"], e["first"]["enc"]))
        if len(tbl) > 40:
            print("    ... %d more values" % (len(tbl) - 40))


if __name__ == "__main__":
    main()
