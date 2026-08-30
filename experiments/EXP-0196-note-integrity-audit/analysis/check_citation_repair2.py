#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0196 -- second, sharper pass at the NEGATIVE half of every "EXP-0189
citation repair" note: "the original citation <EXP> has no per-value records
for it".

Pass 1 (check_citation_repair.py) matched on the field NAME alone and produced
both false alarms (a `dst` record belonging to another instruction) and false
clears (a byte-indexed record under an underscore name). This pass pairs
`instr` with the field and additionally counts BYTE-INDEXED records
(`__raw_b<N>`, `byte_index`) whose byte overlaps the field's db.json bit span --
the records EXP-0164/0189's underscore filter drops, and the same blind spot
DEF-0190-1 documents for INERT verdicts.

Read-only.  Writes analysis/citation_repair_check2.json.
"""
import glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXPS = os.path.join(ROOT, "experiments")
RX = re.compile(r"citation repair: the records supporting this row live in (.+?); "
                r"the original citation (.+?) has no per-value records for it")


def spans():
    db = json.load(open(os.path.join(ROOT, "tools/agx-isa/db.json")))
    out = {}
    for i in db["instructions"]:
        for f in i.get("fields", []):
            out["%s.%s" % (i["mnemonic"], f["name"])] = (f["start"], f["width"])
    return out


def scan(expdir, mnem, fld, span):
    """-> counts of per-value records in expdir/raw/**/*.jsonl for mnem."""
    res = {"files": [], "named": 0, "byte_overlap": 0, "instr_total": 0,
           "other_field_names": {}}
    bytes_of_span = set()
    if span:
        s, w = span
        bytes_of_span = {b for b in range((s) // 8, (s + w - 1) // 8 + 1)}
    for p in sorted(glob.glob(os.path.join(EXPS, expdir, "raw", "**", "*.jsonl"),
                              recursive=True)):
        nn = nb = ni = 0
        for ln in open(p, "rb"):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("instr") != mnem:
                continue
            ni += 1
            f = r.get("field")
            if f == fld:
                nn += 1
            elif isinstance(f, str) and f.startswith("__raw_b") or r.get("byte_index") is not None:
                bi = r.get("byte_index")
                if bi is None and isinstance(f, str) and f.startswith("__raw_b"):
                    try:
                        bi = int(f[7:])
                    except Exception:
                        bi = None
                if bi is not None and bi in bytes_of_span:
                    nb += 1
            if isinstance(f, str) and f != fld:
                res["other_field_names"][f] = res["other_field_names"].get(f, 0) + 1
        if ni:
            res["files"].append({"file": os.path.relpath(p, ROOT), "instr_records": ni,
                                 "named_field_records": nn, "byte_overlap_records": nb})
        res["named"] += nn
        res["byte_overlap"] += nb
        res["instr_total"] += ni
    return res


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    SP = spans()
    out = {}
    for m, entry in sorted(val["instructions"].items()):
        for f, r in sorted(entry.items()):
            if not isinstance(r, dict):
                continue
            mo = RX.search(r.get("note") or "")
            if not mo:
                continue
            key = "%s.%s" % (m, f)
            span = SP.get(key)
            orig = [x.strip() for x in mo.group(2).split(",")]
            live = [x.strip() for x in mo.group(1).split(",")]
            rec = {"label": r.get("label"), "span": span,
                   "claim_original_has_none": orig, "claim_live_in": live,
                   "original": {}, "live_in": {}}
            for slug in orig:
                for d in sorted(glob.glob(os.path.join(EXPS, slug.split("/")[0] + "*"))):
                    if os.path.isdir(d):
                        rec["original"][os.path.basename(d)] = scan(os.path.basename(d), m, f, span)
            for slug in live:
                for d in sorted(glob.glob(os.path.join(EXPS, slug.split("/")[0] + "*"))):
                    if os.path.isdir(d):
                        rec["live_in"][os.path.basename(d)] = scan(os.path.basename(d), m, f, span)
            named = sum(v["named"] for v in rec["original"].values())
            byteo = sum(v["byte_overlap"] for v in rec["original"].values())
            rec["negative_half"] = ("CONTRADICTED-named" if named else
                                    ("CONTRADICTED-byte-indexed" if byteo else "SUPPORTED"))
            rec["positive_half"] = ("SUPPORTED" if any(v["named"] or v["byte_overlap"]
                                                       for v in rec["live_in"].values())
                                    else "NOT-FOUND-by-this-instrument")
            out[key] = rec
            print("%-34s neg=%-26s pos=%-28s orig_named=%d orig_byte=%d"
                  % (key, rec["negative_half"], rec["positive_half"], named, byteo))
    json.dump(out, open(os.path.join(HERE, "citation_repair_check2.json"), "w"),
              indent=1, sort_keys=True)
    import collections
    print()
    print(collections.Counter(v["negative_half"] for v in out.values()))
    print(collections.Counter(v["positive_half"] for v in out.values()))


if __name__ == "__main__":
    main()
