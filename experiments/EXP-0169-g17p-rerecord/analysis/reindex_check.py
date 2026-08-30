#!/usr/bin/env python3
"""EXP-0169 ACCEPTANCE TEST: is this experiment's raw re-indexable by EXP-0164?

The dispatch's acceptance test is not "did we capture something" but "does
EXP-0164's own indexer attribute our records to the fields we claim". So:

  1. `analysis/collect_raw.py` here is a BYTE-IDENTICAL copy of
     `EXP-0164-inert-audit/analysis/collect_raw.py` (sha256 asserted below). It
     is unmodified; it lands in this directory only so that its own
     `WORK = <experiment>/work` convention writes our index instead of
     overwriting EXP-0164's committed one.
  2. This script runs it, then reports, for every field this experiment rules
     on, whether the index carries a BIT-EXACT attribution to EXP-0169, on how
     many (carrier,arm) cells, over how many gated runs and distinct values.
  3. A field claimed in field_verdicts.json with no bit-exact attribution is a
     FAILURE of this experiment, not a footnote, and is printed as one.

  python3 analysis/reindex_check.py

Writes analysis/reindex_report.json.
"""
import collections
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
WORK = os.path.join(EXP, "work")
SELF_EXP = os.path.basename(EXP)
UPSTREAM = os.path.join(EXPDIR, "EXP-0164-inert-audit", "analysis",
                        "collect_raw.py")
NONGATED = re.compile(r"(prefreeze|smoke|pilot|quarantine|burned)", re.I)


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def main():
    mine = os.path.join(HERE, "collect_raw.py")
    a, b = sha256(mine), sha256(UPSTREAM)
    if a != b:
        print("FATAL: analysis/collect_raw.py is NOT byte-identical to "
              "EXP-0164's (%s vs %s). The acceptance test is only meaningful "
              "against the unmodified indexer." % (a[:16], b[:16]))
        return 2
    print("collect_raw.py sha256 %s == EXP-0164's  (unmodified)" % a[:16])

    r = subprocess.run([sys.executable, mine], cwd=EXP,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    print(r.stdout.decode())
    if r.returncode != 0:
        print("FATAL: collect_raw.py failed")
        return 2

    idx = json.load(gzip.open(os.path.join(WORK, "raw_index.json.gz"), "rt"))
    mineidx = idx["index"].get(SELF_EXP, {})
    partial = set(idx["_meta"]["partial_runs"])

    claimed = {}
    fv = os.path.join(HERE, "field_verdicts.json")
    if os.path.exists(fv):
        claimed = {k: v for k, v in json.load(open(fv)).items()
                   if k != "_meta"}

    rep = {"_meta": {"collect_raw_sha256": a,
                     "experiment": SELF_EXP,
                     "indexed_keys": len(mineidx),
                     "parse": idx["parse"].get(SELF_EXP)},
           "fields": {}}
    miss, ok = [], []
    for key in sorted(set(claimed) | set(mineidx)):
        cell = mineidx.get(key)
        if cell is None:
            rep["fields"][key] = {"attributed": False,
                                  "why": "no record indexed under %s" % SELF_EXP}
            if key in claimed:
                miss.append(key)
            continue
        arms = {}
        bitexact = False
        for arm, runs in cell.items():
            g = {rn: e for rn, e in runs.items()
                 if not NONGATED.search(rn) and (SELF_EXP + "/" + rn) not in partial}
            arms[arm] = {
                "gated_runs": sorted(g),
                "n_gated_runs": len(g),
                "n_values": max([e["n_values"] for e in runs.values()] + [0]),
                "moved": {rn: e["moved"] for rn, e in sorted(runs.items())},
                "attribution": sorted({x for e in runs.values()
                                       for x in e["attribution"]}),
                "labels": sorted({x for e in runs.values() for x in e["labels"]}),
            }
            if "bit-exact" in arms[arm]["attribution"]:
                bitexact = True
        rep["fields"][key] = {"attributed": True, "bit_exact": bitexact,
                              "n_arms": len(cell),
                              "n_gated_runs": max(v["n_gated_runs"]
                                                  for v in arms.values()),
                              "arms": arms,
                              "claimed_in_field_verdicts": key in claimed}
        if key in claimed:
            (ok if bitexact else miss).append(key)

    rep["_meta"]["claimed"] = len(claimed)
    rep["_meta"]["claimed_bit_exact"] = len(ok)
    rep["_meta"]["claimed_unattributed"] = len(miss)
    with open(os.path.join(HERE, "reindex_report.json"), "w") as fh:
        json.dump(rep, fh, indent=1, sort_keys=True)

    print("EXP-0169 keys in the index : %d" % len(mineidx))
    print("fields ruled on            : %d" % len(claimed))
    print("  bit-exact attributed     : %d" % len(ok))
    print("  NOT attributed           : %d" % len(miss))
    for k in miss:
        print("     FAIL %s" % k)
    byarm = collections.Counter(
        len(v.get("arms", {})) for v in rep["fields"].values() if v["attributed"])
    print("arms per attributed field  : %s" % dict(sorted(byarm.items())))
    return 1 if miss else 0


if __name__ == "__main__":
    sys.exit(main())
