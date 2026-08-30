#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0196 -- build a per-experiment index of which FIELD / INSTR / ARM / GROUP
names appear in per-value raw records, so an existential note claim ("the
records supporting this row live in EXP-XXXX", "the original citation EXP-YYYY
has no per-value records for it") can be tested rather than believed.

Regex-scans `experiments/*/raw/**/*.jsonl` for the record keys the sweep
harnesses use.  A regex rather than json.loads because 1.7 GB of raw is the
whole point: the index has to be cheap enough to rebuild.

Read-only.  Writes work/raw_field_index.json.gz
"""
import collections, glob, gzip, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXPS = os.path.join(ROOT, "experiments")
OUT = os.path.join(HERE, "..", "work", "raw_field_index.json.gz")

KEYS = ("field", "instr", "group", "arm", "mnemonic", "descriptor", "name", "target_field")
RX = re.compile(r'"(%s)"\s*:\s*"([^"]{1,80})"' % "|".join(KEYS))


def main():
    idx = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    files = sorted(glob.glob(os.path.join(EXPS, "*", "raw", "**", "*.jsonl"), recursive=True))
    print("%d raw jsonl files" % len(files), file=sys.stderr)
    for i, p in enumerate(files):
        rel = os.path.relpath(p, EXPS)
        exp = rel.split(os.sep)[0]
        with open(p, "rb") as fh:
            for ln in fh:
                for k, v in RX.findall(ln.decode("utf-8", "replace")):
                    idx[exp][k][v] += 1
        if (i + 1) % 50 == 0:
            print("  %d/%d" % (i + 1, len(files)), file=sys.stderr)
    out = {e: {k: dict(c) for k, c in d.items()} for e, d in idx.items()}
    with gzip.open(OUT, "wt") as fh:
        json.dump(out, fh)
    print("wrote %s (%d experiments)" % (OUT, len(out)), file=sys.stderr)


if __name__ == "__main__":
    main()
