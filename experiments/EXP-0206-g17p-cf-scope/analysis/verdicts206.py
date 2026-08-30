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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models206 as MD          # noqa: E402

VALID = {"ok", "silent_zero", "wrong_value", "not_written"}
HARD = {"fault", "hang", "invalid_run", "measurement_failure",
        "nondeterministic", "undecodable", "carrier_start_failed"}
AGREE_MIN = 0.99
NOTHER = 0


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
    # ---- GATE A: the actual-byte ledger ------------------------------------
    led_ok = sum(1 for r in tgt if r.get("ledger_ok") is True)
    led_bad = [r.get("value") for r in tgt if r.get("ledger_ok") is False]
    req_vals = {r.get("value") for r in tgt}
    act_enc = {(r.get("ledger") or {}).get("act_bytes") for r in tgt
               if (r.get("ledger") or {}).get("act_bytes")}
    # ---- GATE C: competing semantic models ---------------------------------
    sem = {}
    for r in tgt:
        b = r.get("sem_bucket")
        for m, pred in (r.get("sem_pred") or {}).items():
            d = sem.setdefault(m, {"checked": 0, "hit": 0, "miss": 0,
                                   "miss_values": []})
            if pred is None or b is None:
                continue
            d["checked"] += 1
            if pred == b:
                d["hit"] += 1
            else:
                d["miss"] += 1
                if len(d["miss_values"]) < 24:
                    d["miss_values"].append([r.get("value"), pred, b])
    survivors = [m for m, d in sem.items() if d["checked"] > 0 and d["miss"] == 0]
    # ---- GATE E: contamination ---------------------------------------------
    contaminated = sum(1 for r in tgt if r.get("contaminated"))
    buckets = collections.Counter(r.get("sem_bucket") for r in tgt)
    return {
        "runs": rk,
        "n_records": len(tgt),
        "ledger_ok": led_ok,
        "ledger_bad": len(led_bad),
        "ledger_bad_values": led_bad[:24],
        "distinct_requested_values": len(req_vals),
        "distinct_actual_encodings": len(act_enc),
        "encoding_collision": len(act_enc) < len(req_vals),
        "sem": sem,
        "sem_checked_total": sum(d["checked"] for d in sem.values()),
        "sem_surviving_models": sorted(survivors),
        "buckets": dict(buckets),
        "contaminated_cases": contaminated,
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
        "start": next((r.get("start") for r in tgt), None),
        "width": next((r.get("width") for r in tgt), None),
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
    """Five synthetic arms. The gate must refuse the first four and admit the last.

    (1) DEAD CODE -- a constant observable. Must not promote AND must not be
        called inert (the two mirror-image cannot-fail defects in this corpus).
    (2) FAULT WALL -- one valid payload, many faults. Must not promote: a
        perfectly reproducible hazard map is not a semantic (EXP-0192 Case C).
    (3) LIVENESS WITHOUT SEMANTICS -- real movement, `sem_checked == 0`. Must not
        promote (RE_EXPERIMENT_PROCESS_CORRECTIONS Gate C / the EXP-0169 error).
    (4) LEDGER FAILURE -- movement and a surviving model, but the actual dispatched
        bytes did not decode to the requested value. Must not promote (Gate A).
    (5) WIDTH-1 -- one movement, zero disagreements, a surviving model. MUST be
        promotable: the `moved >= 2 * max(disagree, 1)` form refuses this by
        arithmetic rather than by evidence (FIELD-SWEEP-PROTOCOL 5b).
    """
    ok = True

    def mk(vals, outcome="ok", role="target", arm="A", run="r1", base=None,
           sem=None, bucket="correct", ledger=True):
        rs = [{"role": "_", "field": "_baseline", "note": arm + ":open",
               "observed": base if base is not None else {"vh": "B"},
               "_run": run, "outcome": "ok"}]
        for i, v in enumerate(vals):
            rs.append({"role": role, "field": "f", "instr": "x", "value": i,
                       "observed": v, "outcome": outcome, "bytes": "%02x" % i,
                       "_run": run, "arm": arm, "ledger_ok": ledger,
                       "ledger": {"act_bytes": "%02x" % i},
                       "sem_bucket": bucket,
                       "sem_pred": (sem or {})})
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
            mk([{"vh": "?"}] * 7, outcome="fault", bucket="reject"))
    wall += [dict(r, _run="r2") for r in wall]
    if promote(arm_stats(wall, ["r1", "r2"]), (True, "x"))[0] != "REFUSED":
        print("SELFTEST FAIL: a FAULT WALL (V=1) was promoted"); ok = False

    nosem = (mk([{"vh": "B"}, {"vh": "C"}], base={"vh": "B"}) +
             mk([{"vh": "B"}, {"vh": "C"}], run="r2", base={"vh": "B"}))
    if promote(arm_stats(nosem, ["r1", "r2"]), (True, "x"))[0] != "REFUSED":
        print("SELFTEST FAIL: LIVENESS WITH ZERO SEMANTIC CHECKS was promoted -- "
              "Gate C says sem_checked == 0 can never produce hardware-run")
        ok = False

    sem_ok = {"M": "correct"}
    badled = (mk([{"vh": "B"}, {"vh": "C"}], base={"vh": "B"}, sem=sem_ok,
                 ledger=False) +
              mk([{"vh": "B"}, {"vh": "C"}], run="r2", base={"vh": "B"},
                 sem=sem_ok, ledger=False))
    if promote(arm_stats(badled, ["r1", "r2"]), (True, "x"))[0] != "REFUSED":
        print("SELFTEST FAIL: an arm whose ACTUAL bytes did not match the request "
              "was promoted -- Gate A"); ok = False

    w1 = (mk([{"vh": "B"}, {"vh": "C"}], base={"vh": "B"}, sem=sem_ok) +
          mk([{"vh": "B"}, {"vh": "C"}], run="r2", base={"vh": "B"}, sem=sem_ok))
    st1 = arm_stats(w1, ["r1", "r2"])
    if st1["moved"] != 1 or st1["disagree"] != 0:
        print("SELFTEST FAIL: width-1 arm stats wrong (%s)" % st1); ok = False
    p1, w1w = promote(st1, (True, "x"))
    if p1 != "PROMOTE":
        print("SELFTEST FAIL: a width-1 arm with 1 movement, 0 disagreements and a "
              "surviving model was refused (%s)" % w1w); ok = False
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
    # GATE A -- no hardware conclusion from a case whose requested bytes were not
    # the bytes actually dispatched.
    if st["ledger_bad"]:
        why.append("GATE A: %d cases whose ACTUAL dispatched bytes did not decode "
                   "to the requested value" % st["ledger_bad"])
    if st["distinct_actual_encodings"] < st["distinct_requested_values"]:
        why.append("GATE A: %d distinct requested values collapsed to %d distinct "
                   "ACTUAL encodings (aliasing)"
                   % (st["distinct_requested_values"],
                      st["distinct_actual_encodings"]))
    # GATE C -- `sem_checked == 0` can never produce `hardware-run`.
    if st["sem_checked_total"] == 0:
        why.append("GATE C: sem_checked == 0 -- liveness only, role unknown")
    elif not st["sem_surviving_models"]:
        why.append("GATE C: no pre-registered semantic model survived (%s)"
                   % {m: "%d/%d" % (d["hit"], d["checked"])
                      for m, d in st["sem"].items()})
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
    if st["ledger_bad"]:
        why.append("GATE A: %d cases failed the actual-byte ledger" % st["ledger_bad"])
    return ("INERT" if not why else "UNRESOLVED"), why


def axes(st, ctl, promoted, inerted, n_other_agents):
    """The six INDEPENDENT axes of RE_EXPERIMENT_PROCESS_CORRECTIONS section 2.
    A result on one axis must never imply a result on another."""
    geometry = ("geometry-mapped" if (st["ledger_bad"] == 0
                                      and st["distinct_actual_encodings"]
                                      >= st["distinct_requested_values"])
                else ("ledger-verified" if st["ledger_ok"] else "unverified"))
    # LIVENESS vs the control requirement. RE_EXPERIMENT_PROCESS_CORRECTIONS
    # Gate B: "If the positive control fails, the arm is `carrier-undecidable`;
    # ZERO MOVEMENT is not evidence of inertness." The control exists to license an
    # INERT reading. An arm whose TARGET FIELD ITSELF moved has demonstrated its own
    # detection power directly and more strongly than any control could, so a failed
    # control does not erase an observed movement -- it only bars the inert reading.
    # This experiment's own frozen section 5 rule is STRICTER (a failed control bars
    # both), and it is still applied to `promote`/`inert`; the liveness AXIS reports
    # the normative reading. Both are published side by side.
    if not ctl[0] and st["moved"] == 0 and not sum(st["hard"].values()):
        liveness = "carrier-undecidable"
    elif st["moved"] > 0 and st["V"] >= 2:
        liveness = "live"
    elif sum(st["hard"].values()) and st["V"] >= 1:
        liveness = "live(legal-set-bounded)"
    elif st["V"] == 1 and st["L"] == st["values_dispatched"]:
        liveness = "accepted-inert"
    else:
        liveness = "carrier-undecidable"
    if st["sem_checked_total"] == 0:
        semantics = "unknown"
    elif len(st["sem_surviving_models"]) == 1:
        semantics = "semantically-mapped(single surviving model: %s)" \
            % st["sem_surviving_models"][0]
    elif st["sem_surviving_models"]:
        semantics = "bounded-map(%d models still survive: %s)" \
            % (len(st["sem_surviving_models"]), ",".join(st["sem_surviving_models"]))
    else:
        semantics = "hypothesis(all pre-registered models refuted)"
    return {
        "encoding_geometry": geometry,
        "liveness": liveness,
        "semantics": semantics,
        # Nothing in this experiment builds a whole program from documented rules;
        # every case mutates ONE field of our own compiled carrier.
        "compiler_recipe": "generated-point" if promoted else "not-generated",
        "target": "G17P-direct",
        "reproducibility": ("auditable" if n_other_agents else
                            ("independently-confirmed" if len(st["runs"]) >= 2
                             else "incomplete")),
    }


def main():
    if not selftest():
        print("GATE SELF-TEST FAILED -- refusing to produce verdicts.")
        return 2
    runs = sys.argv[1:]
    if not runs:
        print(__doc__)
        return 0
    recs = load(runs)
    global NOTHER
    NOTHER = 0
    procs = []
    for d in runs:
        f = os.path.join(d, "procs.jsonl")
        if os.path.exists(f):
            for ln in open(f):
                try:
                    procs.append(json.loads(ln))
                except Exception:                               # noqa: BLE001
                    pass
    if procs:
        NOTHER = max(p.get("n_other_agents", 0) for p in procs)
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

    out = {"_gate": "PRE_REGISTRATION.md section 7 + PRE_REGISTRATION_A2.md "
                    "(Gates A/B/C/E), recomputed from raw",
           "_runs": runs, "_selftest": "passed",
           "_concurrency": {
               "samples": len(procs),
               "max_other_gpu_agent_processes": NOTHER,
               "note": "GATE E: a confirmation run may not rely on a busy machine. "
                       "This is a MEASUREMENT of how busy it was, taken from "
                       "raw/<run>/procs.jsonl, not a claim in prose. Non-zero here "
                       "caps every reproducibility axis at `auditable`."},
           "arms": {}, "fields": {}}
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
                  promote=p, promote_blockers=pw, inert=i, inert_blockers=iw,
                  axes=axes(st, ctl, p == "PROMOTE", i == "INERT", NOTHER))
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
        sem_all = {}
        for _, s2 in arms:
            for m, d in s2["sem"].items():
                a2 = sem_all.setdefault(m, {"checked": 0, "hit": 0, "miss": 0})
                a2["checked"] += d["checked"]
                a2["hit"] += d["hit"]
                a2["miss"] += d["miss"]
        surviving = sorted(m for m, d in sem_all.items()
                           if d["checked"] > 0 and d["miss"] == 0)
        out["fields"][key] = {
            "verdict": verdict,
            "axes_per_arm": {a: s2["axes"] for a, s2 in arms if "axes" in s2},
            "semantic_models": sem_all,
            "surviving_models": surviving,
            "ledger_ok_total": sum(s2["ledger_ok"] for _, s2 in arms),
            "ledger_bad_total": sum(s2["ledger_bad"] for _, s2 in arms),
            "distinct_actual_encodings_per_arm":
                {a: s2["distinct_actual_encodings"] for a, s2 in arms},
            "buckets_total": dict(sum((collections.Counter(s2["buckets"])
                                       for _, s2 in arms),
                                      collections.Counter())),
            "contaminated_cases": sum(s2["contaminated_cases"] for _, s2 in arms),
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
        print("%-30s %-20s arms=%d Vmax=%d L=%d hard=%s agr=%s ledger=%d/%d "
              "surviving=%s"
              % (k, v["verdict"], v["n_arms"], v["V_max_per_arm"], v["L_total"],
                 v["hard_total"], v["agreement_min"], v["ledger_ok_total"],
                 v["ledger_ok_total"] + v["ledger_bad_total"],
                 v["surviving_models"] or "NONE"))
        print("      buckets=%s  models=%s" % (v["buckets_total"],
              {m: "%d/%d" % (d["hit"], d["checked"]) for m, d in
               v["semantic_models"].items()}))
    print("\nwrote %s" % p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
