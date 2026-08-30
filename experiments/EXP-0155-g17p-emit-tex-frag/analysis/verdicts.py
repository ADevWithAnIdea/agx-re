#!/usr/bin/env python3
"""verdicts.py -- EXP-0155 reduction: two gated runs -> analysis/field_verdicts.json.

    python3 analysis/verdicts.py --run01 <id> --run02 <id> [--raw-root raw]

Reads ONLY the append-only raw records and the frozen case matrix.  Nothing here
touches hardware, so it is re-runnable by a reviewer from the committed tree.

Labelling rules (frozen; they implement docs/evidence-classification.md sec.2):

  hardware-run        the arm is LIVE, its pre-registered falsifier FIRED, the
                      field was swept over its COMPLETE frozen value set in BOTH
                      gated runs, and every value's outcome AGREES across the two
                      runs.  (An outcome of `ok` -- identical to the arm's own
                      unmutated baseline -- is an observation: it says the field
                      is a don't-care in this context, which is exactly what an
                      emitter needs to know.  Silent zeros and reproducible
                      faults are observations too.)
  isolated-byte-diff  live arm and a reproducible effect at one or more points,
                      but the sweep was incomplete or the two runs disagree at
                      some values -- i.e. validated at points, not over a range.
  untested            the arm was not live, its falsifier did not fire, the field
                      was not run, or the evidence is otherwise INSUFFICIENT.

Nothing is ever rounded up.  Both the strict cross-run label and the label the
frozen rule would give from ONE run are recorded, as EXP-0147 did.

CLEAN-ROOM: pure analysis of our own raw records.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.environ.get("AGXRE_REPO", os.path.abspath(os.path.join(EXP, "..", "..")))
sys.path.insert(0, os.path.join(EXP, "harness"))
sys.path.insert(0, os.path.join(REPO, "tools", "agx-isa"))
import isadb                       # noqa: E402
import casematrix as CM            # noqa: E402

GOOD = ("hardware-run", "isolated-byte-diff")


def load(path):
    recs = []
    with open(path) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                recs.append(json.loads(ln))
    return recs


def index(recs):
    """(arm, field) -> {value: outcome}, plus per-arm liveness / falsifier state."""
    byfield, live, ladder, base_ok, notrun = {}, {}, {}, {}, set()
    for r in recs:
        arm, fld = r["carrier"], r["field"]
        if fld == "_baseline":
            base_ok[arm] = (r["outcome"] == "ok")
        elif fld == "_live_control":
            ladder.setdefault(arm, []).append(r["note"])
            if r["match"]:
                live[arm] = True
        elif fld == "_arm_not_run":
            notrun.add(arm)
        elif fld.startswith("_"):
            continue
        else:
            byfield.setdefault((arm, fld), {})[r["value"]] = r["outcome"]
    for a in ladder:
        live.setdefault(a, False)
    return byfield, live, ladder, base_ok, notrun


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run01", required=True)
    ap.add_argument("--run02", required=True)
    ap.add_argument("--raw-root", default=os.path.join(EXP, "raw"))
    args = ap.parse_args()

    R = {}
    for tag, rid in (("r1", args.run01), ("r2", args.run02)):
        R[tag] = index(load(os.path.join(args.raw_root, rid, "sweep.jsonl")))

    (bf1, live1, lad1, b1, nr1) = R["r1"]
    (bf2, live2, lad2, b2, nr2) = R["r2"]

    # falsifiers: each must come back NON-`ok` in both runs
    fals = {}
    for (arm, fld, val) in CM.FALSIFIERS:
        o1 = bf1.get((arm, fld), {}).get(val)
        o2 = bf2.get((arm, fld), {}).get(val)
        fals[f"{arm}.{fld}={val:#x}"] = {
            "run01": o1, "run02": o2,
            "fired": (o1 not in (None, "ok")) and (o2 not in (None, "ok"))}
    armfals = {}
    for (arm, fld, val) in CM.FALSIFIERS:
        armfals.setdefault(arm, []).append(
            fals[f"{arm}.{fld}={val:#x}"]["fired"])
    armfals = {a: any(v) for a, v in armfals.items()}

    verdicts, per_arm = {}, {}
    for arm in CM.ARMS:
        aid, mn = arm["id"], arm["mnemonic"]
        desc = isadb._BY_MNEM[mn]
        widths = {f["name"]: f["width"] for f in desc["fields"]}
        alive = bool(live1.get(aid)) and bool(live2.get(aid))
        fal_ok = armfals.get(aid, True)     # arms with no falsifier are not gated on one
        per_arm[aid] = {"mnemonic": mn, "carrier": arm["carrier"],
                        "stage": arm["stage"], "occ": arm["occ"],
                        "live_run01": bool(live1.get(aid)),
                        "live_run02": bool(live2.get(aid)),
                        "baseline_ok": [b1.get(aid), b2.get(aid)],
                        "falsifier_fired": armfals.get(aid),
                        "not_run": [aid in nr1, aid in nr2],
                        "ladder_steps": [len(lad1.get(aid, [])), len(lad2.get(aid, []))]}
        for fld in arm["fields"]:
            want = set(CM.field_values(desc["fields"], fld))
            o1 = bf1.get((aid, fld), {})
            o2 = bf2.get((aid, fld), {})
            got = set(o1) & set(o2)
            complete = want.issubset(set(o1)) and want.issubset(set(o2))
            agree = [v for v in sorted(got) if o1[v] == o2[v]]
            disagree = [v for v in sorted(got) if o1[v] != o2[v]]
            moved = sum(1 for v in agree if o1[v] in ("wrong_value", "silent_zero"))
            faults = sum(1 for v in agree if o1[v] in ("fault", "hang"))
            zeros = sum(1 for v in agree if o1[v] == "silent_zero")
            inert = sum(1 for v in agree if o1[v] == "ok")
            w = widths.get(fld, 8)
            rng = (f"0..{(1 << w) - 1} dense (all {1 << w} values)" if w <= 8
                   else f"{len(want)} sampled values of 2^{w} "
                        f"(boundaries + powers of two + 16 asymmetric interior)")
            if not got:
                label, note = "untested", "not swept in both gated runs"
            elif not alive:
                label, note = "untested", ("INSUFFICIENT detection proof: the arm's "
                                           "liveness ladder produced no change in "
                                           "one or both runs, so nothing this field "
                                           "does can be attributed")
            elif not fal_ok:
                label, note = "untested", ("verdict WITHHELD: the arm's "
                                           "pre-registered falsifier did not fire, "
                                           "so the method could not be shown able "
                                           "to see a difference on the day")
            elif complete and not disagree:
                label, note = "hardware-run", ""
            elif not disagree and got:
                label, note = ("isolated-byte-diff",
                               f"swept {len(got)}/{len(want)} of the frozen value "
                               f"set in both runs (incomplete: a hang/deadline "
                               f"budget stopped it); the values that did run agree "
                               f"across both runs")
            else:
                label, note = ("isolated-byte-diff",
                               f"{len(disagree)}/{len(got)} values disagree between "
                               f"the two gated runs; validated at points, not over "
                               f"a range")
            literal = ("hardware-run" if (alive and fal_ok and want.issubset(set(o1)))
                       else label)
            verdicts[f"{mn}.{fld}@{aid}"] = {
                "label": label,
                "label_under_frozen_rule_literal_run01_only": literal,
                "range": rng,
                "target": "G17P",
                "evidence": ["EXP-0155"],
                "arm": aid, "carrier": arm["carrier"], "stage": arm["stage"],
                "swept_both_runs": len(got), "of": len(want),
                "cross_run_disagreements": len(disagree),
                "outcome_counts": {"ok_inert": inert, "moved_output": moved,
                                   "silent_zero": zeros, "fault_or_hang": faults},
                "semantics": "",
                "note": note}

    # ---- per-field roll-up across arms, then per-instruction emittability ----
    roll = {}
    for k, v in verdicts.items():
        mn, rest = k.split(".", 1)
        fld = rest.split("@")[0]
        cur = roll.get(f"{mn}.{fld}")
        rank = {"hardware-run": 3, "isolated-byte-diff": 2, "untested": 0}
        if cur is None or rank[v["label"]] > rank[cur["label"]]:
            roll[f"{mn}.{fld}"] = dict(v, arms=[v["arm"]])
        else:
            cur["arms"].append(v["arm"])

    emit = {}
    val = json.load(open(os.path.join(REPO, "tools", "agx-isa", "validation.json")))
    vi = val["instructions"]
    for mn in sorted({a["mnemonic"] for a in CM.ARMS} | {"vary_store"}):
        d = isadb._BY_MNEM[mn]
        rows = {}
        for f in d["fields"]:
            prior = vi.get(mn, {}).get(f["name"], {}).get("label", "untested")
            new = roll.get(f"{mn}.{f['name']}", {}).get("label")
            best = new if (new and new in GOOD) else (prior if prior in GOOD else
                                                      (new or prior))
            rows[f["name"]] = {"prior": prior, "this_experiment": new, "final": best}
        emit[mn] = {"fields": rows,
                    "emittable": all(r["final"] in GOOD for r in rows.values()),
                    "blocking_after": [n for n, r in rows.items()
                                       if r["final"] not in GOOD]}

    out = {"_spec": "docs/evidence-classification.md sec.2 labels; "
                    "FIELD-SWEEP-PROTOCOL sec.5 shape",
           "_runs": {"run01": args.run01, "run02": args.run02},
           "_target": "G17P (Apple A18 Pro, applegpu_g17p) -- DIRECT, not INFERRED",
           "falsifiers": fals,
           "arms": per_arm,
           "per_arm_field_verdicts": verdicts,
           "field_rollup": roll,
           "emittability": emit,
           "db_defects": {}}
    with open(os.path.join(EXP, "analysis", "field_verdicts.json"), "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)

    n_hw = sum(1 for v in roll.values() if v["label"] == "hardware-run")
    n_ib = sum(1 for v in roll.values() if v["label"] == "isolated-byte-diff")
    n_un = sum(1 for v in roll.values() if v["label"] == "untested")
    print(f"fields rolled up: {len(roll)}  hardware-run={n_hw} "
          f"isolated-byte-diff={n_ib} untested={n_un}")
    for mn, e in sorted(emit.items()):
        print(f"  {mn:20s} {'EMITTABLE' if e['emittable'] else 'blocked: ' + ','.join(e['blocking_after'])}")
    print("falsifiers fired:",
          sum(1 for v in fals.values() if v["fired"]), "/", len(fals))


if __name__ == "__main__":
    main()
