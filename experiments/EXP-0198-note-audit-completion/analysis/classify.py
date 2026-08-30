#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0198 -- roll the per-family checks into one classification of the 167
notes EXP-0196 listed in work/not_checked.json.

Buckets, EXP-0196's definitions verbatim:
  SUPPORTED           every checkable claim tested and holds
  OVERSTATED          >=1 claim contradicted by committed evidence
  UNCHECKABLE         no falsifiable claim
  CITES-MISSING-FILE  names a file/experiment dir that does not exist
plus, kept separate rather than folded into UNCHECKABLE (which would be
cannot-fail bookkeeping):
  INSTRUMENT-LIMITED  a falsifiable claim for which THIS audit could build no
                      instrument that could have returned "no"

Read-only.  Writes analysis/classification.json / .tsv.
"""
import collections, glob, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EMIT = ("hardware-run", "isolated-byte-diff")


def load(n):
    p = os.path.join(HERE, n)
    return json.load(open(p)) if os.path.exists(p) else {}


def main():
    val = json.load(open(os.environ.get("EXP0198_VALIDATION", os.path.join(ROOT, "tools/agx-isa/validation.json"))))
    nc = json.load(open(os.path.join(
        ROOT, "experiments/EXP-0196-note-integrity-audit/work/not_checked.json")))
    src = {}
    for name, d in (("check_0139", load("check_0139.json")),
                    ("check_0157", load("check_0157.json")),
                    ("check_0162", load("check_0162.json").get("per_note", {})),
                    ("check_0155", load("check_0155.json")),
                    ("check_e0189_nonzero", load("check_e0189_nonzero.json")),
                    ("check_0140", load("check_0140.json")),
                    ("check_0138", load("check_0138.json")),
                    ("check_0141", load("check_0141.json")),
                    ("check_0147", load("check_0147.json")),
                    ("check_fspecial", load("check_fspecial.json")),
                    ("check_misc", load("check_misc.json"))):
        for k, v in d.items():
            if k.startswith("_"):
                continue
            src.setdefault(k, []).append((name, v.get("verdict")))
    # the withheld-clause check adds claims to rows already covered elsewhere
    for k, v in load("check_withheld.json").items():
        src.setdefault(k, []).append(("check_withheld", v.get("verdict")))

    rows = []
    for key in nc:
        m, f = key.split(".", 1)
        r = val["instructions"][m][f]
        grade = ("EMIT" if (r.get("label") in EMIT and f != "_instruction")
                 else "EMIT_INSTR" if r.get("label") in EMIT else "OTHER")
        checks = src.get(key, [])
        verds = [v for _, v in checks]
        if not checks:
            bucket = "NOT-CHECKED"
        elif "CONTRADICTED" in verds:
            bucket = "OVERSTATED"
        elif "INSTRUMENT-LIMITED" in verds:
            bucket = "INSTRUMENT-LIMITED"
        elif "NO-INSTRUMENT" in verds or "NO-NUMERIC-CLAIM" in verds:
            bucket = "UNCHECKABLE"
        else:
            bucket = "SUPPORTED"
        rows.append({"key": key, "grade": grade, "label": r.get("label"),
                     "evidence": r.get("evidence"), "bucket": bucket,
                     "checks": [c for c, _ in checks], "verdicts": verds,
                     "note": (r.get("note") or "").strip()})
    json.dump(rows, open(os.path.join(HERE, "classification.json"), "w"), indent=1)
    with open(os.path.join(HERE, "classification.tsv"), "w") as fh:
        fh.write("key\tgrade\tlabel\tbucket\tchecks\n")
        for x in rows:
            fh.write("%s\t%s\t%s\t%s\t%s\n" % (x["key"], x["grade"], x["label"],
                                               x["bucket"], ";".join(x["checks"])))
    tot = collections.Counter(x["bucket"] for x in rows)
    per = collections.Counter((x["grade"], x["bucket"]) for x in rows)
    print("THE 167 NOT-CHECKED NOTES (%d):" % len(rows))
    for b in sorted(tot):
        print("  %-20s %d" % (b, tot[b]))
    print()
    for g in ("EMIT", "EMIT_INSTR", "OTHER"):
        n = sum(v for (gg, _), v in per.items() if gg == g)
        print("%s (%d):" % (g, n),
              {b: per[(g, b)] for b in sorted(tot) if per[(g, b)]})
    print()
    print("OVERSTATED:")
    for x in rows:
        if x["bucket"] == "OVERSTATED":
            print("  %-10s %-30s %s" % (x["grade"], x["key"], x["label"]))
    print("INSTRUMENT-LIMITED:")
    for x in rows:
        if x["bucket"] == "INSTRUMENT-LIMITED":
            print("  %-10s %-30s %s" % (x["grade"], x["key"], x["label"]))


if __name__ == "__main__":
    main()
