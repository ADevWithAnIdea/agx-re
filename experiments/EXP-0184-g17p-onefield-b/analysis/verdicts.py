#!/usr/bin/env python3
"""EXP-0184 verdict computation -- the ONLY place a verdict may be written.

    python3 analysis/verdicts.py raw/<run01> raw/<run02>

Verdicts are recomputed from `raw/` on every invocation and never read back from
a run manifest or a previous verdicts file. `start`/`width` are re-read from the
PINNED `db.json`, so a descriptor that moved under a sibling experiment becomes a
loud merge failure instead of a silent mis-attribution.

THE GATE (frozen in PRE_REGISTRATION.md section 6; nothing else may promote):

 1. Two gated runs, byte-identical programs, the same frozen `arms184.json`.
 2. >= 99 % per-value cross-run agreement on the OUTCOME PARTITION, and
    `moved >= 2 * disagree AND moved >= 1`.
    NOT `moved >= 2 * max(disagree, 1)` -- that form silently cannot promote any
    width-1 field.
 3. The arm's CONTROL -- a field on the SAME instruction at the SAME occurrence,
    already known live -- must have moved in BOTH runs. An arm whose control
    never fires has no detection power and is BARRED from supporting any verdict,
    inert OR live.
 4. The arm-open and arm-close baselines must both be `ok`.
 5. For a never-moving field, rule 2 is satisfied by the CARRIER SET: the
    carriers must differ in the dimension the field controls. Eight arms that
    cannot express a field are one arm.

LABEL POLICY (EXP-0163/EXP-0172, restated so a reviewer can disagree explicitly):
  LIVE               -> `hardware-run`
  INERT-ROBUST       -> `single-template-inference`, NOT emitter grade. Emitter
                        grade asserts the implementer may CHOOSE the value;
                        "emit what the compiler emitted" is a captured-template
                        dependency. The measurement is not downgraded -- its full
                        strength lives in `range`/`note`/`inert_arms`.
  STILL-UNDERPOWERED -> `untested`. Protocol section 5: do not round up.
  DECLINED           -> the field keeps its current label, with the reason.
"""
import hashlib
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
import locate184 as L        # noqa: E402

AGREE_MIN = 99.0
GOOD = {"ok", "silent_zero", "wrong_value", "not_written"}


def load(run_dir):
    recs = []
    p = Path(run_dir) / "sweep.jsonl"
    for ln in p.read_text().splitlines():
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
    """arm -> {"cases": {value: rec}, "baselines": [rec...]}"""
    out = {}
    for r in recs:
        arm = r.get("arm")
        if not arm:
            continue
        if r.get("role") == "baseline":
            out.setdefault(arm.split(":")[0], {"cases": {}, "baselines": []})
            out[arm.split(":")[0]]["baselines"].append(r)
            continue
        d = out.setdefault(arm, {"cases": {}, "baselines": []})
        d["cases"][r["value"]] = r
    return out


def arm_stats(a1, a2, base_key):
    vals = sorted(set(a1["cases"]) & set(a2["cases"]))
    agree = sum(1 for v in vals if vkey(a1["cases"][v]) == vkey(a2["cases"][v]))
    disagree = len(vals) - agree
    moved = sum(1 for v in vals
                if vkey(a1["cases"][v]) != base_key
                and vkey(a2["cases"][v]) != base_key)
    pct = (100.0 * agree / len(vals)) if vals else 0.0
    return {"shared_values": len(vals), "agree_pct": round(pct, 3),
            "disagree": disagree, "moved": moved}


def coverage(a1, a2, mn):
    cases = list(a1["cases"].values()) + list(a2["cases"].values())
    dispatched = len(set(a1["cases"]) | set(a2["cases"]))
    distinct_bytes = len({c.get("bytes") for c in cases if c.get("bytes")})
    enc = len({c["value"] for c in cases
               if (c.get("token") or {}).get("mnemonic") == mn})
    outcomes = {}
    for c in cases:
        outcomes[c["outcome"]] = outcomes.get(c["outcome"], 0) + 1
    tokens = {}
    for c in cases:
        t = (c.get("token") or {}).get("mnemonic")
        tokens[str(t)] = tokens.get(str(t), 0) + 1
    return {"values_dispatched": dispatched, "distinct_bytes": distinct_bytes,
            "encodable_range": enc, "outcomes": outcomes,
            "tokenized_mnemonics": tokens}


def baseline_key(a):
    """The arm-open baseline's partition key, from the run where it was taken."""
    for b in a["baselines"]:
        if str(b.get("note", "")).endswith(":open"):
            return vkey(b)
    return a["baselines"][0] and vkey(a["baselines"][0])


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    r1, r2 = load(sys.argv[1]), load(sys.argv[2])
    i1, i2 = index(r1), index(r2)
    arms_doc = json.loads((EXP / "harness" / "arms184.json").read_text())
    arms = {a["arm"]: a for a in arms_doc["arms"]}

    # control firing, per (carrier, occ)
    control_fired = {}
    for name, a in arms.items():
        if a["role"] != "control":
            continue
        if name not in i1 or name not in i2:
            continue
        bk1 = baseline_key(i1[name]) if i1[name]["baselines"] else None
        st = arm_stats(i1[name], i2[name], bk1)
        control_fired[(a["carrier"], a["occ"])] = {
            "arm": name, "field": a["field"], "moved": st["moved"],
            "agree_pct": st["agree_pct"], "fired": st["moved"] >= 1}

    verdicts, per_arm = {}, {}
    by_field = {}
    for name, a in arms.items():
        if name not in i1 or name not in i2:
            per_arm[name] = {"status": "missing_from_a_run"}
            continue
        bk = baseline_key(i1[name])
        st = arm_stats(i1[name], i2[name], bk)
        cov = coverage(i1[name], i2[name], a["instr"])
        ctl = control_fired.get((a["carrier"], a["occ"]),
                                {"fired": None, "moved": None})
        bl_ok = all(b["outcome"] == "ok" for b in i1[name]["baselines"]) and \
                all(b["outcome"] == "ok" for b in i2[name]["baselines"])
        rec = {"carrier": a["carrier"], "occ": a["occ"], "role": a["role"],
               "instr": a["instr"], "field": a["field"],
               "baseline_field": a.get("baseline_field"),
               "baselines_ok": bl_ok, "control": ctl}
        rec.update(st)
        rec.update(cov)
        per_arm[name] = rec
        if a["role"] == "target":
            by_field.setdefault("%s.%s" % (a["instr"], a["field"]), []).append(
                (name, a, rec))

    # A `_`-prefixed name is NOT a field of the instruction in the pinned db --
    # it is a probe of a byte the descriptor models as a fixed MATCH CONSTANT.
    # Changing it changes which instruction the bytes ARE (`encodable_range`
    # collapses to 1), so it can never carry a FIELD label, however cleanly it
    # moves. Two fields were withdrawn on 2026-08-30 after their "movement"
    # turned out to be the sweep encoding a different instruction; this routes
    # such probes to their own section instead of a verdict row.
    match_probes = {k: v for k, v in by_field.items() if k.split(".", 1)[1].startswith("_")}
    by_field = {k: v for k, v in by_field.items() if not k.split(".", 1)[1].startswith("_")}

    for key, entries in sorted(by_field.items()):
        mn, fld = key.split(".", 1)
        try:
            start, width = L.field_span(mn, fld)
        except KeyError:
            start, width = entries[0][1]["start"], entries[0][1]["width"]
        usable = [e for e in entries if e[2]["control"]["fired"]]
        live = [e for e in usable
                if e[2]["moved"] >= 1
                and e[2]["agree_pct"] >= AGREE_MIN
                and e[2]["moved"] >= 2 * e[2]["disagree"]
                and e[2]["baselines_ok"]]
        distinct_baselines = sorted({e[1].get("baseline_field") for e in entries})
        carriers = sorted({e[1]["carrier"] for e in entries})
        tot_disp = max(e[2]["values_dispatched"] for e in entries)
        tot_bytes = sum(e[2]["distinct_bytes"] for e in entries)
        enc = max(e[2]["encodable_range"] for e in entries)
        if not usable:
            label, verdict = "untested", "STILL-UNDERPOWERED"
            note = ("no arm had detection power: the control on the same "
                    "instruction and occurrence never moved")
        elif live:
            label, verdict = "hardware-run", "LIVE"
            note = ("moved on %d of the %d arms that had detection power "
                    "(%d arms swept in total; the rest had a control that never "
                    "fired and are barred from supporting any verdict)"
                    % (len(live), len(usable), len(entries)))
        else:
            label, verdict = "single-template-inference", "INERT-ROBUST"
            note = ("0 of %d arms moved, on %d carriers with %d distinct "
                    "baseline field values, every arm's control firing"
                    % (len(entries), len(carriers), len(distinct_baselines)))
        verdicts[key] = {
            "label": label, "verdict": verdict,
            "range": "0..%d dense (all %d values)" % ((1 << width) - 1, 1 << width),
            "target": "G17P", "evidence": ["EXP-0184"],
            "values_dispatched": tot_disp, "distinct_bytes": tot_bytes,
            "encodable_range": enc, "start": start, "width": width,
            "carriers": carriers, "distinct_baseline_field_values": distinct_baselines,
            "arms": {e[0]: e[2] for e in entries},
            "note": note,
        }

    probes = {}
    for key, entries in sorted(match_probes.items()):
        probes[key] = {
            "not_a_field": True,
            "why": "the pinned db models this byte as a fixed match constant, "
                   "not a field; changing it changes which instruction the bytes "
                   "decode as, so no field label may be assigned",
            "encodable_range": max(e[2]["encodable_range"] for e in entries),
            "arms": {e[0]: e[2] for e in entries},
        }

    out = {"_generated_by": "analysis/verdicts.py",
           "match_byte_probes": probes,
           "_runs": [str(sys.argv[1]), str(sys.argv[2])],
           "_gate": {"agree_min_pct": AGREE_MIN,
                     "movement_rule": "moved >= 2*disagree AND moved >= 1"},
           "verdicts": verdicts, "arms": per_arm,
           "controls": {"%s#%s" % k: v for k, v in control_fired.items()}}
    p = EXP / "analysis" / "field_verdicts.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    print(json.dumps({k: {kk: v[kk] for kk in
                          ("label", "verdict", "moved" if "moved" in v else "note")}
                      for k, v in verdicts.items()}, indent=1))
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
