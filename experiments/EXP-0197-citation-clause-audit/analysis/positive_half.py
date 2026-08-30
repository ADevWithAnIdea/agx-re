#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0197 -- the POSITIVE half of every citation-repair clause: does the experiment
the repair points at ("the new one is where the evidence is") actually carry per-value
records for that field, and is it on the row's declared target?

EXP-0196 could not answer this (its instrument was field-name keyed and returned
NOT-FOUND for 15 of 28).  Here the same four keyings scan.py uses are applied.

Read-only.  Writes work/positive_half.json.
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
sys.path.insert(0, HERE)
import scan as S  # noqa: E402


def target_of(slug):
    s = slug.lower()
    if "g17p" in s or "a18" in s:
        return "G17P/A18"
    if "m4" in s:
        return "M4"
    if "m5" in s or "g17g" in s:
        return "M5"
    return "?"


def main():
    rows = json.load(open(os.path.join(EXP, "work", "rows.json")))
    specs = S.load_specs()
    out = {}
    for r in rows:
        if not r["live_slugs"]:
            continue
        spec = specs[r["instr"]]
        span = (r["start"], r["width"]) if r["start"] is not None else None
        per = {}
        for slug, dirs in r["live_dirs"].items():
            for d in dirs:
                a = S.scan_dir(d, r["instr"], r["field"], span, spec)
                per[d] = {"k1_named": a["k1_named"]["n"],
                          "k1_distinct": a["k1_named"]["distinct_values"],
                          "k2_byte": a["k2_byte"]["n"],
                          "k2_distinct": a["k2_byte"]["distinct_values"],
                          "k4_anch": a["k4_anchored"]["blobs"],
                          "k4_anch_distinct": a["k4_anchored"]["distinct_values"],
                          "first_named": a["k1_named"]["first"],
                          "target_from_slug": target_of(d)}
                print("  %-34s NEW=%-40s K1=%-6d(%d) K2=%-6d(%d) K4=%-5d(%d) tgt=%s"
                      % (r["key"], d, per[d]["k1_named"], per[d]["k1_distinct"],
                         per[d]["k2_byte"], per[d]["k2_distinct"],
                         per[d]["k4_anch"], per[d]["k4_anch_distinct"],
                         per[d]["target_from_slug"]))
                sys.stdout.flush()
        out[r["key"]] = {"row_target": r["target"], "label": r["label"],
                         "orig": r["orig_slugs"], "new": r["live_slugs"], "per": per}
    json.dump(out, open(os.path.join(EXP, "work", "positive_half.json"), "w"),
              indent=1, default=str)


if __name__ == "__main__":
    main()
