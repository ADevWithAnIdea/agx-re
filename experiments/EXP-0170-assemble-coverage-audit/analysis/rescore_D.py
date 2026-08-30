#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0170 Arm D, step 2 -- re-score EXP-0164's withheld fields under the
UNCHANGED EXP-0164 gate, changing only the two things AMENDMENT D.2/D.3 froze:

  D.2  never-dispatched placeholder records no longer contribute a signature
       (work/collect_raw_D.py -> work/raw_index_D.json.gz)
  D.3  runs the source experiment disowns are not eligible to score a field
       (analysis/run_eligibility.json)

cross_run(), stable_live() and classify() are IMPORTED from
EXP-0164/analysis/audit.py rather than copied, so MIN_COMMON=2,
MIN_AGREE_PCT=99.0 and MOVED_OVER_DISAGREE=2.0 are provably the audit's own
thresholds and cannot have been retuned here.

Three scorings are reported side by side:
  S1  the audit's own numbers, read from EXP-0164/analysis/audit.json
  S2  same run pair the audit chose, placeholders dropped   (isolates D.2)
  S3  placeholders dropped AND ineligible runs excluded     (D.2 + D.3) -- PRIMARY
  S3b sensitivity only: S3 with "PARTIAL BUT USED"/"retained ... are used"
      SCOPE.md runs re-admitted, since E1 is blunter than those files intend

READ-ONLY over everything outside this experiment.
Usage: python3 analysis/rescore_D.py
"""
import collections, gzip, importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
A64 = os.path.join(EXPDIR, "EXP-0164-inert-audit", "analysis")
W64 = os.path.join(EXPDIR, "EXP-0164-inert-audit", "work")

_spec = importlib.util.spec_from_file_location("audit64", os.path.join(A64, "audit.py"))
AUD = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(AUD)          # main() is __main__-guarded; only defs run

assert (AUD.MIN_COMMON, AUD.MIN_AGREE_PCT, AUD.MOVED_OVER_DISAGREE) == (2, 99.0, 2.0), \
    "EXP-0164 thresholds moved; Arm D's 'unchanged gate' claim would be false"

WITHHOLD_FILES = ["withhold_inert_single.json", "withhold_unstable.json",
                  "withhold_unverifiable.json"]

# S3b only: runs whose own marker file says they ARE used (see run_eligibility.py
# E2_CONFLICT).  Never used for the primary S3 verdict.
S3B_READMIT = {("EXP-0144-m4-emit-pack", "m4_20260828_run05"),
               ("EXP-0144-m4-emit-pack", "m4_20260828_rv01__cvt_f2h_dst")}


def gather(key, evidence, index, resolve, pseudo, ineligible, extra_ok=frozenset()):
    """EXP-0164 audit.gather(), with the D.3 eligibility filter replacing the
    PARTIAL.md-only filter.  Everything else is line-for-line the same."""
    per_exp = {}
    for eid in evidence:
        d = resolve(eid)
        if not d or key not in index.get(d, {}):
            continue
        ex = {}
        for arm, runs in index[d][key].items():
            gruns = {r: e for r, e in runs.items()
                     if (d, r) not in ineligible or (d, r) in extra_ok}
            fb = False
            if not gruns:
                gruns, fb = dict(runs), True
            cr = AUD.cross_run(gruns)
            ex[arm] = {
                "runs": {r: {k: e[k] for k in ("n_values", "moved", "n_cases", "n_contam",
                                               "n_placeholder", "n_within_run_unstable",
                                               "attribution", "labels") if k in e}
                         for r, e in sorted(gruns.items())},
                "n_gated_runs": len(gruns),
                "gating_fallback": fb,
                "cross_run": cr,
                "stable_live": AUD.stable_live(cr),
                "moved_total": sum(e["moved"] for e in gruns.values()),
                "n_values_max": max((e["n_values"] for e in gruns.values()), default=0),
                "attribution": sorted({a for e in gruns.values() for a in e["attribution"]}),
            }
        per_exp[eid] = ex
    return per_exp


def bucket_of(per_exp):
    return AUD.classify(per_exp)[0]


def best_cross(per_exp):
    """The arm whose cross_run drives the verdict: prefer a stable_live one, else
    the one with the most common values."""
    best = None
    for eid, ex in per_exp.items():
        for arm, v in ex.items():
            cr = v["cross_run"]
            if not cr:
                continue
            score = (1 if v["stable_live"] else 0, cr["common"])
            if best is None or score > best[0]:
                best = (score, eid, arm, cr, v)
    return best


def main():
    val = json.load(open(os.path.join(W64, "validation.snapshot.json")))
    idxD = json.load(gzip.open(os.path.join(EXP, "work", "raw_index_D.json.gz"), "rt"))
    indexD, pseudoD = idxD["index"], idxD["pseudo"]
    elig = json.load(open(os.path.join(HERE, "run_eligibility.json")))["runs"]
    ineligible = {tuple(k.split("/", 1)) for k, v in elig.items() if not v["eligible"]}

    audit64 = json.load(open(os.path.join(A64, "audit.json")))["fields"]
    resolve = AUD.resolver()

    withheld = {}
    for f in WITHHOLD_FILES:
        for k, v in json.load(open(os.path.join(A64, f))).items():
            if k != "_meta":
                withheld[k] = f.replace("withhold_", "").replace(".json", "").upper()

    # current db spans, so the output can carry start/width merge_verdicts checks
    dbnow = json.load(open(os.path.join(EXP, "work", "db.snapshot.json")))
    spans_now = {(i["mnemonic"], f["name"]): (f["start"], f["width"])
                 for i in dbnow["instructions"] for f in i.get("fields", [])}
    db64 = json.load(open(os.path.join(W64, "db.snapshot.json")))
    spans_64 = {(i["mnemonic"], f["name"]): (f["start"], f["width"])
                for i in db64["instructions"] for f in i.get("fields", [])}

    rows, verdicts = {}, collections.Counter()
    for key, orig_bucket in sorted(withheld.items()):
        mn, fn = key.split(".", 1)
        a64 = audit64.get(key) or {}
        ev = a64.get("evidence") or []

        peS2 = gather(key, ev, indexD, resolve, pseudoD, ineligible=frozenset())
        peS3 = gather(key, ev, indexD, resolve, pseudoD, ineligible=ineligible)
        peS3b = gather(key, ev, indexD, resolve, pseudoD, ineligible=ineligible,
                       extra_ok=S3B_READMIT)
        bS2, bS3, bS3b = bucket_of(peS2), bucket_of(peS3), bucket_of(peS3b)

        # which runs each scoring used
        def used(pe):
            return sorted({"%s/%s" % (e, r) for e, ex in pe.items()
                           for v in ex.values() for r in v["runs"]})

        b64 = best_cross({e: {a: v for a, v in ex.items()}
                          for e, ex in (a64.get("per_experiment") or {}).items()})
        bx2, bx3 = best_cross(peS2), best_cross(peS3)

        if bS3 == "STABLE-LIVE":
            verdict = "WRONGLY-WITHDRAWN"
        elif bS3 == orig_bucket:
            verdict = "AGREES"
        elif not any(v["runs"] for ex in peS3.values() for v in ex.values()):
            verdict = "NO-ELIGIBLE-EVIDENCE"
        else:
            verdict = "STILL-WITHHELD-OTHER-REASON"
        verdicts[verdict] += 1

        ph = sum(r.get("n_placeholder", 0) for ex in peS2.values() for v in ex.values()
                 for r in v["runs"].values())
        rows[key] = {
            "mnemonic": mn, "field": fn,
            "start": spans_now.get((mn, fn), (None, None))[0],
            "width": spans_now.get((mn, fn), (None, None))[1],
            "span_moved_since_EXP-0164": spans_now.get((mn, fn)) != spans_64.get((mn, fn)),
            "span_in_EXP-0164_db": spans_64.get((mn, fn)),
            "label_when_withheld": a64.get("label"),
            "target": a64.get("target"), "evidence": ev,
            "audit_bucket": orig_bucket, "verdict": verdict,
            "S1_audit": {"bucket": a64.get("bucket"),
                         "runA": b64[3]["runA"] if b64 else None,
                         "runB": b64[3]["runB"] if b64 else None,
                         "agree_pct": b64[3]["agree_pct"] if b64 else None,
                         "common": b64[3]["common"] if b64 else None,
                         "movedA": b64[3]["movedA"] if b64 else None,
                         "movedB": b64[3]["movedB"] if b64 else None,
                         "moved_total": a64.get("moved_total"),
                         "raw_files": a64.get("raw_files") or []},
            "S2_placeholders_dropped": {"bucket": bS2,
                         "runA": bx2[3]["runA"] if bx2 else None,
                         "runB": bx2[3]["runB"] if bx2 else None,
                         "agree_pct": bx2[3]["agree_pct"] if bx2 else None,
                         "common": bx2[3]["common"] if bx2 else None,
                         "movedA": bx2[3]["movedA"] if bx2 else None,
                         "movedB": bx2[3]["movedB"] if bx2 else None,
                         "runs_used": used(peS2),
                         "placeholder_records_dropped": ph},
            "S3_primary": {"bucket": bS3,
                         "runA": bx3[3]["runA"] if bx3 else None,
                         "runB": bx3[3]["runB"] if bx3 else None,
                         "agree_pct": bx3[3]["agree_pct"] if bx3 else None,
                         "common": bx3[3]["common"] if bx3 else None,
                         "runs_used": used(peS3),
                         "runs_excluded_as_ineligible": sorted(
                             set(used(peS2)) - set(used(peS3)))},
            "S3b_sensitivity_scope_md_readmitted": {"bucket": bS3b,
                         "runs_used": used(peS3b)},
        }

    doc = {"_meta": {
             "generated_by": "EXP-0170/analysis/rescore_D.py",
             "mergeable": False,
             "NOT_a_merge_file": "deliberately NOT FIELD-SWEEP-PROTOCOL 5 schema; carries no "
                                 "top-level `label`, so work/merge_verdicts.py cannot consume it",
             "gate": {"MIN_COMMON": AUD.MIN_COMMON, "MIN_AGREE_PCT": AUD.MIN_AGREE_PCT,
                      "MOVED_OVER_DISAGREE": AUD.MOVED_OVER_DISAGREE,
                      "source": "imported verbatim from EXP-0164/analysis/audit.py"},
             "scorings": {"S1": "EXP-0164 audit.json as committed",
                          "S2": "audit's run pair, placeholders dropped (D.2)",
                          "S3": "PRIMARY: D.2 + D.3 eligibility",
                          "S3b": "sensitivity: S3 with self-declared-used SCOPE.md runs re-admitted"},
             "withheld_fields": len(rows)},
           "verdict_totals": dict(verdicts),
           "fields": rows}
    json.dump(doc, open(os.path.join(HERE, "rescore_D.json"), "w"), indent=1, sort_keys=True)

    print("withheld %d" % len(rows))
    for k, n in verdicts.most_common():
        print("  %-30s %d" % (k, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
