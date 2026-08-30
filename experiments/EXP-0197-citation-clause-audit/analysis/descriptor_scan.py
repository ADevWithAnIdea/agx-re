#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0197 -- the two `_instruction` (whole-descriptor) rows need a different
question from the field rows: not "does one field's bits vary" but "does the
descriptor's own byte string appear more than once, with more than one value?".

scan.py skips db-match fitting when the row has no bit span (an `_instruction`
row has none), so this runs that fit explicitly over the same harvested blobs and
prints EVERY distinct matching encoding with its file and line.

Read-only.
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
sys.path.insert(0, HERE)
import scan as S  # noqa: E402

TARGETS = [("call_indirect", ["EXP-0035-function-abi"]),
           ("spill_frame_marker", ["EXP-M4-14-a18-splice", "EXP-0041-scratch-helper-abi"])]


def main():
    specs = S.load_specs()
    out = {}
    for mnem, dirs in TARGETS:
        spec = specs[mnem]
        L = spec["length"]
        for d in dirs:
            root = os.path.join(ROOT, "experiments", d)
            hits = collections.defaultdict(list)   # encoding hex -> [(file,line,off)]
            nblob = 0
            for p in S.iter_files(root):
                rel = os.path.relpath(p, ROOT)
                ext = os.path.splitext(p)[1].lower()
                try:
                    if ext in (".jsonl", ".json"):
                        txt = open(p, errors="replace").read()
                        lines = txt.splitlines()
                    else:
                        lines = open(p, errors="replace").read().splitlines()
                except OSError:
                    continue
                for ln, line in enumerate(lines, 1):
                    if len(line) > 200000:
                        line = line[:200000]
                    for h in S.blobs_from_strings([line], L):
                        nblob += 1
                        try:
                            buf = bytes.fromhex(h)
                        except ValueError:
                            continue
                        for off, v in S.matchfit_hits(buf, spec):
                            enc = buf[off:off + L].hex()
                            if len(hits[enc]) < 5:
                                hits[enc].append({"file": rel, "line": ln,
                                                  "offset": off, "blob": h[:80]})
            out["%s@%s" % (mnem, d)] = {
                "blobs_seen": nblob,
                "distinct_encodings": len(hits),
                "encodings": {k: v for k, v in sorted(hits.items())},
            }
            print("%-22s %-32s blobs=%-7d distinct_encodings=%d  %s"
                  % (mnem, d, nblob, len(hits), sorted(hits)[:8]))
    json.dump(out, open(os.path.join(EXP, "work", "descriptor_scan.json"), "w"),
              indent=1)


if __name__ == "__main__":
    main()
