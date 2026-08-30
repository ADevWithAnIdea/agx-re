#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0197 step 0 -- enumerate every validation.json entry whose `note` carries the
clause "has no per-value records", and resolve, for each, the ORIGINAL citation(s)
the clause names plus the db.json bit span of the field.

Read-only.  Writes work/rows.json.
"""
import glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXPS = os.path.join(ROOT, "experiments")

# two distinct phrasings are in use
RX_REPAIR = re.compile(
    r"citation repair: the records supporting this row live in (.+?); "
    r"the original citation (.+?) has no per-value records for it")
RX_FLAG = re.compile(
    r"EXP-0189: every CITED directory \((.+?)\) has no per-value records for this descriptor")


def spans():
    db = json.load(open(os.path.join(ROOT, "tools/agx-isa/db.json")))
    out = {}
    for i in db["instructions"]:
        out[i["mnemonic"]] = {
            "length": i.get("length"), "match": i.get("match") or [],
            "fields": {f["name"]: (f["start"], f["width"]) for f in i.get("fields", [])},
        }
    return out


def resolve(slug):
    """The project validator's own rule: glob(experiments/<slug>*)."""
    return sorted(os.path.basename(d)
                  for d in glob.glob(os.path.join(EXPS, slug.split("/")[0] + "*"))
                  if os.path.isdir(d))


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    DB = spans()
    rows = []
    for m, entry in sorted(val["instructions"].items()):
        for f, r in sorted(entry.items()):
            if not isinstance(r, dict):
                continue
            note = r.get("note") or ""
            if "has no per-value records" not in note:
                continue
            mo, mo2 = RX_REPAIR.search(note), RX_FLAG.search(note)
            if mo:
                orig = [x.strip() for x in mo.group(2).split(",")]
                live = [x.strip() for x in mo.group(1).split(",")]
                kind = "repair"
            elif mo2:
                orig = [x.strip() for x in mo2.group(1).split(",")]
                live = []
                kind = "flag"
            else:
                orig, live, kind = [], [], "UNPARSED"
            spec = DB.get(m, {})
            span = spec.get("fields", {}).get(f)
            if span:
                s, w = span
                bytes_of = list(range(s // 8, (s + w - 1) // 8 + 1))
            else:
                s = w = None
                bytes_of = []
            rows.append({
                "key": "%s.%s" % (m, f), "instr": m, "field": f,
                "label": r.get("label"), "target": r.get("target"),
                "evidence": r.get("evidence"), "kind": kind,
                "orig_slugs": orig, "orig_dirs": {o: resolve(o) for o in orig},
                "live_slugs": live, "live_dirs": {o: resolve(o) for o in live},
                "start": s, "width": w, "bytes_of_span": bytes_of,
                "instr_length": spec.get("length"), "match": spec.get("match"),
                "corrected_by_0196": "CORRECTED 2026-08-30 (EXP-0196)" in note,
                "note": note,
            })
    json.dump(rows, open(os.path.join(HERE, "..", "work", "rows.json"), "w"),
              indent=1)
    print("rows: %d  (repair=%d flag=%d unparsed=%d)" % (
        len(rows),
        sum(1 for r in rows if r["kind"] == "repair"),
        sum(1 for r in rows if r["kind"] == "flag"),
        sum(1 for r in rows if r["kind"] == "UNPARSED")))
    for r in rows:
        print("  %-34s %-18s orig=%-40s span=%s..%s bytes=%s %s" % (
            r["key"], r["label"], ",".join(r["orig_slugs"]),
            r["start"], r["width"], r["bytes_of_span"],
            "[0196-corrected]" if r["corrected_by_0196"] else ""))
        for o, ds in r["orig_dirs"].items():
            if not ds:
                print("      !! original citation %r resolves to NO directory" % o)


if __name__ == "__main__":
    main()
