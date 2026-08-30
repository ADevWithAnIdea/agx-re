#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0197 -- reproduce EXP-0189's own admission filter over every ORIGINAL citation.

EXP-0189/analysis/collect_raw.py indexes a raw record ONLY if all four hold:
   1. the file is under <exp>/raw/** and its name ends in `.jsonl`
   2. rec["instr"] is a str
   3. rec["field"] is a str
   4. rec["field"] does not start with "_"
Anything else is `continue`d before any byte-level attribution happens.

This script counts, per originally-cited experiment, how many records clear each of
those gates -- i.e. how many records EXP-0189 could see AT ALL, before it ever asked
about a particular field.  A directory with 0 admissible records cannot produce a
"per-value record" for ANY field, so the clause it justifies is a property of the
collector, not of the experiment.

Read-only.  Writes work/collector_blindspot.json.
"""
import json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
EXPS = os.path.join(ROOT, "experiments")


def audit(expdir):
    raw = os.path.join(EXPS, expdir, "raw")
    st = {"has_raw_dir": os.path.isdir(raw), "raw_files": 0, "jsonl_files": 0,
          "jsonl_lines": 0, "recs_with_str_instr": 0, "recs_with_str_field": 0,
          "recs_admissible": 0, "recs_field_null": 0, "recs_field_underscore": 0,
          "non_jsonl_raw_files": collections.Counter()}
    if not st["has_raw_dir"]:
        return st
    for dirpath, _, files in os.walk(raw):
        for fn in files:
            st["raw_files"] += 1
            p = os.path.join(dirpath, fn)
            if not fn.endswith(".jsonl"):
                st["non_jsonl_raw_files"][os.path.splitext(fn)[1] or "(noext)"] += 1
                continue
            st["jsonl_files"] += 1
            for line in open(p, errors="replace"):
                line = line.strip()
                if not line:
                    continue
                st["jsonl_lines"] += 1
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if not isinstance(r, dict):
                    continue
                ins, fld = r.get("instr"), r.get("field")
                if isinstance(ins, str):
                    st["recs_with_str_instr"] += 1
                if isinstance(fld, str):
                    st["recs_with_str_field"] += 1
                elif fld is None and isinstance(ins, str):
                    st["recs_field_null"] += 1
                if isinstance(ins, str) and isinstance(fld, str):
                    if fld.startswith("_"):
                        st["recs_field_underscore"] += 1
                    else:
                        st["recs_admissible"] += 1
    st["non_jsonl_raw_files"] = dict(st["non_jsonl_raw_files"])
    return st


def main():
    rows = json.load(open(os.path.join(EXP, "work", "rows.json")))
    dirs = sorted({d for r in rows for ds in r["orig_dirs"].values() for d in ds})
    out = {}
    print("%-40s raw? files jsonl  lines  admissible field:null field:_  non-jsonl" % "original citation")
    for d in dirs:
        st = audit(d)
        out[d] = st
        print("%-40s %-5s %-5d %-5d %-7d %-10d %-10d %-8d %s"
              % (d, st["has_raw_dir"], st["raw_files"], st["jsonl_files"],
                 st["jsonl_lines"], st["recs_admissible"], st["recs_field_null"],
                 st["recs_field_underscore"], st["non_jsonl_raw_files"]))
    json.dump(out, open(os.path.join(EXP, "work", "collector_blindspot.json"), "w"),
              indent=1)


if __name__ == "__main__":
    main()
