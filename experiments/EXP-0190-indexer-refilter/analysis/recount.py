#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0190 step 5 (verbatim from EXP-0189 apart from the two input paths) -- recount emittability under the CURRENT validate_labels.py rule.

audit.py (inherited verbatim from EXP-0164) implements the OLD emittable rule, which
ignored `_instruction` for descriptors that have fields.  `tools/agx-isa/validate_labels.py`
gained the `_instruction` gate on 2026-08-30 (DEF-0173-1), which is why audit.py
recomputes 61 where validation.json publishes 55.  This script reimplements the rule as
it now stands, so every scenario is measured against the published 55.

It also:
  * audits the 172 `_instruction` pseudo-entries, which the field audit excludes by
    construction but which the new gate makes load-bearing;
  * splits the emitter-grade universe into the post-459bb8bd cohort and the rest;
  * emits reclassify.json WITH start/width (the merger refuses a row whose bits moved);
  * runs the text-vs-evidence contradiction sweep (PRE_REGISTRATION section 7.4).

Reads only work/ snapshots + analysis/audit.json.  Writes only into analysis/.
Usage: python3 analysis/recount.py
"""
import argparse, collections, gzip, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
WORK = os.path.join(EXP, "work")

EMIT_OK = ("hardware-run", "isolated-byte-diff")
DATA_WORD_ROLE = "data-word"
WITHHOLD = ("INERT-SINGLE", "UNSTABLE", "UNVERIFIABLE")
NONGATED = re.compile(r"(prefreeze|smoke|pilot|quarantine|burned)", re.I)

# post-459bb8bd cohort: experiment directories touched after the 41/166 withdrawal.
POST = set("""EXP-0157 EXP-0163 EXP-0165 EXP-0166 EXP-0167 EXP-0168 EXP-0169 EXP-0170
EXP-0171 EXP-0172 EXP-0173 EXP-0174 EXP-0175 EXP-0176 EXP-0177 EXP-0178 EXP-0179
EXP-0180 EXP-0181 EXP-0182 EXP-0183 EXP-0184 EXP-0185 EXP-0186 EXP-0187
EXP-0188""".split())

# section 7.4: assertions of inertness / absence / non-observability in row prose.
INERT_CLAIM = re.compile(
    r"\b(fully inert|inert\b|no effect|no observable|never moved|no movement|"
    r"framing only|framing-only|not a field|no semantic|purely structural|"
    r"structural only|does not affect|has no effect|ignored by (the )?hardware|"
    r"don'?t care|dont care)", re.I)


def load(auditname="audit.json", indexname="raw_index.json.gz"):
    """EXP-0190: the two input paths are arguments so the same code runs against the
    legacy and the refiltered index.  Nothing else in this file changed; the rule
    functions are asserted byte-identical by analysis/verify_inheritance.py."""
    val = json.load(open(os.path.join(WORK, "validation.snapshot.json")))
    db = json.load(open(os.path.join(WORK, "db.snapshot.json")))
    audit = json.load(open(os.path.join(HERE, auditname)))["fields"]
    idx = json.load(gzip.open(os.path.join(WORK, indexname), "rt"))
    return val, db, audit, idx


def resolver():
    dirs = sorted(d for d in os.listdir(EXPDIR) if os.path.isdir(os.path.join(EXPDIR, d)))
    cache = {}

    def resolve(eid):
        if eid in cache:
            return cache[eid]
        r = eid if eid in dirs else None
        if r is None:
            c = [d for d in dirs if d.startswith(eid + "-")]
            r = c[0] if len(c) == 1 else None
        cache[eid] = r
        return r
    return resolve


def emittable_current(val, db, withheld_fields, withheld_instr):
    """Exact reimplementation of tools/agx-isa/validate_labels.py's rule as of
    repo revision 0de24f4f (DEF-0173-1 `_instruction` gate included)."""
    wf, wi = set(withheld_fields), set(withheld_instr)
    emit, rel, why = [], [], {}
    for ins in db["instructions"]:
        m = ins["mnemonic"]
        entry = val["instructions"].get(m, {})
        fields = ins.get("fields", [])
        all_emit, reasons = True, []
        for f in fields:
            e = entry.get(f["name"])
            if e is None or e.get("label") not in EMIT_OK:
                all_emit = False
            elif "%s.%s" % (m, f["name"]) in wf:
                all_emit = False
                reasons.append("field:%s" % f["name"])
        if not fields:
            if entry.get("_instruction", {}).get("label") not in EMIT_OK:
                all_emit = False
        if "EMITTABLE VETO" in (entry.get("_instruction") or {}).get("note", ""):
            all_emit = False
        il = (entry.get("_instruction") or {}).get("label")
        if il not in EMIT_OK:
            all_emit = False
        elif m in wi:
            all_emit = False
            reasons.append("_instruction")
        if ins.get("emitter_role") != DATA_WORD_ROLE:
            rel.append(m)
            if all_emit:
                emit.append(m)
            elif reasons:
                why[m] = reasons
    return sorted(emit), sorted(rel), why


def instr_dispatch_audit(val, db, idx, resolve):
    """Was each emitter-grade `_instruction` really DISPATCHED on hardware?

    Mechanical test, deliberately generous: the mnemonic must appear in the raw index
    (per-value records bit-attributed to a field OF THAT MNEMONIC) in at least one
    GATED run of at least one experiment.  We do NOT require the citing experiment to
    be the one that dispatched it -- the question is whether ANY committed raw shows
    the instruction executing.  A mnemonic that fails this test has no per-value
    hardware record anywhere in the repository."""
    partial = set(idx["_meta"]["partial_runs"])
    index = idx["index"]
    seen = idx["_meta"].get("mnemonics_seen_per_exp", {})
    out = {}
    for ins in db["instructions"]:
        m = ins["mnemonic"]
        e = (val["instructions"].get(m) or {}).get("_instruction") or {}
        dispatch = {}
        for d, keys in index.items():
            runs = set()
            for k, arms in keys.items():
                if k.split(".", 1)[0] != m:
                    continue
                for arm, rs in arms.items():
                    for r, v in rs.items():
                        if NONGATED.search(r) or (d + "/" + r) in partial:
                            continue
                        if v["n_values"] >= 1:
                            runs.add(r)
            if runs:
                dispatch[d] = sorted(runs)
        matched = sorted(d for d, ms in seen.items() if m in ms)
        cited = [resolve(x) for x in (e.get("evidence") or [])]
        out[m] = {
            "label": e.get("label"), "evidence": e.get("evidence") or [],
            "n_dirs_with_per_value_records": len(dispatch),
            "dirs_with_per_value_records": dispatch,
            "dirs_where_bytes_match_this_descriptor": matched,
            "cited_dirs": [c for c in cited if c],
            "cited_dir_has_records": sorted(set(dispatch) & {c for c in cited if c}),
            "verdict": ("dispatched" if dispatch else
                        "bytes-seen-only" if matched else "no-per-value-record"),
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", default="audit.json")
    ap.add_argument("--index", default="raw_index.json.gz")
    ap.add_argument("--suffix", default="")
    args = ap.parse_args()
    val, db, audit, idx = load(args.audit, args.index)
    resolve = resolver()
    DBF = {i["mnemonic"]: {f["name"]: (f["start"], f["width"]) for f in i.get("fields", [])}
           for i in db["instructions"]}

    strict = sorted(k for k, r in audit.items() if r["bucket"] in WITHHOLD)
    lenient = sorted(k for k in strict
                     if not (audit[k]["bucket"] == "UNVERIFIABLE" and
                             audit[k]["unverifiable_reason"] == "field-named-but-unstructured"))

    ia = instr_dispatch_audit(val, db, idx, resolve)
    instr_withheld = sorted(m for m, v in ia.items()
                            if v["label"] in EMIT_OK and v["verdict"] != "dispatched")

    base, rel, _ = emittable_current(val, db, [], [])
    scen = {}
    for name, wf, wi in (
            ("published_rule_no_withholding", [], []),
            ("strict_fields_only", strict, []),
            ("lenient_fields_only", lenient, []),
            ("strict_fields_plus_instruction_gate", strict, instr_withheld),
            ("instruction_gate_only", [], instr_withheld)):
        e, _r, why = emittable_current(val, db, wf, wi)
        scen[name] = {"n_fields_withheld": len(wf), "n_instr_withheld": len(wi),
                      "emittable": len(e), "mnemonics": e,
                      "lost_vs_published": sorted(set(base) - set(e)),
                      "why_lost": {m: why[m] for m in sorted(set(base) - set(e)) if m in why}}

    # ---- ranked blame -----------------------------------------------------
    lost = scen["strict_fields_plus_instruction_gate"]["lost_vs_published"]
    ranked = []
    for m in lost:
        bad = []
        for f in DBF.get(m, {}):
            k = "%s.%s" % (m, f)
            if k in set(strict):
                bad.append({"field": f, "start": DBF[m][f][0], "width": DBF[m][f][1],
                            "bucket": audit[k]["bucket"],
                            "reason": audit[k]["unverifiable_reason"],
                            "evidence": audit[k]["evidence"],
                            "max_values_dispatched": audit[k]["max_values_dispatched"],
                            "n_arms_tested": audit[k]["n_arms_that_tested_the_field"],
                            "moved_total": audit[k]["moved_total"]})
        ranked.append({"mnemonic": m, "n_blocking_fields": len(bad),
                       "instruction_gate_blocks": m in set(instr_withheld),
                       "blocking_fields": sorted(bad, key=lambda x: x["field"])})
    ranked.sort(key=lambda x: (x["n_blocking_fields"], x["mnemonic"]))

    # ---- cohort split -----------------------------------------------------
    cohort = {"post": collections.Counter(), "pre": collections.Counter()}
    cohort_keys = {"post": [], "pre": []}
    for k, r in audit.items():
        ev = {e.split("-")[0] + "-" + e.split("-")[1] if e.count("-") >= 1 else e
              for e in r["evidence"]}
        grp = "post" if (set(r["evidence"]) & POST) else "pre"
        cohort[grp][r["bucket"]] += 1
        cohort_keys[grp].append(k)
    cohort_out = {}
    for g in ("post", "pre"):
        n = sum(cohort[g].values())
        w = sum(v for b, v in cohort[g].items() if b in WITHHOLD)
        cohort_out[g] = {"n_fields": n, "buckets": dict(cohort[g]),
                         "n_withheld_strict": w,
                         "withheld_pct": round(100.0 * w / n, 2) if n else None}

    # ---- section 7.4: text asserts inert, raw says otherwise --------------
    contradictions = []
    for k, r in sorted(audit.items()):
        row = val["instructions"][r["mnemonic"]][r["field"]]
        txt = " ".join(str(row.get(x) or "") for x in ("range", "note", "semantics"))
        mt = INERT_CLAIM.search(txt)
        if not mt:
            continue
        hard = collections.Counter()
        for ex in r["per_experiment"].values():
            for arm in ex.values():
                for run in arm["runs"]:
                    pass
        if r["moved_total"] > 0 or r["bucket"] == "STABLE-LIVE":
            contradictions.append({
                "field": k, "start": DBF.get(r["mnemonic"], {}).get(r["field"], (None, None))[0],
                "width": DBF.get(r["mnemonic"], {}).get(r["field"], (None, None))[1],
                "claim_matched": mt.group(0), "bucket": r["bucket"],
                "moved_total": r["moved_total"],
                "max_values_dispatched": r["max_values_dispatched"],
                "label": r["label"], "evidence": r["evidence"],
                "range": row.get("range", ""), "note": (row.get("note") or "")[:400]})
    contradictions.sort(key=lambda x: -x["moved_total"])

    # ---- reclassify.json (flat, WITH start/width) -------------------------
    def rec(k):
        r = audit[k]
        st, wd = DBF.get(r["mnemonic"], {}).get(r["field"], (None, None))
        return {"start": st, "width": wd, "label_now": r["label"],
                "recommend_label": "untested", "bucket": r["bucket"],
                "reason": r["unverifiable_reason"], "target": r["target"],
                "evidence": r["evidence"],
                "n_arms_that_tested_the_field": r["n_arms_that_tested_the_field"],
                "max_values_dispatched": r["max_values_dispatched"],
                "moved_total": r["moved_total"],
                "arms_tested": r["arms_tested"], "raw_files": r["raw_files"],
                "range": val["instructions"][r["mnemonic"]][r["field"]].get("range", ""),
                "note": ("EXP-0189 withheld (%s): %d values dispatched over %d arm(s), "
                         "%d observations moved.%s" %
                         (r["bucket"], r["max_values_dispatched"],
                          r["n_arms_that_tested_the_field"], r["moved_total"],
                          (" Reason: %s." % r["unverifiable_reason"])
                          if r["unverifiable_reason"] else ""))}
    reclass = {
        "_meta": {"experiment": "EXP-0189-closing-audit",
                  "schema": "FIELD-SWEEP-PROTOCOL.md section 5, flat <mnemonic>.<field>, "
                            "start/width carried from work/db.snapshot.json",
                  "db_sha256": val["db_sha256"],
                  "policy": "withhold INERT-SINGLE, UNSTABLE, UNVERIFIABLE (EXP-0164 frozen rule)",
                  "counts": {"strict": len(strict), "lenient": len(lenient),
                             "instruction_entries_withheld": len(instr_withheld)}},
        "strict": {k: rec(k) for k in strict},
        "lenient_subset": lenient,
        "instruction_entries_without_dispatch_record": {
            m: ia[m] for m in instr_withheld},
        "instructions_that_lose_emittable_status": lost,
        "ranked_losses": ranked,
        "text_contradicts_evidence": contradictions,
    }
    json.dump(reclass, open(os.path.join(HERE, "reclassify%s.json" % args.suffix), "w"),
              indent=1, sort_keys=True)
    json.dump({"_meta": {"experiment": "EXP-0189-closing-audit",
                         "rule": "tools/agx-isa/validate_labels.py as of 0de24f4f, "
                                 "including the DEF-0173-1 `_instruction` gate",
                         "denominator_emitter_relevant": len(rel),
                         "published_in_validation_json":
                             val["coverage"]["emittable_of_emitter_relevant"]},
               "scenarios": scen,
               "cohort_split_post_459bb8bd": cohort_out,
               "instruction_entry_audit_summary": collections.Counter(
                   v["verdict"] for v in ia.values() if v["label"] in EMIT_OK),
               "instruction_entry_audit": ia},
              open(os.path.join(HERE, "emittability%s.json" % args.suffix), "w"), indent=1, sort_keys=True)

    print("denominator (emitter-relevant): %d   published: %d" %
          (len(rel), val["coverage"]["emittable_of_emitter_relevant"]))
    for n, v in scen.items():
        print("  %-38s emittable %3d  (fields withheld %d, _instruction withheld %d)"
              % (n, v["emittable"], v["n_fields_withheld"], v["n_instr_withheld"]))
    print("cohort:", json.dumps(cohort_out, sort_keys=True))
    print("_instruction verdicts (emitter-grade only):",
          dict(collections.Counter(v["verdict"] for v in ia.values() if v["label"] in EMIT_OK)))
    print("text-contradicts-evidence rows:", len(contradictions))
    return 0


if __name__ == "__main__":
    sys.exit(main())
