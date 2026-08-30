#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0196 -- final classification of every `note` in tools/agx-isa/validation.json.

Buckets (the brief's):
  SUPPORTED           every checkable claim in the note was tested and holds
  OVERSTATED          at least one checkable claim is contradicted by committed raw
                      (in either direction: claims an observation the raw does not
                      contain, or claims an ABSENCE the raw contradicts)
  UNCHECKABLE         the note makes no claim this audit's instruments can falsify
  CITES-MISSING-FILE  the note names an experiment dir or raw path that does not exist

Consumes the per-check outputs; it does not re-measure.  Read-only.
Writes analysis/classification.json + analysis/classification.tsv.
"""
import collections, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def load(name):
    p = os.path.join(HERE, name)
    return json.load(open(p)) if os.path.exists(p) else {}


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    prov = load("note_provenance.json")
    c0169 = load("check_0169.json")
    c0168 = load("check_0168.json")
    cout = load("outcomes_check2.json")
    ccit = load("citation_repair_check2.json")
    czero = load("e0189_zero_check.json")
    ccov = load("coverage_keys_check.json")

    # hand-adjudicated results that no single script owns
    HAND_OVERSTATED = {
        "sel.b1": "255/128 and 1/128 vs raw 128/128 and 128/128 (EXP-0140 sel.body.b3)",
        "sel.b2": "same note text as sel.b1",
        "sel.selFalse": "same note text as sel.b1",
        "sel._instruction": "'255 of 128 values >= 0x80 and 1 of 128 < 0x80'",
    }
    HAND_SUPPORTED = {  # checked by hand against raw in RESULTS.md
        "matrix_mac.c_neg_all", "matrix_mac.c_neg_half", "matrix_mac.dst_en",
        "falu3.dst", "falu3.ctrl_len", "falu3_ext.dst", "falu3_ext.ctrl_len",
        "h_coord_hi._instruction", "rtq_state_move._instruction",
        "sr_read_wide._instruction", "fspecial_est.b5",
    }
    RV = re.compile(r"Compared against the contaminated run03/run05 on (\d+) measurements")
    EMIT = ("hardware-run", "isolated-byte-diff")

    rows = []
    for m, entry in sorted(val["instructions"].items()):
        for f, r in sorted(entry.items()):
            if not isinstance(r, dict):
                continue
            nt = (r.get("note") or "").strip()
            if not nt:
                continue
            key = "%s.%s" % (m, f)
            grade = "EMIT" if (r.get("label") in EMIT and f != "_instruction") else \
                    ("EMIT_INSTR" if r.get("label") in EMIT else "OTHER")
            checks, verdicts = [], []

            def add(name, v):
                checks.append(name)
                verdicts.append(v)

            if key in c0169:
                add("ladder-moved-vs-raw", c0169[key]["verdict"])
            if key in c0168:
                add("agreement-vs-raw", c0168[key]["verdict"])
            if key in cout:
                for row in cout[key]["rows"]:
                    add("outcomes-histogram-vs-raw", row["verdict"])
            if key in ccit:
                add("citation-repair-negative-half",
                    "SUPPORTED" if ccit[key]["negative_half"] == "SUPPORTED" else "CONTRADICTED")
            if key in czero and czero[key]["verdict"] != "NOT-A-ZERO-CLAIM":
                add("zero-dispatch-claim-vs-raw",
                    "SUPPORTED" if czero[key]["verdict"] == "SUPPORTED" else "CONTRADICTED")
            if RV.search(nt):
                add("rv01-measurements-vs-EXP-0144", "SUPPORTED")   # all 28 reconciled
            if "EXP-0164 withheld:" in nt:
                add("EXP-0164-withheld-numbers", "SUPPORTED")       # all 66 exact
            if key in ccov and ccov[key]["verdict"] == "SUPPORTED":
                add("coverage-keys-vs-raw", "SUPPORTED")
            if key in HAND_OVERSTATED:
                add("hand-adjudicated", "CONTRADICTED")
            elif key in HAND_SUPPORTED:
                add("hand-adjudicated", "SUPPORTED")

            missing = prov.get(key, {}).get("provenance") == "MISSING-FILE"
            if missing:
                bucket = "CITES-MISSING-FILE"
            elif not checks:
                bucket = "UNCHECKABLE"
            elif any(v != "SUPPORTED" for v in verdicts):
                bucket = "OVERSTATED"
            else:
                bucket = "SUPPORTED"
            rows.append({"key": key, "grade": grade, "label": r.get("label"),
                         "evidence": r.get("evidence"), "bucket": bucket,
                         "checks": checks, "verdicts": verdicts,
                         "note_provenance": prov.get(key, {}).get("provenance"),
                         "note": nt})
    json.dump(rows, open(os.path.join(HERE, "classification.json"), "w"), indent=1)
    with open(os.path.join(HERE, "classification.tsv"), "w") as fh:
        fh.write("key\tgrade\tlabel\tbucket\tchecks\n")
        for x in rows:
            fh.write("%s\t%s\t%s\t%s\t%s\n" % (x["key"], x["grade"], x["label"],
                                               x["bucket"], ";".join(x["checks"])))
    c = collections.Counter((x["grade"], x["bucket"]) for x in rows)
    tot = collections.Counter(x["bucket"] for x in rows)
    print("ALL NOTES (%d):" % len(rows))
    for k in sorted(tot):
        print("  %-20s %d" % (k, tot[k]))
    print()
    for g in ("EMIT", "EMIT_INSTR", "OTHER"):
        print("%s:" % g)
        for b in ("SUPPORTED", "OVERSTATED", "UNCHECKABLE", "CITES-MISSING-FILE"):
            print("  %-20s %d" % (b, c[(g, b)]))
    print()
    print("OVERSTATED rows:")
    for x in rows:
        if x["bucket"] == "OVERSTATED":
            print("  %-8s %-32s %-20s %s"
                  % (x["grade"], x["key"], x["label"],
                     [ck for ck, v in zip(x["checks"], x["verdicts"]) if v != "SUPPORTED"]))


if __name__ == "__main__":
    main()
