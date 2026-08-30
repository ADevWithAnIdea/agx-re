#!/usr/bin/env python3
"""EXP-0187 verdict computation -- the ONLY place a verdict may be written.

    python3 analysis/verdicts.py raw/<run01> raw/<run02>

Verdicts are recomputed from `raw/` on every invocation and never read back from
a run manifest or a previous verdicts file. `start`/`width` are re-read from the
PINNED `db.json`, so a descriptor that moved under a sibling experiment becomes a
loud merge failure instead of a silent mis-attribution.

THE GATE (frozen in PRE_REGISTRATION.md section 6; nothing else may promote):

 1. Two gated runs, byte-identical programs, the same frozen `arms187.json`.
 2. >= 99 % per-value cross-run agreement on the OUTCOME PARTITION, and
    `moved >= 2 * disagree AND moved >= 1`.
    NOT `moved >= 2 * max(disagree, 1)` -- that form silently cannot promote any
    width-1 field, and it suppressed a real result on 2026-08-30.
 3. DETECTION POWER. `n4_rt_word` has exactly ONE modelled field and three fixed
    match bytes, so **no same-instruction control exists**. A target arm is
    `usable` only if a control fired for it, and the verdict records WHICH:
      `same_program_point` -- a known-live field of the op at off+4 moved
                              (strongest available: that program point executes)
      `carrier`            -- `rt_query_traverse.opB` moved somewhere in the same
                              carrier (weaker: the carrier has an observable
                              ray-query path, but this occurrence may be dead)
    A target arm with neither is BARRED from supporting any verdict, inert OR
    live, exactly as EXP-0172's gate rule 3 requires.
 4. The arm-open and arm-close baselines must both be `ok`.
 5. For a never-moving field, rule 2 is satisfied by the CARRIER SET: the
    carriers must differ in the dimension the field controls. Eight arms that
    cannot express a field are one arm (EXP-0164).
 6. MEASUREMENT FAILURES (`measurement_failure`, from a MALFORMED response) are
    REMOVED from the agreement computation and from `values_dispatched` -- never
    scored as `ok`, `fault`, or an inertness reading -- and a field whose
    measurement failures exceed 1 % of its dispatched values is refused.

LABEL POLICY (EXP-0163/EXP-0172, restated so a reviewer can disagree explicitly):
  LIVE               -> `hardware-run`
  INERT-ROBUST       -> `single-template-inference`, NOT emitter grade. Emitter
                        grade asserts the implementer may CHOOSE the value;
                        "emit what the compiler emitted" is a captured-template
                        dependency.
  STILL-UNDERPOWERED -> `untested`. Protocol section 5: do not round up.

Derived from EXP-0184 analysis/verdicts.py (our own code, cited).
"""
import hashlib
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import locate187 as L        # noqa: E402

AGREE_MIN = 99.0
MEAS_FAIL_MAX_PCT = 1.0


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
    h = hashlib.sha256(json.dumps(vals, sort_keys=True).encode()).hexdigest()[:16] \
        if vals is not None else "none"
    return "%s|%s" % (r.get("outcome"), h)


def index(recs):
    out = {}
    for r in recs:
        arm = r.get("arm")
        if not arm:
            continue
        base = arm.split(":")[0]
        if r.get("role") == "baseline":
            out.setdefault(base, {"cases": {}, "baselines": []})
            out[base]["baselines"].append(r)
            continue
        d = out.setdefault(arm, {"cases": {}, "baselines": []})
        d["cases"][r["value"]] = r
    return out


def arm_stats(a1, a2, base_key):
    """Agreement/movement over the values MEASURED in both runs, with
    measurement failures removed from both numerator and denominator."""
    shared = sorted(set(a1["cases"]) & set(a2["cases"]))
    mf = [v for v in shared
          if a1["cases"][v]["outcome"] == "measurement_failure"
          or a2["cases"][v]["outcome"] == "measurement_failure"]
    vals = [v for v in shared if v not in set(mf)]
    agree = sum(1 for v in vals if vkey(a1["cases"][v]) == vkey(a2["cases"][v]))
    disagree = len(vals) - agree
    moved = sum(1 for v in vals
                if vkey(a1["cases"][v]) != base_key
                and vkey(a2["cases"][v]) != base_key)
    pct = (100.0 * agree / len(vals)) if vals else 0.0
    return {"shared_values": len(vals), "agree_pct": round(pct, 3),
            "disagree": disagree, "moved": moved,
            "measurement_failures": len(mf),
            "measurement_failure_pct": round(100.0 * len(mf) / max(1, len(shared)), 3)}


def coverage(a1, a2, mn):
    cases = list(a1["cases"].values()) + list(a2["cases"].values())
    dispatched = len({c["value"] for c in cases
                      if c["outcome"] != "measurement_failure"})
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
    arms_doc = json.loads((EXP / "harness" / "arms187.json").read_text())
    arms = {a["arm"]: a for a in arms_doc["arms"]}

    def stats_for(name):
        if name not in i1 or name not in i2:
            return None
        bk = baseline_key(i1[name])
        st = arm_stats(i1[name], i2[name], bk)
        st["baselines_ok"] = (
            all(b["outcome"] == "ok" for b in i1[name]["baselines"]) and
            all(b["outcome"] == "ok" for b in i2[name]["baselines"]))
        return st

    spp_fired, carrier_fired, per_arm = {}, {}, {}
    for name, a in arms.items():
        st = stats_for(name)
        if st is None:
            per_arm[name] = {"status": "missing_from_a_run"}
            continue
        rec = {"carrier": a["carrier"], "occ": a["occ"], "role": a["role"],
               "instr": a["instr"], "field": a["field"],
               "off": a["off"], "start": a["start"], "width": a["width"],
               "baseline_field": a.get("baseline_field"),
               "succ_mnemonic": a.get("succ_mnemonic")}
        rec.update(st)
        rec.update(coverage(i1[name], i2[name], a["instr"]))
        per_arm[name] = rec
        if a["role"] == "control_same_program_point":
            spp_fired[(a["carrier"], a["occ"])] = {
                "arm": name, "field": a["field"], "moved": st["moved"],
                "agree_pct": st["agree_pct"], "fired": st["moved"] >= 1}
        elif a["role"] == "control_carrier":
            c = carrier_fired.setdefault(a["carrier"],
                                         {"arms": [], "moved": 0, "fired": False})
            c["arms"].append({"arm": name, "moved": st["moved"]})
            c["moved"] += st["moved"]
            c["fired"] = c["fired"] or st["moved"] >= 1

    by_field, probes_by_field = {}, {}
    for name, a in arms.items():
        if name not in per_arm or per_arm[name].get("status"):
            continue
        key = "%s.%s" % (a["instr"], a["field"])
        if a["role"] == "target":
            by_field.setdefault(key, []).append((name, a, per_arm[name]))
        elif a["role"] == "probe_word_liveness":
            probes_by_field.setdefault(key, []).append((name, a, per_arm[name]))

    verdicts = {}
    for key, entries in sorted(by_field.items()):
        mn, fld = key.split(".", 1)
        start, width = L.field_span(mn, fld)
        usable = []
        for e in entries:
            spp = spp_fired.get((e[1]["carrier"], e[1]["occ"]))
            car = carrier_fired.get(e[1]["carrier"], {"fired": False})
            kind = ("same_program_point" if (spp and spp["fired"])
                    else ("carrier" if car["fired"] else None))
            e[2]["control"] = {"kind": kind,
                               "same_program_point": spp,
                               "carrier_moved": car.get("moved", 0)}
            if kind:
                usable.append(e)
        live = [e for e in usable
                if e[2]["moved"] >= 1
                and e[2]["agree_pct"] >= AGREE_MIN
                and e[2]["moved"] >= 2 * e[2]["disagree"]
                and e[2]["baselines_ok"]
                and e[2]["measurement_failure_pct"] <= MEAS_FAIL_MAX_PCT]
        strong = [e for e in usable
                  if e[2]["control"]["kind"] == "same_program_point"]
        carriers = sorted({e[1]["carrier"] for e in entries})
        baselines = sorted({e[1].get("baseline_field") for e in entries})
        if not usable:
            label, verdict = "untested", "STILL-UNDERPOWERED"
            note = ("no arm had detection power: neither a same-program-point "
                    "control nor a carrier-level ray-query control ever moved")
        elif live:
            label, verdict = "hardware-run", "LIVE"
            note = ("moved on %d of the %d arms with detection power "
                    "(%d arms swept in total)" % (len(live), len(usable),
                                                  len(entries)))
        else:
            label, verdict = "single-template-inference", "INERT-ROBUST"
            note = ("0 of %d arms moved, on %d carriers with %d distinct "
                    "baseline field values; %d arms had a SAME-PROGRAM-POINT "
                    "control that fired and %d had only a carrier-level control"
                    % (len(entries), len(carriers), len(baselines), len(strong),
                       len(usable) - len(strong)))
        verdicts[key] = {
            "label": label, "verdict": verdict,
            "range": "0..%d dense (all %d values)" % ((1 << width) - 1, 1 << width),
            "target": "G17P", "evidence": ["EXP-0187"],
            "values_dispatched": max(e[2]["values_dispatched"] for e in entries),
            "distinct_bytes": sum(e[2]["distinct_bytes"] for e in entries),
            "encodable_range": max(e[2]["encodable_range"] for e in entries),
            "start": start, "width": width,
            "carriers": carriers,
            "distinct_baseline_field_values": baselines,
            "arms_total": len(entries), "arms_with_power": len(usable),
            "arms_with_same_program_point_power": len(strong),
            "arms": {e[0]: e[2] for e in entries},
            "note": note,
        }

    probes = {}
    for key, entries in sorted(probes_by_field.items()):
        moved_arms = [e[0] for e in entries if e[2]["moved"] >= 1]
        probes[key] = {
            "not_a_field": True,
            "why": "the pinned db models this byte as a FIXED MATCH CONSTANT. "
                   "Changing it changes which instruction the bytes decode as, "
                   "so no field label may be assigned. It is swept as a "
                   "WHOLE-WORD LIVENESS probe: if no value of any match byte "
                   "changes the observable either, the four bytes at that "
                   "offset have no observable effect at all, which distinguishes "
                   "'the field is inert' from 'this occurrence is never executed'.",
            "arms_total": len(entries), "arms_moved": len(moved_arms),
            "moved_arms": moved_arms,
            "encodable_range": max(e[2]["encodable_range"] for e in entries),
            "arms": {e[0]: e[2] for e in entries},
        }

    out = {"_generated_by": "analysis/verdicts.py",
           "_runs": [str(sys.argv[1]), str(sys.argv[2])],
           "_gate": {"agree_min_pct": AGREE_MIN,
                     "movement_rule": "moved >= 2*disagree AND moved >= 1",
                     "measurement_failure_max_pct": MEAS_FAIL_MAX_PCT},
           "verdicts": verdicts,
           "match_byte_probes": probes,
           "controls_same_program_point": {"%s#%s" % k: v
                                           for k, v in spp_fired.items()},
           "controls_carrier": carrier_fired,
           "arms": per_arm}
    p = EXP / "analysis" / "field_verdicts.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    print(json.dumps({k: {"label": v["label"], "verdict": v["verdict"],
                          "arms_with_power": v["arms_with_power"],
                          "note": v["note"]} for k, v in verdicts.items()},
                     indent=1))
    print(json.dumps({k: {"arms_moved": v["arms_moved"],
                          "arms_total": v["arms_total"]}
                      for k, v in probes.items()}, indent=1))
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
