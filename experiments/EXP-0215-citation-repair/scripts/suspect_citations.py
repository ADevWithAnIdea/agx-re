#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""suspect_citations.py -- existing citations that look wrong. NONE IS REMOVED.

Section 9: "A broken citation or missing raw artifact downgrades auditability; it
does not by itself prove the hardware fact false." EXP-0189 removed nothing either
and still did the damage, in prose. So this program writes a list and nothing else:
no removal, no note, no label.

Four independent complaints, reported separately so a "no" from one is never read
as a "no" overall:

  A  the citation resolves to no directory at all
  B  the cited experiment is quarantined, or has no raw/, or commits no authored
     probe -- promotion_check rule_R1's own three tests
  C  the cited experiment yields ZERO records for this row under every keying the
     modern indexer AND the legacy parsers have, while its raw is machine-readable
     (i.e. it is not the format-unreadable case)
  D  the cited experiment's records for this row declare a DIFFERENT bit span, or
     commit bytes that fail the descriptor's own match: same NAME, other bits.
"""
import collections, glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(EXP, "..", ".."))
EXPS = os.path.join(ROOT, "experiments")
W = os.path.join(EXP, "work")
sys.path.insert(0, os.path.join(ROOT, "tools", "agx-isa"))
import evidence_index as EI

SPEC = EI.load_db(os.path.join(W, "db_frozen.json"))
VAL = json.load(open(os.path.join(W, "validation_frozen.json")))
LOC = json.load(open(os.path.join(W, "locators.json")))

LEGKEYS = collections.defaultdict(set)
for line in open(os.path.join(W, "legacy_index", "legacy_records.jsonl")):
    line = line.strip()
    if not line:
        continue
    r = json.loads(line)
    if isinstance(r.get("instr"), str) and isinstance(r.get("field"), str):
        LEGKEYS[r["_exp"]].add("%s.%s" % (r["instr"], r["field"]))

_res = {}
def resolve(slug):
    if slug not in _res:
        _res[slug] = sorted(os.path.basename(d) for d in
                            glob.glob(os.path.join(EXPS, slug.split("/")[0] + "*"))
                            if os.path.isdir(d))
    return _res[slug]

_meta = {}
def meta(exp):
    if exp not in _meta:
        p = os.path.join(W, "index", exp + ".json")
        try:
            _meta[exp] = json.load(open(p))["_meta"]
        except Exception:
            _meta[exp] = None
    return _meta[exp]

def authored(exp):
    d = os.path.join(EXPS, exp)
    return any(os.path.isdir(os.path.join(d, s)) and os.listdir(os.path.join(d, s))
               for s in ("kernels", "harness", "probe", "probes", "src", "shaders",
                         "analysis")) or bool(glob.glob(os.path.join(d, "*.metal")) or
                                              glob.glob(os.path.join(d, "*.py")))

out = {"A_unresolvable": [], "B_no_raw_probe_or_quarantined": [],
       "C_zero_records_though_machine_readable": [], "D_different_bits_same_name": []}
for m, fs in VAL["instructions"].items():
    for f, row in fs.items():
        if f == "_instruction" or not isinstance(row, dict):
            continue
        if m not in SPEC or f not in SPEC[m]["fields"]:
            continue
        key, st_w = "%s.%s" % (m, f), SPEC[m]["fields"][f]
        for slug in (row.get("evidence") or []):
            if not isinstance(slug, str):
                continue
            dirs = resolve(slug)
            if not dirs:
                out["A_unresolvable"].append({"row": key, "citation": slug,
                                              "label": row.get("label")})
                continue
            for d in dirs:
                mm = meta(d)
                bad = []
                if mm is None or not mm.get("has_raw"):
                    bad.append("no raw/")
                if mm and mm.get("quarantined"):
                    bad.append("QUARANTINED")
                if not authored(d):
                    bad.append("no authored probe")
                if bad:
                    out["B_no_raw_probe_or_quarantined"].append(
                        {"row": key, "citation": slug, "dir": d,
                         "label": row.get("label"), "why": ", ".join(bad)})
                    continue
                cell = (LOC.get(d) or {}).get(key)
                if cell is None:
                    if key in LEGKEYS.get(d, ()):
                        continue                      # legacy parsers do reach it
                    if mm.get("record_files", 0) and not mm.get("nonrecord_files", 0):
                        out["C_zero_records_though_machine_readable"].append(
                            {"row": key, "citation": slug, "dir": d,
                             "label": row.get("label"),
                             "record_files": mm.get("record_files"),
                             "instr_records_for_mnemonic":
                                 (mm.get("instr_records") or {}).get(m, 0)})
                    continue
                why = []
                if cell["span_mismatch"] and cell["span_match"] == 0:
                    why.append("records declare span(s) %s, current is %s"
                               % (",".join(sorted(cell["declared_spans"])), list(st_w)))
                bidx = {int(k) for k in (cell.get("byte_indices") or {})}
                span_bytes = set(range(st_w[0] // 8, (st_w[0] + st_w[1] - 1) // 8 + 1))
                if bidx and not (bidx & span_bytes):
                    why.append("every record declares byte %s; the span covers byte %s"
                               % (sorted(bidx), sorted(span_bytes)))
                if cell["n_actual_field_values"] >= 2 and \
                        cell.get("n_actual_field_values_matching", 0) < 2:
                    why.append("%d of %d committed encodings fail the descriptor's own "
                               "match bits" % (cell.get("nonmatch_bytes", 0),
                                               cell.get("match_bytes", 0) +
                                               cell.get("nonmatch_bytes", 0)))
                if why:
                    out["D_different_bits_same_name"].append(
                        {"row": key, "citation": slug, "dir": d,
                         "label": row.get("label"), "target": row.get("target"),
                         "locator": "%s:%s" % (cell.get("obs_file") or cell["first_file"],
                                               cell.get("obs_line") or cell["first_line"]),
                         "records": cell["records"], "why": "; ".join(why)})
json.dump(out, open(os.path.join(EXP, "analysis", "suspect_citations.json"), "w"),
          indent=1, sort_keys=True)
for k, v in out.items():
    print("%-42s %d" % (k, len(v)))
    for x in v[:6]:
        print("    ", json.dumps(x)[:190])
