#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0164 step 2 -- bucket every emitter-grade field of the pinned
validation.json snapshot against the raw index built by collect_raw.py.

Thresholds are frozen in ../PRE_REGISTRATION.md section 5 and are deliberately NOT
command-line tunable.

Outputs (analysis/):
  audit.json, reclassify.json, experiment_coverage.json, emittability.json,
  controls.json, mixed_arm_liveness.json
"""
import collections, gzip, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
WORK = os.path.join(EXP, "work")

EMIT_OK = ("hardware-run", "isolated-byte-diff")
DATA_WORD_ROLE = "data-word"
NONGATED = re.compile(r"(prefreeze|smoke|pilot|quarantine|burned)", re.I)

# --- frozen thresholds (PRE_REGISTRATION section 5) -------------------------
MIN_COMMON = 2
MIN_AGREE_PCT = 99.0
MOVED_OVER_DISAGREE = 2.0
THIN_COMMON = 8
WITHHOLD = ("INERT-SINGLE", "UNSTABLE", "UNVERIFIABLE")

# Recommended `note` text for a withheld field. validate_labels.py requires an
# `untested` entry that still carries evidence to explain itself in `note`.
NOTES = {
    "INERT-SINGLE": ("EXP-0164 withheld: %d values dispatched, %d carrier(s) tested, "
                     "%d observations moved. Never moved anything on the ONE carrier "
                     "tried, so the probe could not have shown liveness either way "
                     "(the EXP-0155 samp_extra failure mode). Needs a second, "
                     "structurally different carrier."),
    "UNSTABLE": ("EXP-0164 withheld: %d values dispatched, %d carrier(s) tested, "
                 "%d observations moved, but the movement does not reproduce across "
                 "the two gated runs at >=99%% per-value agreement with movement "
                 ">= 2x the disagreement count. Needs a third gated run."),
    "UNVERIFIABLE": ("EXP-0164 withheld: %d values dispatched, %d carrier(s) tested, "
                     "%d observations moved -- no per-value record under raw/ can be "
                     "attributed to this field, so the promotion cannot be reproduced "
                     "from committed evidence. This is an auditability gap, not a "
                     "refutation; re-record in the EXP-0138+ sweep.jsonl schema."),
}


def load():
    val = json.load(open(os.path.join(WORK, "validation.snapshot.json")))
    db = json.load(open(os.path.join(WORK, "db.snapshot.json")))
    idx = json.load(gzip.open(os.path.join(WORK, "raw_index.json.gz"), "rt"))
    return val, db, idx


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


def moved_of(entry):
    return entry["moved"]


def cross_run(runs):
    """The two gated runs with the most distinct attributed values."""
    order = sorted(runs.items(), key=lambda kv: (-kv[1]["n_values"], kv[0]))
    if len(order) < 2:
        return None
    (ra, ea), (rb, eb) = order[0], order[1]
    ka, kb = ea["keys"], eb["keys"]
    common = set(ka) & set(kb)
    agree = sum(1 for k in common if ka[k] == kb[k])
    n = len(common)
    return {"runA": ra, "runB": rb,
            "n_valuesA": ea["n_values"], "n_valuesB": eb["n_values"],
            "movedA": ea["moved"], "movedB": eb["moved"],
            "common": n, "agree": agree, "disagreements": n - agree,
            "agree_pct": round(100.0 * agree / n, 2) if n else None}


def stable_live(c):
    if c is None or c["common"] < MIN_COMMON:
        return False
    if c["movedA"] < 1 or c["movedB"] < 1:
        return False
    if c["agree_pct"] is None or c["agree_pct"] < MIN_AGREE_PCT:
        return False
    return min(c["movedA"], c["movedB"]) >= MOVED_OVER_DISAGREE * c["disagreements"]


def gather(key, evidence, index, partial, resolve, pseudo):
    """Collect every gated observation of `key` across its citing experiments."""
    per_exp = {}
    for eid in evidence:
        d = resolve(eid)
        if not d or key not in index.get(d, {}):
            continue
        ex = {}
        for arm, runs in index[d][key].items():
            gruns = {r: e for r, e in runs.items()
                     if not NONGATED.search(r) and (d + "/" + r) not in partial}
            fb = False
            if not gruns:
                gruns, fb = dict(runs), True
            cr = cross_run(gruns)
            ex[arm] = {
                "runs": {r: {k: e[k] for k in ("n_values", "moved", "n_cases",
                                               "n_contam", "n_within_run_unstable",
                                               "attribution", "labels")}
                         for r, e in sorted(gruns.items())},
                "n_gated_runs": len(gruns),
                "gating_fallback": fb,
                "cross_run": cr,
                "stable_live": stable_live(cr),
                "moved_total": sum(e["moved"] for e in gruns.values()),
                "n_values_max": max((e["n_values"] for e in gruns.values()), default=0),
                "attribution": sorted({a for e in gruns.values() for a in e["attribution"]}),
                "n_baseline_signatures": len({s for r in gruns
                                              for s in pseudo.get(d, {}).get(arm, {}).get(r, [])}),
            }
        per_exp[eid] = ex
    return per_exp


def classify(per_exp):
    arms = {(e, a) for e, ex in per_exp.items() for a in ex}
    tested = {(e, a) for e, ex in per_exp.items() for a, v in ex.items() if v["n_values_max"] >= 2}
    moved = sum(v["moved_total"] for ex in per_exp.values() for v in ex.values())
    any_stable = any(v["stable_live"] for ex in per_exp.values() for v in ex.values())
    any_2run = any(v["n_gated_runs"] >= 2 for ex in per_exp.values() for v in ex.values())
    if not tested:
        return "UNVERIFIABLE", arms, tested, moved
    if any_stable:
        return "STABLE-LIVE", arms, tested, moved
    if moved == 0:
        return ("INERT-MULTI" if len(tested) >= 2 else "INERT-SINGLE"), arms, tested, moved
    if not any_2run:
        return "SINGLE-RUN", arms, tested, moved
    return "UNSTABLE", arms, tested, moved


def build_record(mn, fn, rec, per_exp):
    bucket, arms, tested, moved = classify(per_exp)
    mixed = []
    for eid, ex in per_exp.items():
        inert = sorted(a for a, v in ex.items() if v["moved_total"] == 0 and v["n_values_max"] >= 2)
        live = sorted(a for a, v in ex.items() if v["stable_live"])
        if inert and live:
            mixed.append({"experiment": eid, "inert_arms": inert, "stable_live_arms": live,
                          "live_moved": {a: ex[a]["cross_run"]["movedA"] for a in live},
                          "inert_values_swept": {a: ex[a]["n_values_max"] for a in inert}})
    attribution = sorted({a for ex in per_exp.values() for v in ex.values()
                          for a in v["attribution"]})
    return {
        "mnemonic": mn, "field": fn, "label": rec.get("label"), "target": rec.get("target"),
        "evidence": rec.get("evidence") or [],
        "bucket": bucket, "unverifiable_reason": None,
        "n_arms_with_records": len(arms), "n_arms_that_tested_the_field": len(tested),
        "arms": sorted("%s:%s" % (e, a) for e, a in arms),
        "arms_tested": sorted("%s:%s" % (e, a) for e, a in tested),
        "moved_total": moved,
        "max_values_dispatched": max((v["n_values_max"] for ex in per_exp.values()
                                      for v in ex.values()), default=0),
        "attribution": attribution,
        "byte_level_only": bool(attribution) and "bit-exact" not in attribution,
        "n_contaminated": sum(r["n_contam"] for ex in per_exp.values() for v in ex.values()
                              for r in v["runs"].values()),
        "n_within_run_unstable": sum(r["n_within_run_unstable"] for ex in per_exp.values()
                                     for v in ex.values() for r in v["runs"].values()),
        "gating_fallback": any(v["gating_fallback"] for ex in per_exp.values()
                               for v in ex.values()),
        "noisy_harness_arms": sorted(a for ex in per_exp.values() for a, v in ex.items()
                                     if v["n_baseline_signatures"] > 1),
        "thin_cross_run": any(v["cross_run"] and v["cross_run"]["common"] < THIN_COMMON
                              for ex in per_exp.values() for v in ex.values()),
        "mixed_arm_liveness": mixed,
        "per_experiment": per_exp,
    }


def main():
    val, db, idx = load()
    resolve = resolver()
    partial = set(idx["_meta"]["partial_runs"])
    index, pseudo = idx["index"], idx["pseudo"]

    # ---------------- experiment coverage -----------------------------------
    cited = collections.Counter()
    for mn, fields in val["instructions"].items():
        for fn, rec in fields.items():
            if fn.startswith("_") or rec.get("label") not in EMIT_OK:
                continue
            for e in rec.get("evidence") or []:
                cited[e] += 1
    expcov = {}
    for eid, n in sorted(cited.items()):
        d = resolve(eid)
        rawdir = os.path.join(EXPDIR, d, "raw") if d else None
        nfiles = sum(len(fs) for _, _, fs in os.walk(rawdir)) if rawdir and os.path.isdir(rawdir) else 0
        recs = index.get(d, {}) if d else {}
        allruns = sorted({r for k in recs.values() for a in k.values() for r in a})
        gated = sorted(r for r in allruns
                       if not NONGATED.search(r) and (d + "/" + r) not in partial)
        expcov[eid] = {
            "dir": d, "emitter_grade_field_citations": n,
            "raw_dir_exists": bool(rawdir and os.path.isdir(rawdir)), "raw_files": nfiles,
            "db_fields_with_per_value_records": len(recs),
            "runs": allruns, "gated_runs": gated,
            "non_gated_runs": [r for r in allruns if r not in gated],
            "parse_verdict": ("per-value records parsed and bit-attributed" if recs else
                              ("raw present, NO per-value field records" if nfiles
                               else "no raw files")),
        }

    # ---------------- per-field classification ------------------------------
    audit = {}
    unverif_by_dir = collections.defaultdict(set)
    for mn, fields in val["instructions"].items():
        for fn, rec in fields.items():
            if fn.startswith("_") or rec.get("label") not in EMIT_OK:
                continue
            key = "%s.%s" % (mn, fn)
            ev = rec.get("evidence") or []
            per_exp = gather(key, ev, index, partial, resolve, pseudo)
            r = build_record(mn, fn, rec, per_exp)
            r["raw_files"] = sorted({"experiments/%s/raw/%s/" % (resolve(e), run)
                                     for e, ex in per_exp.items() for v in ex.values()
                                     for run in v["runs"]})
            audit[key] = r
            if r["bucket"] == "UNVERIFIABLE":
                for e in ev:
                    d = resolve(e)
                    if d:
                        unverif_by_dir[d].add((mn, fn))

    # ---------------- UNVERIFIABLE sub-reasons ------------------------------
    mention = collections.defaultdict(set)
    for d, names in unverif_by_dir.items():
        rawdir = os.path.join(EXPDIR, d, "raw")
        if not os.path.isdir(rawdir):
            continue
        for dirpath, _, filenames in os.walk(rawdir):
            for f in filenames:
                p = os.path.join(dirpath, f)
                try:
                    if os.path.getsize(p) > 64 * 1024 * 1024:
                        continue
                    txt = open(p, "r", errors="replace").read()
                except Exception:
                    continue
                for mn, fn in names:
                    if mn in txt and re.search(r"\b%s\b" % re.escape(fn), txt):
                        mention[d].add((mn, fn))
    seen_mn = idx["_meta"].get("mnemonics_seen_per_exp", {})
    for key, r in audit.items():
        if r["bucket"] != "UNVERIFIABLE":
            continue
        mn, fn = r["mnemonic"], r["field"]
        dirs = [resolve(e) for e in r["evidence"]]
        anyraw = any(expcov.get(e, {}).get("raw_files") for e in r["evidence"])
        named = any((mn, fn) in mention.get(d or "", set()) for d in dirs)
        # PRE_REGISTRATION amendment A4: distinguish "the raw never touched this
        # instruction" from "the raw swept this instruction but the sweep cannot be
        # attributed to this field" (e.g. EXP-0140 swept the descriptor-selecting
        # byte itself, so no single reg_move_* descriptor owns the cases).
        touched = any(mn in seen_mn.get(d or "", []) for d in dirs)
        r["unverifiable_reason"] = (
            "field-named-but-unstructured" if named else
            "raw-present-but-unattributable" if touched else
            "no-field-records" if anyraw else "no-raw")
        r["evidence_files_outside_raw"] = sorted(
            {"experiments/%s/%s" % (d, f)
             for d in dirs if d
             for f in os.listdir(os.path.join(EXPDIR, d))
             if f.endswith(".json") and f not in ("manifest.json", "CAPTURE_CONTRACT.json")})

    # ---------------- withhold sets & emittability --------------------------
    strict = sorted(k for k, r in audit.items() if r["bucket"] in WITHHOLD)
    lenient = sorted(k for k in strict
                     if not (audit[k]["bucket"] == "UNVERIFIABLE" and
                             audit[k]["unverifiable_reason"] == "field-named-but-unstructured"))
    inert_only = sorted(k for k, r in audit.items() if r["bucket"] == "INERT-SINGLE")

    def emittable(withheld):
        w = set(withheld)
        emit, rel = [], []
        for ins in db["instructions"]:
            m = ins["mnemonic"]
            entry = val["instructions"].get(m, {})
            fields = ins.get("fields", [])
            ok = True
            for f in fields:
                e = entry.get(f["name"])
                if e is None or e.get("label") not in EMIT_OK or ("%s.%s" % (m, f["name"])) in w:
                    ok = False
            if not fields:
                ok = (entry.get("_instruction", {}).get("label") in EMIT_OK)
            if "EMITTABLE VETO" in (entry.get("_instruction") or {}).get("note", ""):
                ok = False
            if ins.get("emitter_role") != DATA_WORD_ROLE:
                rel.append(m)
                if ok:
                    emit.append(m)
        return sorted(emit), sorted(rel)

    unstable_only = sorted(k for k, r in audit.items() if r["bucket"] == "UNSTABLE")
    chain_broken = sorted(k for k, r in audit.items()
                          if r["bucket"] in ("INERT-SINGLE", "UNSTABLE") or
                          (r["bucket"] == "UNVERIFIABLE" and r["unverifiable_reason"] in
                           ("no-field-records", "raw-present-but-unattributable")))
    base, rel = emittable([])
    variants = {}
    for name, w in (("strict", strict), ("lenient", lenient),
                    ("inert_single_only", inert_only),
                    ("inert_single_plus_unstable", sorted(set(inert_only) | set(unstable_only))),
                    ("chain_broken_only", chain_broken)):
        e, _ = emittable(w)
        variants[name] = {"n_fields_withheld": len(w), "emittable": len(e),
                          "mnemonics": e, "lost": sorted(set(base) - set(e))}
    emitjson = {"denominator_emitter_relevant": len(rel),
                "published": {"n": val["coverage"]["emittable_of_emitter_relevant"]},
                "recomputed_from_snapshot_no_withholding": {"n": len(base), "mnemonics": base},
                "variants": variants}

    # per-instruction blame: which withheld fields kill which currently-emittable
    # instruction, and which FIELD NAME recurs as the blocker across instructions.
    lost_detail = {}
    byname = collections.defaultdict(list)
    for ins in db["instructions"]:
        m = ins["mnemonic"]
        if m not in set(base):
            continue
        bad = [f["name"] for f in ins.get("fields", [])
               if "%s.%s" % (m, f["name"]) in set(strict)]
        if bad:
            lost_detail[m] = [{"field": b, "bucket": audit["%s.%s" % (m, b)]["bucket"],
                               "reason": audit["%s.%s" % (m, b)]["unverifiable_reason"],
                               "evidence": audit["%s.%s" % (m, b)]["evidence"]}
                              for b in sorted(bad)]
            for b in bad:
                byname[b].append(m)
    load_bearing = sorted(({"field_name": n, "n_instructions_blocked": len(ms),
                            "instructions": sorted(ms)} for n, ms in byname.items()),
                          key=lambda x: (-x["n_instructions_blocked"], x["field_name"]))

    # near-miss sensitivity: UNSTABLE fields that clear the movement test and fail
    # ONLY the 99% agreement bar.  Reported, never used to re-bucket.
    nearmiss = []
    for k in unstable_only:
        for eid, ex in audit[k]["per_experiment"].items():
            for arm, vv in ex.items():
                c = vv["cross_run"]
                if not c or c["agree_pct"] is None:
                    continue
                if (c["movedA"] >= 1 and c["movedB"] >= 1 and
                        min(c["movedA"], c["movedB"]) >= MOVED_OVER_DISAGREE * c["disagreements"]
                        and 95.0 <= c["agree_pct"] < MIN_AGREE_PCT):
                    nearmiss.append({"field": k, "experiment": eid, "arm": arm,
                                     "agree_pct": c["agree_pct"], "common": c["common"],
                                     "moved": [c["movedA"], c["movedB"]],
                                     "disagreements": c["disagreements"]})
                    break
            else:
                continue
            break
    e_nm, _ = emittable(sorted(set(strict) - {n["field"] for n in nearmiss}))
    emitjson["sensitivity_agree_95pct"] = {
        "near_miss_fields": nearmiss,
        "n": len(nearmiss),
        "emittable_if_near_miss_kept": len(e_nm),
    }

    # ---------------- controls ----------------------------------------------
    orchpath = os.path.join(EXPDIR, "EXP-0155-g17p-emit-tex-frag", "analysis",
                            "withheld_by_orchestrator.json")
    orch = json.load(open(orchpath))
    c1 = {}
    for k in sorted(orch):
        mn, _, fn = k.partition(".")
        pe = gather(k, ["EXP-0155"], index, partial, resolve, pseudo)
        b, arms, tested, moved = classify(pe)
        c1[k] = {"audit_bucket": b, "withheld_by_audit": b in WITHHOLD,
                 "n_arms_tested": len(tested), "moved_total": moved,
                 "orchestrator_reason": orch[k]["why"]}
    c1_ok = all(v["withheld_by_audit"] for v in c1.values())
    c3 = [k for k, r in audit.items()
          if r["bucket"] == "STABLE-LIVE" and
          any("|" in "" for _ in [0])]  # placeholder, filled below
    controls = {
        "C1_reproduce_orchestrator_EXP0155": {"all_15_withheld_by_audit": c1_ok, "detail": c1},
        "C2_iter.dst": {"bucket": audit.get("iter.dst", {}).get("bucket"),
                        "pass": audit.get("iter.dst", {}).get("bucket") == "STABLE-LIVE"},
        "C4_counts": {"expected_fields": val["coverage"]["by_label"]["hardware-run"] +
                      val["coverage"]["by_label"]["isolated-byte-diff"],
                      "audited_fields": len(audit),
                      "pass": len(audit) == val["coverage"]["by_label"]["hardware-run"] +
                      val["coverage"]["by_label"]["isolated-byte-diff"],
                      "cited_experiments_accounted": len(expcov)},
    }

    buckets = collections.Counter(r["bucket"] for r in audit.values())
    reasons = collections.Counter(r["unverifiable_reason"] for r in audit.values()
                                  if r["bucket"] == "UNVERIFIABLE")
    summary = {"total": len(audit), "buckets": dict(buckets),
               "unverifiable_reasons": dict(reasons),
               "byte_level_only": sum(1 for r in audit.values() if r["byte_level_only"]),
               "mixed_arm_liveness": sum(1 for r in audit.values() if r["mixed_arm_liveness"])}

    meta = {"experiment": "EXP-0189-closing-audit",
            "validation_snapshot_sha256_pinned":
                "867e4b05dbcd000f98a8ac4705d07f419b1d0a69c4b276e030b0daf225eaf0b7",
            "db_snapshot_sha256": val["db_sha256"],
            "thresholds": {"min_common": MIN_COMMON, "min_agree_pct": MIN_AGREE_PCT,
                           "moved_over_disagree": MOVED_OVER_DISAGREE},
            "summary": summary}
    json.dump({"_meta": meta, "fields": audit},
              open(os.path.join(HERE, "audit.json"), "w"), indent=1, sort_keys=True)
    json.dump({"_meta": {"experiment": "EXP-0189-closing-audit",
                         "schema": "FIELD-SWEEP-PROTOCOL.md section 5 flat <mnemonic>.<field>",
                         "policy": "withhold INERT-SINGLE, UNSTABLE, UNVERIFIABLE",
                         "counts": summary},
               "strict": {k: {"label": "untested",
                              "range": val["instructions"][audit[k]["mnemonic"]]
                                          [audit[k]["field"]].get("range", ""),
                              "note": NOTES[audit[k]["bucket"]] % (
                                  audit[k]["max_values_dispatched"],
                                  audit[k]["n_arms_that_tested_the_field"],
                                  audit[k]["moved_total"]) + (
                                  " Reason: %s." % audit[k]["unverifiable_reason"]
                                  if audit[k]["unverifiable_reason"] else ""),
                              "bucket": audit[k]["bucket"],
                              "reason": audit[k]["unverifiable_reason"],
                              "label_now": audit[k]["label"],
                              "target": audit[k]["target"],
                              "evidence": audit[k]["evidence"],
                              "n_arms_that_tested_the_field":
                                  audit[k]["n_arms_that_tested_the_field"],
                              "max_values_dispatched": audit[k]["max_values_dispatched"],
                              "moved_total": audit[k]["moved_total"],
                              "arms_tested": audit[k]["arms_tested"],
                              "raw_files": audit[k]["raw_files"]} for k in strict},
               "lenient_subset": lenient,
               "instructions_that_lose_emittable_status": variants["strict"]["lost"],
               "why_each_instruction_is_lost": lost_detail,
               "load_bearing_field_names": load_bearing},
              open(os.path.join(HERE, "reclassify.json"), "w"), indent=1, sort_keys=True)
    json.dump(expcov, open(os.path.join(HERE, "experiment_coverage.json"), "w"),
              indent=1, sort_keys=True)
    json.dump(emitjson, open(os.path.join(HERE, "emittability.json"), "w"),
              indent=1, sort_keys=True)
    json.dump(controls, open(os.path.join(HERE, "controls.json"), "w"),
              indent=1, sort_keys=True)
    json.dump({k: audit[k]["mixed_arm_liveness"] for k in sorted(audit)
               if audit[k]["mixed_arm_liveness"]},
              open(os.path.join(HERE, "mixed_arm_liveness.json"), "w"),
              indent=1, sort_keys=True)

    print(json.dumps(summary, indent=1))
    print("emittable of %d: published %d | recomputed %d | strict %d | lenient %d | inert-single-only %d"
          % (len(rel), emitjson["published"]["n"], len(base),
             variants["strict"]["emittable"], variants["lenient"]["emittable"],
             variants["inert_single_only"]["emittable"]))
    print("C1 all-15-withheld:", c1_ok, " C2:", controls["C2_iter.dst"], " C4:", controls["C4_counts"]["pass"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
