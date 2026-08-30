#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0192 -- does fault-vs-ok "movement" meet the hardware-run / isolated-byte-diff bar?

The criterion is frozen in ../PRE_REGISTRATION.md section 4 and is deliberately NOT
command-line tunable.

NO THIRD INDEXER IS WRITTEN.  Two committed implementations supply every input:

  * EXP-0190/work/raw_index.json.gz -- the corrected indexer's own attribution of raw
    records to db fields, including the per-cell modal signature map `keys`, whose
    signature is exactly `collect_raw.py::sig_of` = "<hardclass>|<sha1(observed)[:10]>".
    Splitting that signature is what lets this script separate a FAULT transition from a
    transition between two distinct VALID payloads -- the distinction `moved` cannot make.
  * EXP-0191/analysis/detection_gate.py::payload_of -- imported unmodified -- for the
    record-level validity rules (error payloads, empty observations, bookkeeping-only
    dicts), used as the independent second pass of PRE_REGISTRATION section 4.3 rule 3.

Outputs (analysis/):
  valid_payload_audit.json    -- the full per-row / per-arm table and the verdicts
  reclassify.json             -- ONLY if PRE_REGISTRATION section 4.2 Case C fires
"""
import collections
import gzip
import hashlib
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.abspath(os.path.join(HERE, ".."))
EXPDIR = os.path.abspath(os.path.join(EXP, ".."))
ROOT = os.path.abspath(os.path.join(EXPDIR, ".."))

E0190 = os.path.join(EXPDIR, "EXP-0190-indexer-refilter")
E0191 = os.path.join(EXPDIR, "EXP-0191-detection-gate")

# ---- import EXP-0191's validity rules, unmodified --------------------------
_spec = importlib.util.spec_from_file_location(
    "detection_gate", os.path.join(E0191, "analysis", "detection_gate.py"))
DG = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(DG)
payload_of = DG.payload_of
HARD = DG.HARD
CONTAM = DG.CONTAM

# EXP-0190/collect_raw.py's own HARD set, re-asserted so a drift aborts the run.
INDEX_HARD = {"fault", "hang", "undecodable", "killed", "not_written",
              "no_draw", "lost_7_of_8", "nondeterministic"}
assert HARD == INDEX_HARD, "HARD set drift between EXP-0190 and EXP-0191"

EMIT_OK = ("hardware-run", "isolated-byte-diff")

# ---- scope, PRE_REGISTRATION section 6 -------------------------------------
ROWS = ["jump_cond.offset", "ret.linkmode", "ret_luse.linkmode", "n3_sample_read.tail"]
CONTROLS = ["call.b5"]          # R2: must NOT be withheld


def sha_files(paths):
    out = {}
    for p in paths:
        h = hashlib.sha256()
        with open(os.path.join(ROOT, p), "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        out[p] = h.hexdigest()
    return out


def load():
    idxfile = json.load(gzip.open(os.path.join(E0190, "work",
                                                  "raw_index.json.gz"), "rt"))
    idx = idxfile["index"]
    audit = json.load(open(os.path.join(E0190, "analysis", "audit.json")))["fields"]
    val = json.load(open(os.path.join(ROOT, "tools", "agx-isa", "validation.json")))
    db = json.load(open(os.path.join(ROOT, "tools", "agx-isa", "db.json")))
    gate = json.load(open(os.path.join(E0191, "analysis", "gate_results.json")))
    return idx, audit, val, db, gate


def db_geom(db):
    g = {}
    for i in db["instructions"]:
        for f in i.get("fields", []):
            g["%s.%s" % (i["mnemonic"], f["name"])] = {"start": f["start"],
                                                       "width": f["width"]}
    return g


def live_labels(val):
    """flat `<mnemonic>.<field>` -> row, from the live validation.json."""
    out = {}
    for mn, fields in val["instructions"].items():
        if not isinstance(fields, dict):
            continue
        for fn, fv in fields.items():
            if fn.startswith("_") or not isinstance(fv, dict) or "label" not in fv:
                continue
            out["%s.%s" % (mn, fn)] = fv
    return out


# ---------------------------------------------------------------------------
# 1. Index-level pass.  A `keys` entry is "<rest>:<fieldvalue>" -> "<hard>|<hash>".
# ---------------------------------------------------------------------------
def split_sig(s):
    hard, _, h = s.partition("|")
    return hard, h


def arm_stats(runs):
    """PRE_REGISTRATION section 4.1, over one arm's gated runs."""
    valid_payloads = set()          # distinct VALID observation hashes
    all_sigs = set()                # distinct signatures INCLUDING fault classes
    legal_values = set()            # field values with >=1 non-HARD case
    fault_values = set()
    hard_counts = collections.Counter()
    n_cells = 0
    n_cases = 0
    per_run = {}
    for run, e in sorted(runs.items()):
        n_cases += e.get("n_cases", 0)
        rv, ra, rl = set(), set(), set()
        for cell, sig in (e.get("keys") or {}).items():
            n_cells += 1
            fv = cell.split(":", 1)[1]
            hard, h = split_sig(sig)
            ra.add(sig)
            all_sigs.add(sig)
            if hard in HARD:
                hard_counts[hard] += 1
                fault_values.add(fv)
            else:
                legal_values.add(fv)
                rl.add(fv)
                if h and h != "-":
                    valid_payloads.add(h)
                    rv.add(h)
        per_run[run] = {"n_cases": e.get("n_cases"), "n_contam": e.get("n_contam"),
                        "n_values_indexed": e.get("n_values"), "moved": e.get("moved"),
                        "n_keyed_cells": len(e.get("keys") or {}),
                        "V_valid_payloads": len(rv),
                        "V_all_signatures": len(ra),
                        "L_legal_values": len(rl)}
    return {"n_cases": n_cases, "n_keyed_cells": n_cells,
            "n_fault_cells": sum(hard_counts.values()),
            "hard_class_counts": dict(hard_counts),
            "V_valid_payloads": len(valid_payloads),
            "V_all_signatures": len(all_sigs),
            "L_legal_values": len(legal_values),
            "n_fault_only_values": len(fault_values - legal_values),
            "per_run": per_run}


def index_pass(idx, row):
    """Every arm in the WHOLE corpus that the indexer attributes to `row`."""
    out = {}
    for expdir, keys in idx.items():
        if expdir.startswith("_"):
            continue
        if row not in keys:
            continue
        for arm, runs in keys[row].items():
            out["%s|%s" % (expdir, arm)] = arm_stats(runs)
    return out


# ---------------------------------------------------------------------------
# 2. Record-level second pass (PRE_REGISTRATION 4.3 rule 3), using payload_of.
#    Keyed by (experiment dir, armkey) exactly as detection_gate.py builds armkey.
# ---------------------------------------------------------------------------
def record_pass(want_arms):
    """want_arms: {(expdir, armkey)} -> per record-`field`-name payload stats."""
    res = collections.defaultdict(lambda: collections.defaultdict(
        lambda: {"payloads": set(), "outcomes": collections.Counter(),
                 "invalid": collections.Counter(), "values_legal": set(),
                 "values_hard": set(), "n": 0}))
    exps = {e for e, _ in want_arms}
    for expdir in sorted(exps):
        raw = os.path.join(EXPDIR, expdir, "raw")
        if not os.path.isdir(raw):
            continue
        for dp, _, fns in os.walk(raw):
            for fn in fns:
                if not fn.endswith(".jsonl"):
                    continue
                for line in open(os.path.join(dp, fn), errors="replace"):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(rec, dict):
                        continue
                    f, i = rec.get("field"), rec.get("instr")
                    if not (isinstance(f, str) and isinstance(i, str)):
                        continue
                    ac = [str(rec[k]) for k in ("carrier", "arm")
                          if rec.get(k) not in (None, "")]
                    armkey = "|".join(ac) if ac else "-"
                    if (expdir, armkey) not in want_arms:
                        continue
                    st = res[(expdir, armkey)]["%s.%s" % (i, f)]
                    st["n"] += 1
                    oc = rec.get("outcome")
                    st["outcomes"][str(oc)] += 1
                    v = rec.get("value")
                    v = v if isinstance(v, (int, str)) else json.dumps(v, sort_keys=True)
                    p, why = payload_of(rec)
                    if p is None:
                        st["invalid"][why or "?"] += 1
                        if oc in HARD:
                            st["values_hard"].add(v)
                        continue
                    st["values_legal"].add(v)
                    st["payloads"].add(DG.sha(p))
    out = {}
    for (expdir, armkey), byfield in res.items():
        out["%s|%s" % (expdir, armkey)] = {
            k: {"n_records": s["n"],
                "V_valid_payloads": len(s["payloads"]),
                "L_legal_values": len(s["values_legal"]),
                "n_fault_only_values": len(s["values_hard"] - s["values_legal"]),
                "outcomes": dict(s["outcomes"]),
                "invalid_reasons": dict(s["invalid"])}
            for k, s in sorted(byfield.items())}
    return out


# ---------------------------------------------------------------------------
# 3. The frozen criterion, PRE_REGISTRATION section 4.2
# ---------------------------------------------------------------------------
def classify_row(arms, rec_level, row):
    """-> (case, reason).  Case A/B STAND; Case C WITHHOLDS."""
    if not arms:
        return "UNVERIFIABLE-HERE", "no arm in the pinned index attributes to this row (R3)"
    # rule 3: record level wins where it recovers more distinct valid payloads
    recV = {}
    for armk, byfield in rec_level.items():
        if row in byfield:
            recV[armk] = byfield[row]["V_valid_payloads"]
    bestV = max([a["V_valid_payloads"] for a in arms.values()] + list(recV.values()))
    if bestV >= 2:
        return "A", "an attributing arm shows %d distinct VALID payloads" % bestV
    maxL = max(a["L_legal_values"] for a in arms.values())
    maxLrec = max([rec_level[k][row]["L_legal_values"] for k in recV] or [0])
    L = max(maxL, maxLrec)
    if L <= 1:
        return "B", ("no arm shows 2 distinct valid payloads, and at most %d value(s) of "
                     "the field are observed LEGAL -- nothing for an emitter to choose" % L)
    return "C", ("no arm shows 2 distinct valid payloads, yet %d distinct values are "
                 "observed LEGAL: >=2 legal values are indistinguishable, which is an "
                 "INERTNESS observation that `moved` re-scored as movement" % L)


def main():
    idx, audit, val, db, gate = load()
    geom = db_geom(db)
    labels = live_labels(val)

    slkey = "stable_live_arms_with_fewer_than_2_distinct_valid_payloads"
    seven = gate.get(slkey) or gate.get("_post_hoc", {}).get(slkey) or {}
    if not seven:
        for v in gate.values():
            if isinstance(v, dict) and slkey in v:
                seven = v[slkey]
                break

    scope_rows = list(ROWS)
    for arm, meta in (seven.items() if isinstance(seven, dict) else []):
        for f in (meta.get("fields") or []):
            if f not in scope_rows:
                scope_rows.append(f)

    # index-level pass for every row in scope + the controls
    per_row = {}
    for row in scope_rows + CONTROLS:
        per_row[row] = index_pass(idx, row)

    want = set()
    for row, arms in per_row.items():
        for armk in arms:
            e, _, a = armk.partition("|")
            want.add((e, a))
    if isinstance(seven, dict):
        for armk in seven:
            e, _, a = armk.partition("|")
            want.add((e, a))
    rec = record_pass(want)

    verdicts = {}
    for row in scope_rows + CONTROLS:
        arms = per_row[row]
        case, why = classify_row(arms, rec, row)
        au = audit.get(row, {})
        verdicts[row] = {
            "live_label": (labels.get(row) or {}).get(
                "label", "(absent from validation.json)"),
            "live_range": (labels.get(row) or {}).get("range"),
            "live_note": (labels.get(row) or {}).get("note"),
            "snapshot_label": au.get("label"),
            "bucket": au.get("bucket"),
            "moved_total": au.get("moved_total"),
            "stable_live_arms": [a for a, v in
                                 ((k2, v2) for ex in au.get("per_experiment", {}).values()
                                  for k2, v2 in ex.items()) if v.get("stable_live")],
            "target": au.get("target"),
            "evidence": au.get("evidence"),
            "n_attributing_arms": len(arms),
            "arms": arms,
            "record_level": {k: v.get(row) for k, v in rec.items() if row in v},
            "cross_run": {k: v.get("cross_run") for ex in au.get("per_experiment", {}).values()
                          for k, v in ex.items()},
            "case": case,
            "verdict": {"A": "STANDS", "B": "STANDS (legality-only)",
                        "C": "WITHHOLD"}.get(case, case),
            "reason": why,
            "geometry": geom.get(row),
            "is_control": row in CONTROLS,
        }

    withhold = {r: v for r, v in verdicts.items()
                if v["case"] == "C" and v["live_label"] in EMIT_OK and r not in CONTROLS}

    ctrl_fail = [c for c in CONTROLS if verdicts[c]["case"] == "C"]

    out = {
        "_meta": {
            "experiment": "EXP-0192-fault-as-movement",
            "question": ("does a field whose movement consists only of ok<->fault "
                         "transitions, with fewer than two distinct VALID payloads, meet "
                         "the hardware-run / isolated-byte-diff bar?"),
            "criterion": "PRE_REGISTRATION.md section 4.2, frozen before any count "
                         "was computed, at repo revision "
                         "8d01daa35a53a478f72fe800dc94d27492c11d77 (tree clean)",
            "reused_implementations": [
                "EXP-0190/analysis/collect_raw.py (via work/raw_index.json.gz; its "
                "sig_of signature is split, not recomputed)",
                "EXP-0190/analysis/audit.py (via analysis/audit.json)",
                "EXP-0191/analysis/detection_gate.py::payload_of (imported unmodified)"],
            "input_hashes": sha_files([
                "tools/agx-isa/validation.json", "tools/agx-isa/db.json",
                "experiments/EXP-0190-indexer-refilter/work/raw_index.json.gz",
                "experiments/EXP-0190-indexer-refilter/analysis/audit.json",
                "experiments/EXP-0191-detection-gate/analysis/detection_gate.py",
                "experiments/EXP-0191-detection-gate/analysis/reclassify.json"]),
            "hard_classes": sorted(HARD),
            "contaminated_outcomes": sorted(CONTAM),
            "scope_rows": scope_rows,
            "controls": CONTROLS,
            "device_contacted": False,
        },
        "summary": {
            "n_rows_examined": len(scope_rows),
            "case_A_stands": sorted(r for r in scope_rows if verdicts[r]["case"] == "A"),
            "case_B_stands_legality_only": sorted(
                r for r in scope_rows if verdicts[r]["case"] == "B"),
            "case_C_withhold": sorted(r for r in scope_rows if verdicts[r]["case"] == "C"),
            "unverifiable_here": sorted(
                r for r in scope_rows if verdicts[r]["case"] == "UNVERIFIABLE-HERE"),
            "criterion_fired": bool(withhold),
            "R2_control_check": {c: verdicts[c]["case"] for c in CONTROLS},
            "R2_control_broken": ctrl_fail,
        },
        "seven_stable_live_arms_from_EXP_0191": seven,
        "verdicts": verdicts,
    }
    with open(os.path.join(HERE, "valid_payload_audit.json"), "w") as f:
        json.dump(out, f, indent=1, sort_keys=True, default=list)
        f.write("\n")

    if withhold:
        rc = {"_meta": {"experiment": "EXP-0192-fault-as-movement",
                        "trigger": "PRE_REGISTRATION.md section 4.2 Case C",
                        "action": "RECOMMENDED withholding to `untested`; this experiment "
                                  "edits no label. The orchestrator owns validation.json."}}
        for r, v in sorted(withhold.items()):
            g = geom.get(r) or {}
            rc[r] = {"current_label": v["live_label"],
                     "start": g.get("start"), "width": g.get("width"),
                     "case": "C", "reason": v["reason"],
                     "L_legal_values_max": max(a["L_legal_values"]
                                               for a in v["arms"].values()),
                     "V_valid_payloads_max": max(a["V_valid_payloads"]
                                                 for a in v["arms"].values()),
                     "n_fault_cells": {k: a["n_fault_cells"] for k, a in v["arms"].items()},
                     "arms": sorted(v["arms"]),
                     "target": v["target"], "evidence": v["evidence"],
                     "recommended_note": (
                         "EXP-0192 withheld: the STABLE-LIVE promotion rests only on "
                         "ok<->fault signature transitions. No arm produced two distinct "
                         "VALID observation payloads, while >=2 field values ran legally "
                         "and were indistinguishable -- an inertness observation that "
                         "collect_raw.py::sig_of re-scored as movement. The fault wall "
                         "itself remains a valid legal-set bound.")}
        with open(os.path.join(HERE, "reclassify.json"), "w") as f:
            json.dump(rc, f, indent=1, sort_keys=True)
            f.write("\n")

    print(json.dumps(out["summary"], indent=1))
    for r in scope_rows + CONTROLS:
        v = verdicts[r]
        print("%-24s %-22s case=%s  V=%s L=%s faults=%s arms=%d" % (
            r, v["live_label"], v["case"],
            [a["V_valid_payloads"] for a in v["arms"].values()],
            [a["L_legal_values"] for a in v["arms"].values()],
            [a["n_fault_cells"] for a in v["arms"].values()],
            v["n_attributing_arms"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
