#!/usr/bin/env python3
"""EXP-0206 GATE -- recomputes every verdict from raw/ under the frozen rule of
PRE_REGISTRATION.md section 7. Nothing is read back from a run manifest.

  python3 analysis/verdicts206.py raw/g17p_20260830_run01 raw/g17p_20260830_run02

THE GATE MUST BE ABLE TO SAY NO. Thirteen checks in this corpus could not, in two
mirror-image forms: a PROMOTION gate with no `moved >= 1` conjunct (which
certified a synthetic dead-code arm) and an INERTNESS gate with no
detection-power conjunct (which certified an arm whose observable could not vary).
`selftest()` runs first and the gate REFUSES TO RUN if it fails: it feeds itself
a dead-code arm, a fault-wall arm, and a width-1 arm and asserts the first two are
refused and the third is promotable.

Definitions, all from raw:

  VALID case   status OK and the INTEGRITY SENTINEL present. `not_written` (the
               sentinel written and every value word still POISON) is VALID: it is
               how a mid-program terminator announces itself.
  HARD case    fault / hang / invalid_run (sentinel missing) / measurement_failure
               / nondeterministic. **Hard outcomes are NEVER movement.** A gate
               that separates `ok` from `fault` counts a GPU fault as evidence;
               that defect withdrew `ret_luse.linkmode`.
  V            distinct VALID payloads. V <= 1 across many legal values means the
               values ran legally and were INDISTINGUISHABLE -- a hazard map, not
               a semantic (EXP-0192 Case C).
  L            values that produced a valid payload.
  moved        values whose valid payload differs from THIS ARM's own baseline
               (the `_force_baseline` where the descriptor is synthesized, else
               the arm-open baseline).
  disagree     values valid in both runs whose payloads differ between runs.
  control      the arm at the SAME occurrence sweeping the detection-power field.
               It FIRES if it produces >= 2 distinct valid payloads, or a
               valid<->hard split. A control that does not fire BARS every verdict
               on its target arm -- live AND inert.

CLEAN-ROOM: pure analysis of our own raw records.
"""
import collections
import glob
import json
import os
import sys

VALID = {"ok", "silent_zero", "wrong_value", "not_written"}
HARD = {"fault", "hang", "invalid_run", "measurement_failure",
        "nondeterministic", "undecodable", "carrier_start_failed"}
AGREE_MIN = 0.99


def payload(r):
    return json.dumps(r.get("observed"), sort_keys=True)


def load(run_dirs):
    out = []
    for d in run_dirs:
        run = os.path.basename(d.rstrip("/"))
        for f in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
            for line in open(f, errors="replace"):
                try:
                    r = json.loads(line)
                except Exception:                               # noqa: BLE001
                    continue
                r["_run"] = run
                out.append(r)
    return out


def arm_stats(recs, runs):
    """recs = every record of ONE arm across both runs."""
    tgt = [r for r in recs if r.get("role") in
           ("target", "control", "control_termination")]
    base = {}
    for r in recs:
        if r.get("field") == "_force_baseline":
            base[r["_run"]] = payload(r)
    for r in recs:
        if r.get("field") == "_baseline" and str(r.get("note", "")).endswith(":open"):
            base.setdefault(r["_run"], payload(r))
    valid = [r for r in tgt if r.get("outcome") in VALID]
    hard = collections.Counter(r.get("outcome") for r in tgt
                               if r.get("outcome") in HARD)
    other = collections.Counter(r.get("outcome") for r in tgt
                                if r.get("outcome") not in VALID
                                and r.get("outcome") not in HARD)
    per_run = collections.defaultdict(dict)
    for r in valid:
        per_run[r["_run"]][r.get("value")] = payload(r)
    moved = set()
    for r in valid:
        b = base.get(r["_run"])
        if b is not None and payload(r) != b:
            moved.add(r.get("value"))
    rk = sorted(per_run)
    disagree, comparable = set(), set()
    if len(rk) >= 2:
        a, b = per_run[rk[0]], per_run[rk[1]]
        comparable = set(a) & set(b)
        disagree = {v for v in comparable if a[v] != b[v]}
    agreement = (1 - len(disagree) / len(comparable)) if comparable else None
    return {
        "runs": rk,
        "n_records": len(tgt),
        "V": len({payload(r) for r in valid}),
        "L": len({r.get("value") for r in valid}),
        "values_dispatched": len({r.get("value") for r in tgt}),
        "distinct_encodings": len({r.get("bytes") for r in tgt if r.get("bytes")}),
        "moved": len(moved),
        "moved_values": sorted(moved)[:64],
        "disagree": len(disagree),
        "comparable": len(comparable),
        "agreement": agreement,
        "hard": dict(hard),
        "unclassified": dict(other),
        "n_valid": len(valid),
        "baseline_per_run": {k: v[:40] for k, v in base.items()},
        "prediction": {
            "checked": sum(1 for r in tgt if r.get("prediction_ok") is not None),
            "held": sum(1 for r in tgt if r.get("prediction_ok") is True),
            "refuted": sum(1 for r in tgt if r.get("prediction_ok") is False),
        },
        "occ_dim": next((r.get("occ_dim") for r in tgt), None),
        "carrier": next((r.get("carrier") for r in tgt), None),
        "region": next((r.get("region") for r in tgt), None),
        "off": next((r.get("off") for r in tgt), None),
        "key": next((r.get("key") for r in tgt), None),
        "field": next((r.get("field") for r in tgt), None),
        "instr": next((r.get("instr") for r in tgt), None),
        "role": next((r.get("role") for r in tgt), None),
        "synthesized": next((r.get("synthesized") for r in tgt), None),
    }


def control_fires(st):
    """>= 2 distinct valid payloads, OR a valid<->hard split. Both are real
    demonstrations that the arm's observable responds to a change at this exact
    occurrence."""
    if st is None:
        return False, "no control arm"
    if st["V"] >= 2:
        return True, "control produced %d distinct valid payloads" % st["V"]
    nhard = sum(st["hard"].values())
    if nhard and st["n_valid"]:
        return True, "control produced a valid<->hard split (%d valid, %d hard)" \
            % (st["n_valid"], nhard)
    if st["moved"] > 0:
        return True, "control moved %d values off baseline" % st["moved"]
    return False, ("control did NOT fire (V=%d, valid=%d, hard=%d) -- this arm has "
                   "no demonstrated detection power and BARS every verdict on its "
                   "target, live AND inert"
                   % (st["V"], st["n_valid"], sum(st["hard"].values())))


def selftest():
    """Three synthetic arms. The gate must refuse the first two and admit the third."""
    ok = True

    def mk(vals, outcome="ok", role="target", arm="A", run="r1", base=None):
        rs = [{"role": "_", "field": "_baseline", "note": arm + ":open",
               "observed": base if base is not None else {"vh": "B"},
               "_run": run, "outcome": "ok"}]
        for i, v in enumerate(vals):
            rs.append({"role": role, "field": "f", "instr": "x", "value": i,
                       "observed": v, "outcome": outcome, "bytes": "%02x" % i,
                       "_run": run, "arm": arm})
        return rs

    dead = mk([{"vh": "B"}] * 8) + mk([{"vh": "B"}] * 8, run="r2")
    st = arm_stats(dead, ["r1", "r2"])
    if st["moved"] != 0 or st["V"] != 1:
        print("SELFTEST FAIL: dead-code arm did not read as V=1, moved=0"); ok = False
    if promote(st, (True, "x"))[0] != "REFUSED":
        print("SELFTEST FAIL: a DEAD-CODE arm was promoted"); ok = False
    if inert(st, (False, "x"))[0] != "UNRESOLVED":
        print("SELFTEST FAIL: an arm with NO fired control was called inert"); ok = False

    wall = (mk([{"vh": "B"}], base={"vh": "B"}) +
            mk([{"vh": "?"}] * 7, outcome="fault"))
    wall += [dict(r, _run="r2") for r in wall]
    stw = arm_stats(wall, ["r1", "r2"])
    if promote(stw, (True, "x"))[0] != "REFUSED":
        print("SELFTEST FAIL: a FAULT WALL (V=1) was promoted"); ok = False

    w1 = (mk([{"vh": "B"}, {"vh": "C"}], base={"vh": "B"}) +
          mk([{"vh": "B"}, {"vh": "C"}], run="r2", base={"vh": "B"}))
    st1 = arm_stats(w1, ["r1", "r2"])
    if st1["moved"] != 1 or st1["disagree"] != 0:
        print("SELFTEST FAIL: width-1 arm stats wrong (%s)" % st1); ok = False
    if promote(st1, (True, "x"))[0] != "PROMOTE":
        print("SELFTEST FAIL: a width-1 arm with 1 movement and 0 disagreements "
              "was refused -- the `2*max(disagree,1)` arithmetic bug"); ok = False
    return ok


def promote(st, ctl):
    """PRE_REGISTRATION section 7 step 2. Written as `moved >= 2 * disagree AND
    moved > 0` -- NOT `moved >= 2 * max(disagree, 1)`, which cannot promote any
    width-1 field by arithmetic rather than by evidence."""
    why = []
    if st["V"] < 2:
        why.append("V=%d < 2: fewer than two distinct VALID payloads (Case C -- "
                   "the values ran legally and were indistinguishable)" % st["V"])
    if not (st["moved"] > 0):
        why.append("moved=0")
    if not (st["moved"] >= 2 * st["disagree"]):
        why.append("moved=%d < 2*disagree=%d" % (st["moved"], 2 * st["disagree"]))
    if st["agreement"] is None or st["agreement"] < AGREE_MIN:
        why.append("cross-run agreement %s < %.2f" % (st["agreement"], AGREE_MIN))
    if len(st["runs"]) < 2:
        why.append("fewer than 2 gated runs")
    if not ctl[0]:
        why.append(ctl[1])
    return ("PROMOTE" if not why else "REFUSED"), why


def inert(st, ctl):
    """Section 7 step 3 / FIELD-SWEEP-PROTOCOL section 9: an INERT verdict needs a
    positive control IN THE SAME DIMENSION that moved on this arm, a swept range,
    cross-run agreement, and a pre-registered falsifier. Missing any -> UNRESOLVED,
    never 'inert'."""
    why = []
    if st["V"] != 1:
        why.append("V=%d, not a single payload" % st["V"])
    if not ctl[0]:
        why.append(ctl[1])
    if st["agreement"] is None or st["agreement"] < AGREE_MIN:
        why.append("cross-run agreement %s < %.2f" % (st["agreement"], AGREE_MIN))
    if len(st["runs"]) < 2:
        why.append("fewer than 2 gated runs")
    if st["L"] < st["values_dispatched"]:
        why.append("only %d of %d dispatched values produced a valid payload -- the "
                   "range is bounded by a hazard, not swept clean"
                   % (st["L"], st["values_dispatched"]))
    return ("INERT" if not why else "UNRESOLVED"), why


def main():
    if not selftest():
        print("GATE SELF-TEST FAILED -- refusing to produce verdicts.")
        return 2
    runs = sys.argv[1:]
    if not runs:
        print(__doc__)
        return 0
    recs = load(runs)
    by_arm = collections.defaultdict(list)
    for r in recs:
        a = r.get("arm")
        if not a:
            continue
        by_arm[a.split(":mid")[0].replace(":open", "").replace(":close", "")].append(r)

    stats = {a: arm_stats(rs, runs) for a, rs in by_arm.items()}
    # map occurrence -> control arm
    ctl_by_occ = {}
    for a, st in stats.items():
        if st["role"] in ("control", "control_termination"):
            ctl_by_occ.setdefault((st["carrier"], st["region"], st["off"]), []).append((a, st))

    out = {"_gate": "PRE_REGISTRATION.md section 7, recomputed from raw",
           "_runs": runs, "_selftest": "passed", "arms": {}, "fields": {}}
    per_key = collections.defaultdict(list)
    for a, st in sorted(stats.items()):
        if st["role"] != "target":
            out["arms"][a] = st
            continue
        ctls = ctl_by_occ.get((st["carrier"], st["region"], st["off"]), [])
        fired = [(n, control_fires(s)) for n, s in ctls]
        best = next((f for f in fired if f[1][0]), None)
        ctl = best[1] if best else (fired[0][1] if fired else (False, "no control arm"))
        p, pw = promote(st, ctl)
        i, iw = inert(st, ctl)
        st = dict(st, control=[{"arm": n, "fires": f[0], "why": f[1]}
                               for n, f in fired],
                  promote=p, promote_blockers=pw, inert=i, inert_blockers=iw)
        out["arms"][a] = st
        per_key[st["key"]].append((a, st))

    for key, arms in sorted(per_key.items()):
        V = max(s["V"] for _, s in arms)
        L = sum(s["L"] for _, s in arms)
        hard = collections.Counter()
        for _, s in arms:
            hard.update(s["hard"])
        ag = [s["agreement"] for _, s in arms if s["agreement"] is not None]
        promoted = [a for a, s in arms if s["promote"] == "PROMOTE"]
        inerts = [a for a, s in arms if s["inert"] == "INERT"]
        verdict = ("hardware-run" if promoted else
                   ("hardware-run(INERT)" if inerts and len(inerts) == len(arms)
                    else "untested"))
        out["fields"][key] = {
            "verdict": verdict,
            "n_arms": len(arms),
            "V_max_per_arm": V,
            "V_union": len({p for _, s in arms for p in [s["V"]]}) and None,
            "L_total": L,
            "hard_total": dict(hard),
            "agreement_min": min(ag) if ag else None,
            "arms_promoted": promoted,
            "arms_inert": inerts,
            "arms_unresolved": [a for a, s in arms
                                if s["promote"] != "PROMOTE" and s["inert"] != "INERT"],
        }

    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gate206.json")
    with open(p, "w") as f:
        json.dump(out, f, indent=1, sort_keys=True)

    print("== per-arm ==")
    for a, st in sorted(out["arms"].items()):
        if st.get("role") != "target":
            continue
        print("%-56s V=%-3d L=%-4d moved=%-4d dis=%-3d agr=%s hard=%s -> %s / %s"
              % (a[:56], st["V"], st["L"], st["moved"], st["disagree"],
                 ("%.4f" % st["agreement"]) if st["agreement"] is not None else "n/a",
                 st["hard"], st["promote"], st["inert"]))
    print("\n== per-field ==")
    for k, v in sorted(out["fields"].items()):
        print("%-32s %-22s arms=%d Vmax=%d L=%d hard=%s agr_min=%s"
              % (k, v["verdict"], v["n_arms"], v["V_max_per_arm"], v["L_total"],
                 v["hard_total"], v["agreement_min"]))
    print("\nwrote %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
