#!/usr/bin/env python3
"""verdicts.py -- EXP-0204 verdicts on the SIX INDEPENDENT AXES.

Recomputed FROM raw/ only.  Never from a run manifest, never from memory.

`RE_EXPERIMENT_PROCESS_CORRECTIONS.md` sec.2: one label must no longer carry four
conclusions.  Every field is scored separately on encoding geometry, liveness,
semantics, compiler recipe, target and reproducibility, with EXACT NUMERATORS AND
DENOMINATORS -- never a percentage alone (sec.5 Phase 2).  The legacy
`docs/evidence-classification.md` label is emitted only as the strictest one all
six axes support.

THE GATES (frozen in PRE_REGISTRATION sec.15; do not edit without a new amendment)

  A  actual-byte ledger: requested value == value decoded from the ACTUAL bytes
     re-read from the dispatched program.  A round trip is not this gate.
  B  a positive control in the arm's own dimension moved the same observable.
     If it failed, the arm is `carrier-undecidable` and zero movement is NOT
     evidence of inertness.
  C  an independent semantic predictor assigned the case to a modelled bucket.
     `sem_checked == 0` can never produce `hardware-run`.
  D  a generated compiler recipe.  NOT ATTEMPTED here, so nothing is `emittable`.
  E  two CLEAN runs (quiet machine) in reversed/shuffled order with identical
     ledgers and no victim/cascade evidence.

  and the arithmetic rule, written LITERALLY:
        moved >= 2*disagree   AND   moved > 0
  NOT `moved >= 2*max(disagree,1)`, which cannot promote any width-1 field
  (FIELD-SWEEP-PROTOCOL sec.5b).  selftest() proves both directions before any
  verdict is computed.
"""
import collections, glob, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "harness"))
sys.path.insert(0, os.path.join(HERE, "pinned"))
import carriers as CA                       # noqa: E402
import arms as ARMSPEC                      # noqa: E402
import isadb                                # noqa: E402

CONTROL = {"_baseline", "_detect", "_detect_summary", "_baseline_recheck",
           "_baseline_final", "_cascade_check", "_arm_not_run", "_sites"}
HARD = {"fault", "hang", "undecodable", "malformed", "unreproduced", "not_run",
        "ledger_mismatch"}
AGREE_BAR = 99.0


def selftest():
    """This gate must be able to say NO.  Thirteen checks in this corpus could not."""
    def gate(moved, disagree):
        return moved >= 2 * disagree and moved > 0
    assert gate(1, 0), "width-1 trap: 1 moved / 0 disagreements MUST pass"
    assert not gate(0, 0), "a field that never moved must NOT pass"
    assert not gate(1, 1), "moved must be >= 2x disagreements"
    assert gate(4, 2)
    return True


def load(run_dir):
    p = os.path.join(run_dir, "sweep.jsonl")
    out = []
    if not os.path.exists(p):
        return out
    for line in open(p, errors="replace"):
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def quietness(run_dir):
    """A MEASUREMENT of whether the machine was quiet, not a claim."""
    p = os.path.join(run_dir, "procs.jsonl")
    if not os.path.exists(p):
        return {"quiet": None, "reason": "no procs.jsonl (run predates the sampler)"}
    n = busy = worst = 0
    names = collections.Counter()
    for line in open(p, errors="replace"):
        try:
            s = json.loads(line)
        except Exception:
            continue
        n += 1
        if s.get("n_foreign", 0) > 0:
            busy += 1
            worst = max(worst, s["n_foreign"])
            for f in s.get("foreign", []):
                names[f["cmd"].split()[0].split("/")[-1][:40]] += 1
    return {"quiet": (busy == 0 and n > 0), "samples": n, "busy_samples": busy,
            "max_concurrent_foreign_procs": worst,
            "foreign_process_names": dict(names.most_common(6))}


def payload(r):
    o = r.get("observed") or {}
    return json.dumps(o.get("hh"), sort_keys=True)


def main():
    selftest()
    runs = sorted(d for d in glob.glob(os.path.join(HERE, "raw", "g17p_*"))
                  if os.path.isdir(d))
    q = {os.path.basename(d): quietness(d) for d in runs}
    baseline_val = {(a["id"], f): a["baseline_fields"][f]
                    for a in ARMSPEC.ARMS for f in a["fields"]}

    # per (mnemonic, field, arm, run): value -> record
    cell = collections.defaultdict(dict)
    detect = collections.defaultdict(dict)
    base_pl = collections.defaultdict(dict)
    base_oracle = collections.defaultdict(dict)
    for d in runs:
        rid = os.path.basename(d)
        for r in load(d):
            arm, f = r.get("carrier"), r.get("field")
            if f == "_detect_summary":
                try:
                    detect[arm][rid] = json.loads(r["note"])
                except Exception:
                    pass
                continue
            if f == "_baseline":
                base_pl[arm][rid] = payload(r)
                o = r.get("oracle") or {}
                base_oracle[arm][rid] = {"checked": o.get("checked"),
                                         "agree": o.get("agree"),
                                         "match": r.get("match")}
                continue
            if f in CONTROL or r.get("value", -1) < 0:
                continue
            cell[(r["instr"], f, arm, rid)][r["value"]] = r

    fields = collections.defaultdict(list)
    for (m, f, arm, rid) in cell:
        if arm not in fields[(m, f)]:
            fields[(m, f)].append(arm)

    out = {
        "_experiment": "EXP-0204",
        "_target": "G17P (Apple A18 Pro, applegpu_g17p) -- DIRECT, not INFERRED",
        "_spec": ("RE_EXPERIMENT_PROCESS_CORRECTIONS.md (normative, wins) + "
                  "docs/evidence-classification.md sec.2 + FIELD-SWEEP-PROTOCOL sec.5; "
                  "gates frozen in PRE_REGISTRATION sec.15"),
        "_runs": {os.path.basename(d): q[os.path.basename(d)] for d in runs},
        "_gate_selftest": ("passed: promotes (moved=1,disagree=0); refuses (moved=0); "
                           "refuses (moved=1,disagree=1)"),
        "_gate_D_note": ("Gate D (generated compiler recipe) was NOT ATTEMPTED in this "
                         "experiment.  Every arm splices one field of a compiler-emitted "
                         "occurrence, which is a liveness/semantics instrument, not a "
                         "generation proof.  No instruction here is claimed emittable."),
        "arms": {}, "fields": {}, "db_defects": {},
    }

    for (m, f), armlist in sorted(fields.items()):
        key = f"{m}.{f}"
        desc = isadb._BY_MNEM[m]
        fd = next(x for x in desc["fields"] if x["name"] == f)
        w = fd["width"]
        per_arm = {}
        for arm in armlist:
            rids = sorted(rid for (mm, ff, aa, rid) in cell
                          if (mm, ff, aa) == (m, f, arm))
            bval = baseline_val.get((arm, f))
            rows = {rid: cell[(m, f, arm, rid)] for rid in rids}
            # ---- Gate A: the actual-byte ledger -------------------------
            led_ok = led_seen = 0
            actual_enc = set()
            requested = set()
            for rid in rids:
                for v, r in rows[rid].items():
                    L = r.get("ledger") or {}
                    requested.add(v)
                    if L.get("actual_bytes"):
                        actual_enc.add(L["actual_bytes"])
                    if L.get("gate_a_ok") is not None:
                        led_seen += 1
                        led_ok += 1 if L["gate_a_ok"] else 0
            # ---- outcome census over the FIRST run ----------------------
            oc = collections.Counter()
            sem = collections.Counter()
            sem_checked = 0
            r0 = rows[rids[0]] if rids else {}
            for v, r in r0.items():
                oc[r.get("outcome")] += 1
                s = r.get("semantic") or {}
                sem[s.get("bucket", "none")] += 1
                if s.get("checked"):
                    sem_checked += 1
            # ---- liveness + cross-run ------------------------------------
            moved = disagree = common = 0
            moved_vals = []
            if len(rids) >= 2:
                a, b = rows[rids[0]], rows[rids[1]]
                ba = base_pl.get(arm, {}).get(rids[0])
                bb = base_pl.get(arm, {}).get(rids[1])
                for v in sorted(set(a) & set(b)):
                    ra, rb = a[v], b[v]
                    if ra.get("outcome") in HARD or rb.get("outcome") in HARD:
                        continue
                    if ra.get("outcome") == "foreign" or rb.get("outcome") == "foreign":
                        continue
                    common += 1
                    pa, pb = payload(ra), payload(rb)
                    if pa != pb:
                        disagree += 1
                        continue
                    if ba is not None and pa != ba:
                        moved += 1
                        moved_vals.append(v)
            V = len({payload(r) for r in r0.values()
                     if r.get("outcome") not in HARD and r.get("outcome") != "foreign"})
            dm = detect.get(arm, {})
            powered = all(bool((dm.get(r) or {}).get("detect_ok")) for r in rids) if rids else False
            dim = [c for r in rids
                   for c in ((dm.get(r) or {}).get("dimension_controls_moved", {})
                             .get(key, []))]
            dim_ok = bool(dim) and all(
                bool((dm.get(r) or {}).get("dimension_controls_moved", {}).get(key))
                for r in rids)
            per_arm[arm] = {
                "runs": rids,
                "baseline_field_value": bval,
                "baseline_host_oracle": base_oracle.get(arm, {}),
                "gate_A_ledger": {"cases_with_ledger": led_seen, "cases_ok": led_ok,
                                  "distinct_requested_values": len(requested),
                                  "distinct_actual_encodings": len(actual_enc),
                                  "passed": led_seen > 0 and led_ok == led_seen},
                "gate_B_control": {"detection_power": powered,
                                   "dimension_controls_moved": sorted(set(dim)),
                                   "passed": bool(powered and dim_ok)},
                "gate_C_semantics": {"sem_checked": sem_checked,
                                     "buckets": dict(sem),
                                     "passed": sem_checked > 0},
                "outcomes_run1": dict(oc),
                "cross_run": {"common_values": common, "disagreements": disagree,
                              "agreement": (f"{common - disagree}/{common}"
                                            if common else "0/0"),
                              "agreement_pct": (round(100.0 * (common - disagree) / common, 2)
                                                if common else None)},
                "moved": moved, "moved_values_sample": moved_vals[:24],
                "distinct_valid_payloads": V,
            }
            out["arms"][f"{key}@{arm}"] = per_arm[arm]

        rows = list(per_arm.values())
        clean_runs = [r for r in sorted({x for a in per_arm.values() for x in a["runs"]})
                      if (q.get(r) or {}).get("quiet")]
        # ---------------- axis scoring ---------------------------------
        gA = [r for r in rows if r["gate_A_ledger"]["passed"]]
        gB = [r for r in rows if r["gate_B_control"]["passed"]]
        gC = [r for r in rows if r["gate_C_semantics"]["passed"]]
        n_moved_arms = sum(1 for r in rows if r["moved"] > 0)
        agr = [r["cross_run"]["agreement_pct"] for r in rows
               if r["cross_run"]["agreement_pct"] is not None]
        repro_arms = [r for r in rows
                      if r["cross_run"]["agreement_pct"] is not None
                      and r["cross_run"]["agreement_pct"] >= AGREE_BAR
                      and r["moved"] >= 2 * r["cross_run"]["disagreements"]
                      and r["moved"] > 0]
        sem_correct = sum(r["gate_C_semantics"]["buckets"].get("correct", 0) for r in rows)
        sem_total = sum(r["gate_C_semantics"]["sem_checked"] for r in rows)

        geometry = ("ledger-verified" if gA and len(gA) == len(rows) else
                    ("ledger-verified(partial)" if gA else "unverified"))
        if not gB:
            liveness = "carrier-undecidable"
        elif n_moved_arms:
            liveness = "live"
        else:
            liveness = "accepted-inert"
        semantics = ("unknown" if sem_total == 0 else
                     ("bounded-map" if sem_correct else "hypothesis"))
        repro = ("independently-confirmed" if (repro_arms and clean_runs and
                                               len(clean_runs) >= 2)
                 else ("auditable" if repro_arms else "incomplete"))
        # legacy label = the strictest all six axes support
        if (geometry.startswith("ledger-verified") and liveness == "live"
                and semantics == "bounded-map" and repro == "independently-confirmed"):
            legacy = "hardware-run"
        elif (geometry.startswith("ledger-verified") and liveness == "live"
              and semantics == "bounded-map" and repro_arms):
            legacy = "isolated-byte-diff"
        else:
            # RE_EXPERIMENT_PROCESS_CORRECTIONS sec.2, strict mapping:
            # `isolated-byte-diff` "requires a PREDICTED SEMANTIC EFFECT at the
            # tested point, not merely an isolated byte difference", and
            # `hardware-run` requires semantic checks against an independent
            # predictor.  Reproducible liveness with a refuted or absent semantic
            # model therefore maps to the legacy `untested` -- which is NOT "no
            # evidence".  The evidence is in `axes` and `counts`; do not round
            # liveness up into the legacy label.
            legacy = "untested"

        enc = (1 << w) if w <= 8 else None
        disp = max((r["gate_A_ledger"]["distinct_requested_values"] for r in rows),
                   default=0)
        out["fields"][key] = {
            "label": legacy,
            "axes": {
                "encoding_geometry": geometry,
                "liveness": liveness,
                "semantics": semantics,
                "compiler_recipe": "not-generated",
                "target": "G17P-direct",
                "reproducibility": repro,
            },
            "target": "G17P",
            "evidence": ["EXP-0204"],
            "start": fd["start"], "width": fd["width"],
            "range": (f"0..{enc - 1} dense (all {enc} values) x {len(rows)} arms"
                      if enc else
                      f"{disp} sampled values of 2^{w} (boundaries + powers of two + "
                      f"all-ones prefixes + 16 hashed interior) x {len(rows)} arms"),
            "counts": {
                "encodable_values": enc,
                "dispatched_values_per_arm": disp,
                "distinct_requested_values": disp,
                "distinct_bytes": max((r["gate_A_ledger"]["distinct_actual_encodings"]
                                       for r in rows), default=0),
                "ledger_cases_ok_over_checked":
                    f"{sum(r['gate_A_ledger']['cases_ok'] for r in rows)}/"
                    f"{sum(r['gate_A_ledger']['cases_with_ledger'] for r in rows)}",
                "arms": len(rows),
                "arms_with_detection_power": sum(1 for r in rows
                                                 if r["gate_B_control"]["detection_power"]),
                "arms_with_dimension_control_moved": len(gB),
                "arms_where_field_moved": n_moved_arms,
                "moved_total": sum(r["moved"] for r in rows),
                "disagreements_total": sum(r["cross_run"]["disagreements"] for r in rows),
                "cross_run_common_total": sum(r["cross_run"]["common_values"] for r in rows),
                "cross_run_agreement_min": (min(agr) if agr else None),
                "sem_checked_total": sem_total,
                "sem_correct_total": sem_correct,
                "sem_buckets_total": dict(sum(
                    (collections.Counter(r["gate_C_semantics"]["buckets"]) for r in rows),
                    collections.Counter())),
                "outcome_totals_run1": dict(sum(
                    (collections.Counter(r["outcomes_run1"]) for r in rows),
                    collections.Counter())),
                "distinct_valid_payloads_max": max((r["distinct_valid_payloads"]
                                                    for r in rows), default=0),
                "arms_passing_repro_gate": len(repro_arms),
                "clean_quiet_runs": clean_runs,
            },
            "gates": {"A": bool(gA), "B": bool(gB), "C": bool(gC),
                      "D": False, "E": bool(len(clean_runs) >= 2 and repro_arms)},
            "dimension": CA.DIMENSION.get(key, ""),
            "arms": [f"{key}@{a}" for a in armlist],
            "note": "",
        }

    p = os.path.join(HERE, "analysis", "field_verdicts.json")
    with open(p, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)
    print("wrote", p)
    for k, v in sorted(out["fields"].items()):
        c = v["counts"]
        print(f"  {k:22s} {v['label']:18s} "
              f"geom={v['axes']['encoding_geometry']:26s} live={v['axes']['liveness']:20s} "
              f"sem={v['axes']['semantics']:12s} repro={v['axes']['reproducibility']}")
        print(f"      arms={c['arms']} moved_arms={c['arms_where_field_moved']} "
              f"moved={c['moved_total']} disagree={c['disagreements_total']} "
              f"common={c['cross_run_common_total']} ledger={c['ledger_cases_ok_over_checked']} "
              f"distinct_bytes={c['distinct_bytes']} sem={c['sem_correct_total']}/{c['sem_checked_total']}")


if __name__ == "__main__":
    main()
