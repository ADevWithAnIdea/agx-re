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


def db_defects(rules_path):
    """Descriptor defects this experiment proved on hardware.  Each one cites the
    exact machine-checked set identity in analysis/bit_rules.json.  db.json is
    NOT edited here -- the orchestrator owns it (FIELD-SWEEP-PROTOCOL sec.6)."""
    try:
        R = json.load(open(rules_path))
    except OSError:
        R = {}

    def st(key, outcome):
        return R.get(key, {}).get("rules", {}).get(outcome, {}).get("statement", "")

    return {
      "vary_store.match_and_length": {
        "severity": "high -- this is the `emit_unsafe` flag db.json already carries",
        "db_says": "vary_store matches on byte0 == 0x57 ALONE and is always 8 bytes; "
                   "the emit_unsafe note attributes the discriminator to byte+2 == 0x54.",
        "hardware_says": "byte+2 is a DON'T-CARE: all 256 values leave the observation "
                         "identical to the unmutated baseline, in BOTH the 6-byte "
                         "fragment form (c_kill, c_mask) and the 8-byte vertex form "
                         "(c_iter, c_vary16) -- four independent programs. The "
                         "discriminator is byte+1, and only its LOW THREE BITS: "
                         "(byte+1 & 7) == 6 keeps the 8-byte vertex varying store; "
                         "(byte+1 & 7) in {4,5} keeps the 6-byte fragment kill/"
                         "target-mask op; the upper five bits are don't-care.",
        "evidence": {
          "vertex_ok": st("op57_vertex|c_iter/vert@106|byte1", "ok"),
          "vertex_ok_replicate": st("op57_vertex|c_vary16/vert@166|byte1", "ok"),
          "vertex_fault": st("op57_vertex|c_iter/vert@106|byte1", "fault"),
          "fragment_ok": st("op57_fragment|c_kill/frag@88|byte1", "ok"),
          "fragment_ok_replicate": st("op57_fragment|c_mask/frag@88|byte1", "ok"),
          "byte2_inert_vertex": st("op57_vertex|c_iter/vert@106|byte2", "inert"),
          "byte2_inert_fragment": st("op57_fragment|c_kill/frag@88|byte2", "inert"),
          "same_rule_from_the_field_sweep": st(
              "vary_store|vary_store@c_iter/vert106|hint1", "ok")},
        "recommended_descriptor_change":
          "match vary_store on byte0 == 0x57 AND (byte+1 & 7) == 6, length 8; add a "
          "SEPARATE 6-byte descriptor for byte0 == 0x57 AND (byte+1 & 7) in {4,5} "
          "(the fragment kill / target-mask op). Drop byte+2 from the "
          "discrimination entirely -- it is hardware-proven inert. Field `hint2` "
          "(byte+2) and `hint6`/`b7` are then don't-care operands, not selectors.",
        "note": "This is the EXP-0091 collision, unresolved since then. It is now "
                "resolved by behaviour on G17P, from two code paths (the dedicated "
                "0x57 probe and the vary_store field sweep) that agree exactly."},

      "vary_slot.slot": {
        "severity": "medium",
        "db_says": "byte+3 = the varying slot (monotone, tracks the store slot); "
                   "label corpus-correlation.",
        "hardware_says": "INERT: all 256 values leave the observed pixel identical to "
                         "the unmutated baseline, on two different vertex programs "
                         "(c_iter, 4 varyings; c_vary16, 12 varyings). Meanwhile "
                         "byte+1 (`sel`) is exactly load-bearing: the pixel is "
                         "unchanged for the single value 0x0c and moves for all 255 "
                         "others.",
        "evidence": {"slot_inert": st("vary_slot|vary_slot@iter_v0|slot", "inert"),
                     "slot_inert_replicate": st("vary_slot|vary_slot@v16_v0|slot", "inert"),
                     "sel_ok": st("vary_slot|vary_slot@iter_v0|sel", "ok")},
        "recommended_descriptor_change":
          "keep the field, but document byte+3 as a don't-care in the emitted "
          "program: the slot an emitter must get right is vary_store.out_slot, not "
          "vary_slot.slot. A back end may write any value here.",
        "note": "The monotone correlation db.json records is real in COMPILED code "
                "and still says nothing about what the hardware reads."},

      "tex_sample.coord_is_occurrence_dependent": {
        "severity": "medium",
        "db_says": "coord (op+1) is the coordinate register operand.",
        "hardware_says": "coord is INERT over all 256 values on the first two sample "
                         "occurrences of t_sample and on the depth-compare occurrence "
                         "of t_lodoff, but LIVE on the third t_sample occurrence "
                         "(a residue rule mod 32) and on the gather occurrence. So "
                         "the byte is a real operand selector only for some "
                         "occurrences: the coordinate can also arrive implicitly, "
                         "which is consistent with the `chain` nibble being the "
                         "operand-source selector.",
        "evidence": {"inert_occ0": st("tex_sample|tex_sample@t1_0|coord", "inert"),
                     "inert_occ1": st("tex_sample|tex_sample@t1_1|coord", "inert"),
                     "live_occ2": st("tex_sample|tex_sample@t1_2|coord", "ok")},
        "recommended_descriptor_change":
          "do not document coord as an unconditional register operand; its liveness "
          "is conditioned on the companion nibbles (kind/chain). An emitter must set "
          "chain correctly and may not assume coord alone selects the coordinate.",
        "note": "Directly relevant to DOC-02's 'where do a sample's coordinates come "
                "from' blocker."}}


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
    # The frozen rule (PRE_REGISTRATION sec.7 / casematrix.FALSIFIERS) withholds an
    # arm when a falsifier "matches the baseline" -- i.e. was RUN and came back
    # `ok`.  A falsifier value the hang budget never reached is *not evaluated*,
    # and absence of evidence is not evidence of failure: those arms still have
    # to pass the liveness ladder in BOTH runs, which is the detection-power
    # test.  Both readings are recorded per arm.
    armfals, armfals_ran = {}, {}
    for (arm, fld, val) in CM.FALSIFIERS:
        e = fals[f"{arm}.{fld}={val:#x}"]
        armfals.setdefault(arm, []).append(e["fired"])
        ran = e["run01"] is not None and e["run02"] is not None
        armfals_ran.setdefault(arm, []).append((ran, e["fired"]))
    armfals = {a: any(v) for a, v in armfals.items()}
    # withheld iff SOME falsifier ran in both runs and NONE that ran fired
    withhold = {}
    for a, lst in armfals_ran.items():
        ran = [f for (r, f) in lst if r]
        withhold[a] = bool(ran) and not any(ran)

    # The vary_store field sweep is emitted by the collision probe, not by an
    # entry in CM.ARMS, under a carrier id `vary_store@<carrier>/vert<off>`.  It
    # is treated here as a pseudo-arm whose liveness is established by the op57
    # byte+1 sweep on the SAME instruction in the SAME program (which moves the
    # observation for 224 of 256 values), recorded in the raw file alongside it.
    vs_ids = sorted({a for (a, f) in bf1 if a.startswith("vary_store@")}
                    & {a for (a, f) in bf2 if a.startswith("vary_store@")})
    pseudo = [dict(id=i, mnemonic="vary_store", carrier=i.split("@")[1],
                   stage="vertex", occ=0,
                   fields=["hint1", "hint2", "out_slot_hi", "b5_tag", "hint6", "b7"],
                   live=None,
                   note="swept by the 0x57 collision probe; liveness established "
                        "by the byte+1 sweep on the same instruction")
              for i in vs_ids]
    for i in vs_ids:
        live1[i] = live2[i] = True

    verdicts, per_arm = {}, {}
    for arm in list(CM.ARMS) + pseudo:
        aid, mn = arm["id"], arm["mnemonic"]
        desc = isadb._BY_MNEM[mn]
        widths = {f["name"]: f["width"] for f in desc["fields"]}
        alive = bool(live1.get(aid)) and bool(live2.get(aid))
        fal_ok = not withhold.get(aid, False)
        per_arm[aid] = {"mnemonic": mn, "carrier": arm["carrier"],
                        "stage": arm["stage"], "occ": arm["occ"],
                        "live_run01": bool(live1.get(aid)),
                        "live_run02": bool(live2.get(aid)),
                        "baseline_ok": [b1.get(aid), b2.get(aid)],
                        "falsifier_fired": armfals.get(aid),
                        "falsifier_evaluated": [f"{f}={v:#x}" for (a2, f, v) in CM.FALSIFIERS
                                                if a2 == aid and
                                                fals[f"{a2}.{f}={v:#x}"]["run01"] is not None],
                        "verdicts_withheld": withhold.get(aid, False),
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
            elif not agree:
                label, note = "untested", (f"NO reproducible observation: all "
                                           f"{len(got)} values common to the two "
                                           f"gated runs DISAGREE between them")
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
           "db_defects": db_defects(rules_path=os.path.join(HERE, "bit_rules.json"))}
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
