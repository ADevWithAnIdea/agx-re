#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0170 Arm B step 2 -- classify every currently-emitter-grade field in
validation.json as FULL-RANGE / UNDER-COVERED / UNKNOWN from the distinct-`bytes`
counters built by coverage_index.py, and emit analysis/coverage.json +
analysis/reclassify.json.

All thresholds are frozen in PRE_REGISTRATION.md 3 and are NOT recomputed here.

READ-ONLY except analysis/coverage.json, analysis/reclassify.json, analysis/summary.md.
Usage: python3 analysis/classify.py
"""
import collections, gzip, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
WORK = os.path.join(EXP, "work")

EMIT = {"hardware-run", "isolated-byte-diff"}
INFORMATIVE_MIN_VALUES = 4          # frozen
SEVERE, MODERATE = 0.50, 0.90       # frozen severity bands

# frozen claimed-range parsers (PRE_REGISTRATION 3, "Claim check")
RE_ALL_N = re.compile(r"all\s+(\d+)\s+values")
RE_DENSE = re.compile(r"\b0\s*\.\.\s*(\d+)\s+dense")
RE_LIST = re.compile(r"^\s*([0-9]+\s*(?:,\s*[0-9]+\s*)+)$")


def claimed_count(rng):
    if not isinstance(rng, str) or not rng.strip():
        return None, "unparseable"
    m = RE_ALL_N.search(rng)
    if m:
        return int(m.group(1)), "all-N-values"
    m = RE_DENSE.search(rng)
    if m:
        return int(m.group(1)) + 1, "0..N-dense"
    m = RE_LIST.match(rng)
    if m:
        return len([x for x in m.group(1).split(",") if x.strip()]), "comma-list"
    return None, "unparseable"


def ev_match(expdir, evid):
    return expdir == evid or expdir.startswith(evid + "-")


def main():
    idx = json.load(gzip.open(os.path.join(WORK, "coverage_index.json.gz"), "rt"))
    groups = idx["groups"]
    val = json.load(open(os.path.join(WORK, "validation.snapshot.json")))
    db = json.load(open(os.path.join(WORK, "db.snapshot.json")))
    static = json.load(open(os.path.join(HERE, "static_overlap.json")))
    st = {(r["mnemonic"], r["field"]): r for r in static["overlapping_fields"]}
    dbf = {i["mnemonic"]: [(f["name"], f["start"], f["width"]) for f in i.get("fields", [])]
           for i in db["instructions"]}

    # (mnemonic, field) -> list of cells
    cells = collections.defaultdict(list)
    for g in groups:
        mn = g["instr_db"]
        if not mn:
            continue
        for a in g["attributed"]:
            cells[(mn, a["field"])].append((g, a))

    records = []
    for mn, entry in sorted(val["instructions"].items()):
        for (fname, fstart, fwidth) in dbf.get(mn, []):
            lab = entry.get(fname)
            if not lab or lab.get("label") not in EMIT:
                continue
            evid = lab.get("evidence") or []
            cs = cells.get((mn, fname), [])

            def pick(scope_cited):
                out = []
                for g, a in cs:
                    if scope_cited and not any(ev_match(g["exp"], e) for e in evid):
                        continue
                    if not g["informative"] or g["degenerate_bytes_constant"]:
                        continue
                    out.append((g, a))
                return out

            cited = pick(True)
            anyscope = pick(False)

            def summarize(sel):
                if not sel:
                    return None
                Vmax = max(g["n_values"] for g, _ in sel)
                Bmax = max(g["n_bytes"] for g, _ in sel)
                spans = [a["n_span"] for _, a in sel if a["n_span"] is not None]
                uni = set()
                truncated = False
                for _, a in sel:
                    if a["n_span"] is None:
                        continue
                    if a["n_span"] > len(a["span_values"]):
                        truncated = True     # span_values capped at 300 by the indexer
                    uni |= set(a["span_values"])
                return {
                    "n_cells": len(sel),
                    "experiments": sorted({g["exp"] for g, _ in sel}),
                    "max_distinct_values_dispatched": Vmax,
                    "max_distinct_bytes_observed": Bmax,
                    "max_distinct_field_span_encodings": max(spans) if spans else None,
                    "union_field_span_encodings": (max(max(spans), len(uni)) if truncated
                                                   else (len(uni) if spans else None)),
                    "union_truncated": truncated,
                    "n_collapsed_cells": sum(1 for g, _ in sel if g["collapse"]),
                    "attribution": sorted({g["attribution"] for g, _ in sel}),
                }

            sc, sa = summarize(cited), summarize(anyscope)

            if sc is None:
                cls = "UNKNOWN"
                frac = None
                why = ("no informative raw sweep group with a `bytes` column is "
                       "attributable to this field from its cited evidence")
                if sa is not None:
                    why += "; but an uncited experiment does have one"
            else:
                V, B = sc["max_distinct_values_dispatched"], sc["max_distinct_bytes_observed"]
                frac = B / V
                if B >= V:
                    cls = "FULL-RANGE"
                    why = "some cited sweep delivered >= as many distinct encodings as values"
                else:
                    cls = "UNDER-COVERED"
                    why = ("no cited sweep delivered the %d distinct encodings its own "
                           "records dispatched; best was %d" % (V, B))

            sfield = st.get((mn, fname))
            claimed, howparsed = claimed_count(lab.get("range"))
            nspan = sc["union_field_span_encodings"] if sc else None
            if nspan is None:
                claim_check = "no-raw"
            elif claimed is None:
                claim_check = "unparseable"
            elif nspan >= claimed:
                claim_check = "met"
            else:
                claim_check = "short"

            # cause tag (frozen H5 rule)
            cause = None
            if cls == "UNDER-COVERED":
                if sfield:
                    pred = sfield["reachable_fraction_old"]
                    obs = frac
                    cause = ("assemble-match-overlap"
                             if abs(obs - pred) < 1e-9 else "match-overlap-but-ratio-differs")
                else:
                    cause = "not-assemble"

            sev = None
            if frac is not None and cls == "UNDER-COVERED":
                sev = "severe" if frac <= SEVERE else ("moderate" if frac <= MODERATE
                                                       else "marginal")

            files = sorted({f for g, _ in (cited or anyscope or []) for f in g["files"]})
            records.append({
                "mnemonic": mn, "field": fname, "start": fstart, "width": fwidth,
                "label": lab.get("label"), "target": lab.get("target"),
                "evidence": evid,
                "claimed_range": lab.get("range"),
                "claimed_count": claimed, "claimed_count_parse": howparsed,
                "classification": cls,
                "reachable_fraction": frac,
                "severity": sev,
                "cause": cause,
                "claim_check": claim_check,
                "match_overlap": bool(sfield),
                "reachable_old": sfield["reachable_old"] if sfield else (1 << fwidth),
                "reachable_fraction_old": sfield["reachable_fraction_old"] if sfield else 1.0,
                "range_string_exceeds_field_width": bool(
                    claimed is not None and claimed > (1 << fwidth)),
                "cited_scope": sc,
                "any_scope": sa,
                "rescued_by_uncited": bool(cls == "UNDER-COVERED" and sa and
                                           sa["max_distinct_bytes_observed"] >=
                                           sc["max_distinct_values_dispatched"]),
                "why": why,
                "raw_files": files[:40],
                "n_raw_files": len(files),
            })

    # ---- emittability impact ---------------------------------------------
    dw = {i["mnemonic"] for i in db["instructions"]
          if i.get("emitter_role") == "data-word"}
    withheld = {(r["mnemonic"], r["field"]) for r in records
                if r["classification"] == "UNDER-COVERED"}
    emit_now = set(val["coverage"]["emittable_mnemonics"])
    lost = sorted({m for m, f in withheld if m in emit_now})

    counts = collections.Counter(r["classification"] for r in records)
    doc = {
        "_meta": {
            "generated_by": "EXP-0170/analysis/classify.py",
            "thresholds": {"informative_min_distinct_values": INFORMATIVE_MIN_VALUES,
                           "severe<=": SEVERE, "moderate<=": MODERATE},
            "definition": {
                "UNDER-COVERED": "max distinct `bytes` over cited informative sweep groups "
                                 "< max distinct dispatched `value`s over the same groups",
                "FULL-RANGE": "some cited informative sweep group delivered >= as many "
                              "distinct byte strings as the most ambitious group dispatched values",
                "UNKNOWN": "no informative cited sweep group carries a usable `bytes` column",
            },
        },
        "totals": {
            "emitter_grade_fields": len(records),
            **{k: counts.get(k, 0) for k in ("FULL-RANGE", "UNDER-COVERED", "UNKNOWN")},
            "claim_check": dict(collections.Counter(r["claim_check"] for r in records)),
            "instructions_currently_emittable": len(emit_now),
            "instructions_that_would_lose_emittable_status": lost,
        },
        "fields": records,
    }
    json.dump(doc, open(os.path.join(HERE, "coverage.json"), "w"), indent=1)

    # ---- reclassify.json (FIELD-SWEEP-PROTOCOL 5 schema) ------------------
    rc = {}
    rc_all = {}
    for r in records:
        if r["classification"] != "UNDER-COVERED":
            continue
        sc = r["cited_scope"]
        row = {
            "label": "untested",
            "start": r["start"], "width": r["width"],
            "range": "",
            "target": r["target"],
            "evidence": ["EXP-0170"] + r["evidence"],
            "semantics": "",
            "note": ("EXP-0170 withheld (DEF-0166-1 coverage audit): the cited raw sweep "
                     "dispatched %d distinct values but only %d distinct `bytes` strings "
                     "ever reached the GPU (%.1f%% of the claimed range); the field's own "
                     "bit span took %s distinct encodings. db.json pins %d of this field's "
                     "%d encodings via its own `match`, so the old OR-only "
                     "isadb.assemble() could reach at most %d. Previous label %r with range "
                     "%r rests on values that were never spliced. Cause: %s. Cited "
                     "experiments: %s."
                     % (sc["max_distinct_values_dispatched"],
                        sc["max_distinct_bytes_observed"],
                        100.0 * r["reachable_fraction"],
                        sc["max_distinct_field_span_encodings"],
                        (1 << r["width"]) - r["reachable_old"],
                        1 << r["width"], r["reachable_old"],
                        r["label"], r["claimed_range"], r["cause"],
                        ", ".join(sc["experiments"]))),
        }
        key = "%s.%s" % (r["mnemonic"], r["field"])
        rc_all[key] = dict(row, severity=r["severity"],
                           recommend=("withhold" if r["severity"] != "marginal"
                                      else "review-only"))
        if r["severity"] != "marginal":
            rc[key] = row
    json.dump(rc, open(os.path.join(HERE, "reclassify.json"), "w"), indent=1, sort_keys=True)
    json.dump(rc_all, open(os.path.join(HERE, "reclassify_frozen_rule.json"), "w"),
              indent=1, sort_keys=True)

    # ---- Arm A x Arm B: did the 53 overlapping fields ever exceed 2^(w-p)? ----
    ov = []
    for r in static["overlapping_fields"]:
        mn, fn = r["mnemonic"], r["field"]
        sel = [(g, a) for g, a in cells.get((mn, fn), [])
               if g["informative"] and not g["degenerate_bytes_constant"]
               and a["n_span"] is not None]
        uni = set()
        trunc = False
        for g, a in sel:
            if a["n_span"] > len(a["span_values"]):
                trunc = True
            uni |= set(a["span_values"])
        obs = (max(max(a["n_span"] for _, a in sel), len(uni)) if (sel and trunc)
               else (len(uni) if sel else None))
        lab = (val["instructions"].get(mn) or {}).get(fn) or {}
        ov.append({
            "mnemonic": mn, "field": fn, "start": r["start"], "width": r["width"],
            "label": lab.get("label", "(absent)"), "range": lab.get("range"),
            "evidence": lab.get("evidence"),
            "encodable": r["encodable"], "reachable_old": r["reachable_old"],
            "observed_union_span_encodings": obs,
            "experiments_with_raw": sorted({g["exp"] for g, _ in sel}),
            "verdict": ("no-raw" if obs is None else
                        ("EXCEEDS-old-limit (harness bypassed assemble())"
                         if obs > r["reachable_old"] else
                         ("AT-old-limit (consistent with the OR-only defect)"
                          if obs == r["reachable_old"] else
                          "below-old-limit (sparse sweep; defect not separable)"))),
        })
    doc["overlapping_field_audit"] = ov
    doc["totals"]["overlapping_fields"] = len(ov)
    doc["totals"]["overlapping_fields_verdict"] = dict(collections.Counter(
        o["verdict"] for o in ov))
    doc["totals"]["overlapping_fields_emitter_grade"] = len(
        [o for o in ov if o["label"] in EMIT])
    doc["totals"]["range_strings_exceeding_field_width"] = len(
        [r for r in records if r["range_string_exceeds_field_width"]])
    json.dump(doc, open(os.path.join(HERE, "coverage.json"), "w"), indent=1)

    print("emitter-grade fields audited: %d" % len(records))
    for k in ("FULL-RANGE", "UNDER-COVERED", "UNKNOWN"):
        print("  %-14s %4d" % (k, counts.get(k, 0)))
    print("claim check:", doc["totals"]["claim_check"])
    print("instructions that would lose emittable status:", lost or "(none)")
    print("wrote analysis/coverage.json and analysis/reclassify.json (%d rows)" % len(rc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
