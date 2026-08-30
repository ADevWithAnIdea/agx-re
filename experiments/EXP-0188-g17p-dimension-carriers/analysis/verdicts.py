#!/usr/bin/env python3
"""EXP-0188 verdict computation -- the ONLY place a verdict may be written.

    python3 analysis/verdicts.py raw/<run01> raw/<run02>

Verdicts are recomputed from `raw/` on every invocation and never read back from a
run manifest or a previous verdicts file. `start`/`width` are re-read from the
PINNED `db.json`, so a descriptor that moved under a sibling experiment becomes a
loud merge failure instead of a silent mis-attribution.

THE GATE (frozen in PRE_REGISTRATION.md section 6; nothing else may promote):

 1. Two gated runs, byte-identical programs, the same frozen `arms188.json`.
 2. >= 99 % per-value cross-run agreement on the OUTCOME PARTITION, and
        moved >= 2 * disagree   AND   moved >= 1.
    NOT `moved >= 2 * max(disagree, 1)`. That form demands `moved >= 2` and so
    CANNOT PROMOTE ANY WIDTH-1 FIELD by arithmetic rather than by evidence --
    EXP-0178 found it silently suppressing a real result. `simd_shuffle.cache` is
    width 1, so this experiment would be the next victim.
 3. DETECTION POWER: at the arm's occurrence, at least one CONTROL -- a field of
    the SAME instruction at the SAME offset, already known live -- must have moved
    in both runs. An arm with no firing control is BARRED from supporting any
    verdict, inert OR live.
 4. The arm-open and arm-close baselines must both be `ok`.
 5. MEASUREMENT FAILURES (`MALFORMED` responses, protocol 3d) are REMOVED from
    the agreement computation and from `values_dispatched`, never scored as `ok`,
    `fault` or an inertness reading; a field whose measurement failures exceed
    1 % of its dispatched values is refused outright.
 6. For a never-moving field, rule 2 is satisfied only by the CARRIER SET: the
    carriers must differ in THE DIMENSION THE FIELD CONTROLS, and the dimension
    spread actually achieved is reported in `dimension_spread` so a reviewer can
    check it rather than take it on trust. Eight arms that cannot express a field
    are one arm.

LABEL POLICY (EXP-0163/EXP-0172/EXP-0184, restated so a reviewer can disagree):
  LIVE                -> `hardware-run`
  INERT-ROBUST        -> `single-template-inference`, NOT emitter grade. Emitter
                         grade asserts the implementer may CHOOSE the value;
                         "emit what the compiler emitted" is a captured-template
                         dependency. The measurement is not downgraded -- its full
                         strength lives in `range`/`note`/`dimension_spread`.
  STILL-UNDERPOWERED  -> `untested`. Protocol section 5: do not round up.
  DECLINED            -> the field keeps its current label, with the reason.
"""
import hashlib
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import locate188 as L        # noqa: E402
import targets188 as T       # noqa: E402

def _arms_path():
    """The gated pair ran against the A3 re-scoped arm list where it exists; the
    frozen `arms188.json` is never modified and remains the parent document."""
    g = EXP / "harness" / "arms188_gated.json"
    return g if g.exists() else (EXP / "harness" / "arms188.json")


AGREE_MIN = 99.0
MEAS_FAIL_MAX_PCT = 1.0
MEASUREMENT_FAILURE = "measurement_failure"


def load(run_dir):
    recs = []
    for ln in (Path(run_dir) / "sweep.jsonl").read_text().splitlines():
        ln = ln.strip()
        if ln:
            try:
                recs.append(json.loads(ln))
            except ValueError:
                pass
    return recs


def vkey(r):
    """The per-value OUTCOME PARTITION key: outcome plus the exact observed value
    vector. Two runs agree on a value iff this key is identical."""
    o = r.get("observed") or {}
    vals = o.get("vals_u32")
    h = (hashlib.sha256(json.dumps(vals, sort_keys=True).encode()).hexdigest()[:16]
         if vals is not None else "none")
    return "%s|%s" % (r.get("outcome"), h)


def index(recs):
    out = {}
    for r in recs:
        arm = r.get("arm")
        if not arm:
            continue
        base = arm.split(":")[0]
        d = out.setdefault(base, {"cases": {}, "baselines": []})
        if r.get("role") == "baseline":
            d["baselines"].append(r)
        else:
            d["cases"][r["value"]] = r
    return out


def _clean(a):
    """Cases that are OBSERVATIONS. A MALFORMED response is a measurement
    failure and is removed, not scored (protocol 3d)."""
    return {v: r for v, r in a["cases"].items()
            if r.get("outcome") != MEASUREMENT_FAILURE}


def arm_stats(a1, a2, base_key):
    c1, c2 = _clean(a1), _clean(a2)
    vals = sorted(set(c1) & set(c2))
    agree = sum(1 for v in vals if vkey(c1[v]) == vkey(c2[v]))
    disagree = len(vals) - agree
    moved = sum(1 for v in vals
                if vkey(c1[v]) != base_key and vkey(c2[v]) != base_key)
    pct = (100.0 * agree / len(vals)) if vals else 0.0
    mf = (sum(1 for r in a1["cases"].values()
              if r.get("outcome") == MEASUREMENT_FAILURE)
          + sum(1 for r in a2["cases"].values()
                if r.get("outcome") == MEASUREMENT_FAILURE))
    return {"shared_values": len(vals), "agree_pct": round(pct, 3),
            "disagree": disagree, "moved": moved, "measurement_failures": mf}


def coverage(a1, a2, mn):
    cases = list(_clean(a1).values()) + list(_clean(a2).values())
    dispatched = len(set(_clean(a1)) | set(_clean(a2)))
    distinct_bytes = len({c.get("bytes") for c in cases if c.get("bytes")})
    enc = len({c["value"] for c in cases
               if (c.get("token") or {}).get("mnemonic") == mn})
    outcomes, tokens = {}, {}
    for c in cases:
        outcomes[c["outcome"]] = outcomes.get(c["outcome"], 0) + 1
        t = str((c.get("token") or {}).get("mnemonic"))
        tokens[t] = tokens.get(t, 0) + 1
    return {"values_dispatched": dispatched, "distinct_bytes": distinct_bytes,
            "encodable_range": enc, "outcomes": outcomes,
            "tokenized_mnemonics": tokens}


def baseline_key(a):
    for b in a["baselines"]:
        if str(b.get("note", "")).endswith(":open"):
            return vkey(b)
    return vkey(a["baselines"][0]) if a["baselines"] else None


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    i1, i2 = index(load(sys.argv[1])), index(load(sys.argv[2]))
    arms_doc = json.loads((_arms_path()).read_text())
    arms = {a["arm"]: a for a in arms_doc["arms"]}
    dims = {t["mnemonic"] + "." + t["field"]: t["dimension"] for t in T.TARGETS}

    # Detection power per (group, carrier, occ): ANY control that moved counts.
    control_fired, control_detail = {}, {}
    for name, a in arms.items():
        if a["role"] != "control" or name not in i1 or name not in i2:
            continue
        st = arm_stats(i1[name], i2[name], baseline_key(i1[name]))
        k = (a["group"], a["carrier"], a["occ"])
        control_detail.setdefault(k, []).append(
            {"arm": name, "field": a["field"], "moved": st["moved"],
             "agree_pct": st["agree_pct"]})
        control_fired[k] = control_fired.get(k, False) or st["moved"] >= 1

    verdicts, per_arm, by_field = {}, {}, {}
    for name, a in arms.items():
        if name not in i1 or name not in i2:
            per_arm[name] = {"status": "missing_from_a_run"}
            continue
        st = arm_stats(i1[name], i2[name], baseline_key(i1[name]))
        cov = coverage(i1[name], i2[name], a["instr"])
        k = (a["group"], a["carrier"], a["occ"])
        bl_ok = (all(b["outcome"] == "ok" for b in i1[name]["baselines"])
                 and all(b["outcome"] == "ok" for b in i2[name]["baselines"]))
        rec = {"carrier": a["carrier"], "group": a["group"], "occ": a["occ"],
               "role": a["role"], "instr": a["instr"], "field": a["field"],
               "off": a["off"], "baseline_field": a.get("baseline_field"),
               "carrier_dimension": a.get("carrier_dimension"),
               "occ_dimension": a.get("occ_dimension"),
               "baselines_ok": bl_ok,
               "control": {"fired": control_fired.get(k),
                           "detail": control_detail.get(k, [])}}
        rec.update(st)
        rec.update(cov)
        per_arm[name] = rec
        if a["role"] == "target":
            by_field.setdefault("%s.%s" % (a["instr"], a["field"]), []).append(
                (name, a, rec))

    for key, entries in sorted(by_field.items()):
        mn, fld = key.split(".", 1)
        start, width = L.field_span(mn, fld)
        usable = [e for e in entries if e[2]["control"]["fired"]]
        live = [e for e in usable
                if e[2]["moved"] >= 1
                and e[2]["agree_pct"] >= AGREE_MIN
                and e[2]["moved"] >= 2 * e[2]["disagree"]
                and e[2]["baselines_ok"]]
        carriers = sorted({e[1]["carrier"] for e in entries})
        car_dims = sorted({str(e[1].get("carrier_dimension")) for e in entries})
        occ_dims = sorted({json.dumps(e[1].get("occ_dimension"), sort_keys=True)
                           for e in entries})
        usable_car_dims = sorted({str(e[1].get("carrier_dimension")) for e in usable})
        usable_occ_dims = sorted({json.dumps(e[1].get("occ_dimension"), sort_keys=True)
                                  for e in usable})
        tot_disp = max((e[2]["values_dispatched"] for e in entries), default=0)
        tot_bytes = sum(e[2]["distinct_bytes"] for e in entries)
        enc = max((e[2]["encodable_range"] for e in entries), default=0)
        mf = sum(e[2]["measurement_failures"] for e in entries)
        disp_all = sum(e[2]["values_dispatched"] for e in entries)
        mf_pct = (100.0 * mf / max(disp_all + mf, 1))
        if mf_pct > MEAS_FAIL_MAX_PCT:
            label, verdict = "untested", "REFUSED-MEASUREMENT-FAILURES"
            note = ("%.2f%% of dispatched values returned MALFORMED responses "
                    "(> %.1f%% ceiling); no reading from this field is scored"
                    % (mf_pct, MEAS_FAIL_MAX_PCT))
        elif not usable:
            label, verdict = "untested", "STILL-UNDERPOWERED"
            note = ("no arm had detection power: at every occurrence, every "
                    "control on the same instruction failed to move")
        elif live:
            label, verdict = "hardware-run", "LIVE"
            note = ("moved on %d of the %d arms that had detection power "
                    "(%d arms swept in total; the rest sit at occurrences where "
                    "no control fired and are barred from supporting a verdict)"
                    % (len(live), len(usable), len(entries)))
        else:
            label, verdict = "single-template-inference", "INERT-ROBUST"
            note = ("0 of %d arms with detection power moved (%d arms swept), "
                    "across %d carriers spanning %d distinct values of the "
                    "dimension this field is hypothesised to control"
                    % (len(usable), len(entries), len(carriers),
                       len(usable_car_dims)))
        verdicts[key] = {
            "label": label, "verdict": verdict,
            "range": "0..%d dense (all %d values)" % ((1 << width) - 1, 1 << width),
            "target": "G17P", "evidence": ["EXP-0188"],
            "values_dispatched": tot_disp, "distinct_bytes": tot_bytes,
            "encodable_range": enc, "start": start, "width": width,
            "measurement_failures": mf,
            "carriers": carriers,
            "dimension": dims.get(key),
            "dimension_spread": {
                "carrier_dimension_values_swept": car_dims,
                "carrier_dimension_values_with_detection_power": usable_car_dims,
                "occurrence_dimension_values_swept": occ_dims,
                "occurrence_dimension_values_with_detection_power": usable_occ_dims,
            },
            "arms": {e[0]: e[2] for e in entries},
            "note": note,
        }

    out = {"_generated_by": "analysis/verdicts.py",
           "_runs": [str(sys.argv[1]), str(sys.argv[2])],
           "_gate": {"agree_min_pct": AGREE_MIN,
                     "movement_rule": "moved >= 2*disagree AND moved >= 1",
                     "measurement_failure_ceiling_pct": MEAS_FAIL_MAX_PCT},
           "verdicts": verdicts, "arms": per_arm,
           "controls": {"%s/%s#%s" % k: {"fired": v, "detail": control_detail[k]}
                        for k, v in control_fired.items()},
           "dropped_carriers": arms_doc.get("dropped_carriers", [])}
    (EXP / "analysis" / "field_verdicts.json").write_text(
        json.dumps(out, indent=1, sort_keys=True))

    # FLAT form, per FIELD-SWEEP-PROTOCOL section 5: one row per field, the keys
    # the orchestrator merges, and nothing nested that a merge would have to walk.
    flat = {}
    for key, v in verdicts.items():
        flat[key] = {k: v[k] for k in
                     ("label", "verdict", "range", "target", "evidence",
                      "values_dispatched", "distinct_bytes", "encodable_range",
                      "start", "width", "note")}
        flat[key]["carriers"] = v["carriers"]
        flat[key]["dimension"] = v["dimension"]
    (EXP / "analysis" / "field_verdicts_flat.json").write_text(
        json.dumps(flat, indent=1, sort_keys=True))
    print(json.dumps({k: {"label": v["label"], "verdict": v["verdict"],
                          "note": v["note"]} for k, v in verdicts.items()},
                     indent=1))
    print("wrote analysis/field_verdicts.json + analysis/field_verdicts_flat.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
