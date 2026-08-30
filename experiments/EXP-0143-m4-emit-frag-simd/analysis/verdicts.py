#!/usr/bin/env python3
"""verdicts.py -- EXP-0143 reduction: raw sweep -> analysis/field_verdicts.json.

    python3 analysis/verdicts.py <run01> [<run02>]

Applies the promotion rules FROZEN in PRE_REGISTRATION.md sec.10.  Nothing here
touches hardware; it is a pure function of raw/<run_id>/sweep.jsonl, so a
reviewer can re-derive every verdict from the committed evidence.

CLEAN-ROOM: analysis of our own captured observations only.
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))
sys.path.insert(0, os.path.abspath(os.path.join(EXP, "..", "..", "tools", "agx-isa")))
import casematrix as CM          # noqa: E402
import isadb                     # noqa: E402

# outcomes that say "the machine, not the field" -- excluded from the gate
NOISE = {"foreign", "unreproduced"}
# outcomes that count as this field's value MOVING the observation
MOVED = {"wrong_value", "silent_zero"}


def load(run_id):
    p = os.path.join(EXP, "raw", run_id, "sweep.jsonl")
    recs = []
    with open(p) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def index(recs):
    """(arm, field) -> {value: outcome}, plus arm-level bookkeeping."""
    byfield = defaultdict(dict)
    arm_live, arm_base, stopped = {}, {}, set()
    field_stopped = set()
    for r in recs:
        arm, fld = r["carrier"], r["field"]
        if fld == "_live_control":
            arm_live[arm] = bool(r["match"])
        elif fld == "_baseline":
            arm_base[arm] = (r["observed"].get("status") == "OK")
        elif fld in ("_baseline_recheck", "_baseline_final"):
            if not r["match"]:
                stopped.add(arm)
        elif not fld.startswith("_"):
            st = r["observed"].get("status")
            if r["value"] == -1 and st == "ARM_STOPPED":
                stopped.add(arm)
                continue
            if r["value"] == -1 and st == "FIELD_STOPPED":
                # sec.8 area stop: THIS field is partial, the arm continues.
                field_stopped.add((arm, fld))
                continue
            byfield[(arm, fld)][r["value"]] = r["outcome"]
    return byfield, arm_live, arm_base, stopped, field_stopped


def summarise(vals):
    h = defaultdict(int)
    for o in vals.values():
        h[o] += 1
    n_eff = sum(v for k, v in h.items() if k not in NOISE)
    moved = sum(v for k, v in h.items() if k in MOVED)
    return dict(h), n_eff, moved


def rng(mnem, fld, vals):
    desc = isadb._BY_MNEM[mnem]
    w = next(f["width"] for f in desc["fields"] if f["name"] == fld)
    full = 1 << w
    if len(vals) >= full:
        return f"0..{full - 1} dense (all {full} values)"
    return (f"{len(vals)} of {full} values: boundaries, all powers of two, "
            f"all 2^i-1, and 16 asymmetric interior samples")


def main():
    runs = sys.argv[1:]
    if not runs:
        sys.exit("usage: verdicts.py <run01> [<run02>]")
    primary = index(load(runs[0]))
    gate = index(load(runs[1])) if len(runs) > 1 else None

    byfield, arm_live, arm_base, stopped, field_stopped = primary
    # arm -> mnemonic
    arm_mnem = {a["id"]: a["mnemonic"] for a in CM.ARMS}
    # (mnemonic, field) -> list of arms that swept it
    groups = defaultdict(list)
    for (arm, fld) in byfield:
        groups[(arm_mnem[arm], fld)].append(arm)

    verdicts, defects, gate_report = {}, {}, {}

    # ---- pre-registered falsifiers must have fired -----------------------
    fals = {}
    for (arm, fld, v) in CM.FALSIFIERS:
        o = byfield.get((arm, fld), {}).get(v)
        fals[f"{arm}.{fld}={v:#04x}"] = {
            "outcome": o,
            "fired": o in MOVED or o == "fault",
        }

    for (mnem, fld), arms in sorted(groups.items()):
        per_arm = {}
        for arm in arms:
            vals = byfield[(arm, fld)]
            h, n_eff, moved = summarise(vals)
            per_arm[arm] = {"outcomes": h, "n_effective": n_eff,
                            "moved_output": moved,
                            "arm_live": arm_live.get(arm),
                            "arm_stopped": arm in stopped,
                            "field_stopped": (arm, fld) in field_stopped}
        any_moved = any(a["moved_output"] > 0 for a in per_arm.values())
        n_arms = len(arms)
        complete = all(not a["arm_stopped"] and not a["field_stopped"]
                       for a in per_arm.values())
        live_arms = [a for a in arms if arm_live.get(a)]

        # ---- gate agreement (run02) -------------------------------------
        agree = None
        if gate:
            gb = gate[0]
            tot = same = 0
            for arm in arms:
                a1, a2 = byfield[(arm, fld)], gb.get((arm, fld), {})
                for v, o1 in a1.items():
                    o2 = a2.get(v)
                    if o2 is None or o1 in NOISE or o2 in NOISE:
                        continue
                    tot += 1
                    same += (o1 == o2)
            agree = {"compared": tot, "identical": same,
                     "pct": round(100.0 * same / tot, 2) if tot else None}
        gate_report[f"{mnem}.{fld}"] = agree

        # ---- promotion (PRE_REGISTRATION sec.10) -------------------------
        gate_ok = bool(agree and agree["compared"] and agree["pct"] >= 99.0)
        vals_any = byfield[(arms[0], fld)]
        detection = None
        if any_moved and live_arms:
            detection = ("field detection power proven: at least one value of this "
                         "field changed the observed pixel/lane")
        elif not any_moved and n_arms >= 2 and any(arm_live.get(a) for a in arms):
            detection = ("field inert across its full range on %d independent "
                         "occurrences of a proven-live instruction" % n_arms)
        else:
            detection = "INSUFFICIENT"

        if detection == "INSUFFICIENT":
            label = "untested"
        elif not gate_ok:
            label = "isolated-byte-diff" if any_moved else "untested"
        elif not complete:
            label = "isolated-byte-diff"
        else:
            label = "hardware-run"

        verdicts[f"{mnem}.{fld}"] = {
            "label": label,
            "range": rng(mnem, fld, vals_any),
            "target": "M4",
            "evidence": ["EXP-0143"],
            "semantics": "",          # filled by hand in RESULTS.md review
            "detection": detection,
            "arms": per_arm,
            "gate": agree,
            "note": "",
        }

    out = {"_schema": "FIELD-SWEEP-PROTOCOL sec.5",
           "_runs": runs,
           "_falsifiers": fals,
           "_gate": gate_report,
           "verdicts": verdicts,
           "db_defects": defects}
    p = os.path.join(HERE, "field_verdicts.json")
    json.dump(out, open(p, "w"), indent=1, sort_keys=True)
    n = defaultdict(int)
    for v in verdicts.values():
        n[v["label"]] += 1
    print(json.dumps({"fields": len(verdicts), "by_label": dict(n),
                      "falsifiers_fired": sum(1 for f in fals.values() if f["fired"]),
                      "falsifiers": len(fals)}, indent=1))


if __name__ == "__main__":
    main()
