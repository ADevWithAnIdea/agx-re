#!/usr/bin/env python3
"""verdicts.py -- EXP-0204 verdicts, recomputed FROM raw/ only.

Never from a run manifest, never from memory of what was run.  Reads every
`raw/g17p_*/sweep.jsonl`, re-derives the counts, applies the gate frozen in
PRE_REGISTRATION sec.8, and writes analysis/field_verdicts.json.

THE GATE (frozen; do not edit without a new pre-registration)
  1. >= 2 gated runs on the same arm;
  2. >= 99 % per-value cross-run agreement over values valid in BOTH runs
     (foreign / InnocentVictim segregated; both figures reported);
  3. moved >= 2*disagree  AND  moved > 0
     -- written LITERALLY.  NOT `moved >= 2*max(disagree,1)`, which cannot
     promote any width-1 field and silently suppressed `read_en` in EXP-0178
     (FIELD-SWEEP-PROTOCOL sec.5b).  `selftest()` proves this form promotes a
     1-bit field with 1 moved value and 0 disagreements, and refuses a field
     with 0 moved;
  4. the arm has detection power AND a moved control in the field's OWN
     dimension (sec.9 rule 1);
  5. V (distinct VALID observed payloads) >= 2 -- a field whose every legal value
     produced one payload ran legally and was INDISTINGUISHABLE (wave_audit's
     Case-C test);
  6. for tex_deriv.dstsrc only: both runs measured QUIET.

`moved` counts ONLY status-OK, same-mnemonic, non-hard outcomes.  A GPU fault is
not movement, and neither is our own disassembler failing to decode -- both were
found being counted as movement in this corpus this week.
"""
import collections, json, os, sys, glob

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "harness"))
sys.path.insert(0, os.path.join(HERE, "pinned"))
import carriers as CA                       # noqa: E402

HARD = {"fault", "hang", "undecodable", "malformed", "unreproduced", "not_run"}
CONTROL_FIELDS = {"_baseline", "_detect", "_detect_summary", "_baseline_recheck",
                  "_baseline_final", "_cascade_check", "_arm_not_run"}
AGREE_BAR = 99.0


def selftest():
    """This gate must be able to say NO.  Thirteen checks in this corpus could not."""
    def gate(moved, disagree):
        return moved >= 2 * disagree and moved > 0
    assert gate(1, 0), "width-1 trap: a 1-bit field with 1 moved / 0 disagree MUST pass"
    assert not gate(0, 0), "a field that never moved must NOT pass"
    assert not gate(1, 1), "moved must be >= 2x disagreements"
    assert gate(4, 2)
    return True


def load(run_dir):
    recs = []
    p = os.path.join(run_dir, "sweep.jsonl")
    if not os.path.exists(p):
        return recs
    for line in open(p, errors="replace"):
        try:
            recs.append(json.loads(line))
        except Exception:
            pass
    return recs


def quiet(run_dir):
    """Was the machine quiet for the whole run?  A MEASUREMENT, not a claim."""
    p = os.path.join(run_dir, "procs.jsonl")
    if not os.path.exists(p):
        return None, {"reason": "no procs.jsonl"}
    n, busy, worst, names = 0, 0, 0, collections.Counter()
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
                names[f["cmd"].split()[0][:60]] += 1
    return (busy == 0 and n > 0), {"samples": n, "busy_samples": busy,
                                   "max_foreign": worst,
                                   "foreign_cmds": dict(names.most_common(6))}


def main():
    selftest()
    runs = sorted(d for d in glob.glob(os.path.join(HERE, "raw", "g17p_*"))
                  if os.path.isdir(d))
    quietness = {os.path.basename(d): quiet(d) for d in runs}
    per = collections.defaultdict(lambda: collections.defaultdict(dict))
    detect = collections.defaultdict(dict)
    hard = collections.defaultdict(lambda: collections.Counter())
    bytes_seen = collections.defaultdict(set)
    oracles = collections.defaultdict(set)
    baseline_oracle = collections.defaultdict(dict)

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
                o = r.get("oracle") or {}
                baseline_oracle[arm][rid] = {"checked": o.get("checked"),
                                             "agree": o.get("agree"),
                                             "status": r["observed"].get("status")}
                continue
            if f in CONTROL_FIELDS:
                continue
            key = (r["instr"], f, arm)
            out = r.get("outcome")
            if r.get("bytes"):
                bytes_seen[key].add(r["bytes"])
            oracles[key].add(json.dumps(r.get("oracle"), sort_keys=True))
            if out in HARD or out == "foreign":
                hard[key][out] += 1
                continue
            per[key][rid][r["value"]] = json.dumps(r.get("observed", {}).get("hh"),
                                                  sort_keys=True)

    fields = {}
    arms_out = {}
    for (mnem, fname, arm), byrun in sorted(per.items()):
        rk = sorted(byrun)
        if len(rk) < 2:
            agree = None
            dis = common = 0
            moved = 0
        else:
            a, b = byrun[rk[0]], byrun[rk[1]]
            com = set(a) & set(b)
            disv = [v for v in com if a[v] != b[v]]
            common, dis = len(com), len(disv)
            agree = 100.0 * (1 - dis / max(common, 1))
        # movement = differs from the arm's own baseline observation, in BOTH runs
        base = {}
        for rid in rk:
            bl = [v for v in byrun[rid]]
            base[rid] = None
        moved_vals = []
        if len(rk) >= 2:
            a, b = byrun[rk[0]], byrun[rk[1]]
            # the baseline payload is the modal payload of the arm's own baseline
            # value; recovered from the arm spec
            bval = None
            for spec in _ARMS:
                if spec["id"] == arm:
                    bval = spec["baseline_fields"].get(fname)
            ba = a.get(bval)
            for v in sorted(set(a) & set(b)):
                if ba is not None and a[v] != ba and a[v] == b[v]:
                    moved_vals.append(v)
        moved = len(moved_vals)
        V = len(set(byrun[rk[0]].values())) if rk else 0
        key = f"{mnem}.{fname}"
        dm = detect.get(arm, {})
        dim_ok = all(bool((dm.get(r) or {}).get("dimension_controls_moved", {})
                          .get(key)) for r in rk) if rk else False
        pow_ok = all(bool((dm.get(r) or {}).get("detect_ok")) for r in rk) if rk else False
        arms_out[f"{key}@{arm}"] = {
            "runs": rk, "common_values": common, "disagreements": dis,
            "cross_run_agreement_pct": None if agree is None else round(agree, 2),
            "moved": moved, "moved_values_sample": moved_vals[:24],
            "distinct_valid_payloads": V,
            "distinct_encodings_dispatched": len(bytes_seen[(mnem, fname, arm)]),
            "distinct_oracles": len(oracles[(mnem, fname, arm)]),
            "hard_outcomes": dict(hard[(mnem, fname, arm)]),
            "detection_power": pow_ok,
            "dimension_control_moved": dim_ok,
            "dimension_controls": (dm.get(rk[0], {}) if rk else {})
                                  .get("dimension_controls_moved", {}).get(key, []),
            "baseline_host_oracle": baseline_oracle.get(arm, {}),
        }
        fields.setdefault(key, []).append(f"{key}@{arm}")
    return fields, arms_out, quietness, runs


_ARMS = []


def build():
    global _ARMS
    import arms as A
    _ARMS = A.ARMS
    fields, arms_out, quietness, runs = main()

    import isadb
    out = {
        "_experiment": "EXP-0204",
        "_target": "G17P (Apple A18 Pro, applegpu_g17p) -- DIRECT, not INFERRED",
        "_spec": "docs/evidence-classification.md sec.2 labels; "
                 "FIELD-SWEEP-PROTOCOL sec.5 shape; gate frozen in PRE_REGISTRATION sec.8",
        "_runs": [os.path.basename(r) for r in runs],
        "_machine_quiet": {k: {"quiet": v[0], **v[1]} for k, v in quietness.items()},
        "_gate_selftest": "passed: promotes (moved=1,disagree=0); refuses (moved=0); "
                          "refuses (moved=1,disagree=1)",
        "arms": arms_out,
        "fields": {},
    }
    for key, armids in sorted(fields.items()):
        mnem, fname = key.split(".", 1)
        desc = isadb._BY_MNEM[mnem]
        fd = next(f for f in desc["fields"] if f["name"] == fname)
        rows = [arms_out[a] for a in armids]
        quiet_all = all((quietness.get(r) or (None,))[0] for r in out["_runs"])
        # gate
        passing = []
        for a in armids:
            r = arms_out[a]
            ag = r["cross_run_agreement_pct"]
            if (len(r["runs"]) >= 2 and ag is not None and ag >= AGREE_BAR
                    and r["moved"] >= 2 * r["disagreements"] and r["moved"] > 0
                    and r["detection_power"] and r["dimension_control_moved"]
                    and r["distinct_valid_payloads"] >= 2):
                passing.append(a)
        needs_quiet = key in ("tex_deriv.dstsrc",)
        gate_ok = bool(passing) and (quiet_all or not needs_quiet)
        w = fd["width"]
        rng = (f"0..{(1 << w) - 1} dense (all {1 << w} values) x {len(armids)} arms"
               if w <= 8 else
               f"{max(r['common_values'] for r in rows)} sampled values of 2^{w} "
               f"(boundaries + powers of two + all-ones prefixes + 16 hashed interior) "
               f"x {len(armids)} arms")
        label = ("hardware-run" if gate_ok else
                 ("isolated-byte-diff"
                  if any(r["moved"] > 0 for r in rows) else "untested"))
        out["fields"][key] = {
            "label": label,
            "range": rng,
            "target": "G17P",
            "evidence": ["EXP-0204"],
            "start": fd["start"], "width": fd["width"],
            "arms": armids,
            "arms_passing_gate": passing,
            "n_arms": len(armids),
            "values_dispatched": max(r["common_values"] for r in rows),
            "distinct_bytes": max(r["distinct_encodings_dispatched"] for r in rows),
            "distinct_oracles": max(r["distinct_oracles"] for r in rows),
            "distinct_valid_payloads_max": max(r["distinct_valid_payloads"] for r in rows),
            "moved_max": max(r["moved"] for r in rows),
            "moved_total": sum(r["moved"] for r in rows),
            "disagreements_total": sum(r["disagreements"] for r in rows),
            "cross_run_agreement_min_pct": min(
                [r["cross_run_agreement_pct"] for r in rows
                 if r["cross_run_agreement_pct"] is not None] or [None]),
            "hard_outcomes_total": dict(sum(
                (collections.Counter(r["hard_outcomes"]) for r in rows),
                collections.Counter())),
            "arms_with_detection_power": sum(1 for r in rows if r["detection_power"]),
            "arms_with_dimension_control_moved":
                sum(1 for r in rows if r["dimension_control_moved"]),
            "dimension": CA.DIMENSION.get(key, ""),
            "machine_quiet_required": needs_quiet,
            "machine_quiet_observed": quiet_all,
            "note": "",
        }
    p = os.path.join(HERE, "analysis", "field_verdicts.json")
    with open(p, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print("wrote", p)
    for k, v in sorted(out["fields"].items()):
        print(f"  {k:24s} {v['label']:20s} moved_max={v['moved_max']:4d} "
              f"agree_min={v['cross_run_agreement_min_pct']} "
              f"V={v['distinct_valid_payloads_max']} arms={v['n_arms']} "
              f"pass={len(v['arms_passing_gate'])}")


if __name__ == "__main__":
    build()
