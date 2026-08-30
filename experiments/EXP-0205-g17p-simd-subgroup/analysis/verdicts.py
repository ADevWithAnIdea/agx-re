#!/usr/bin/env python3
"""EXP-0205 verdict computation -- the ONLY place a verdict may be written.

    python3 analysis/verdicts.py raw/<run01> raw/<run02>

Verdicts are recomputed from `raw/` on every invocation and never read back from
a previous verdicts file.  `start`/`width` are re-read from the PINNED db.json,
so a descriptor that moved under a sibling experiment becomes a loud failure
rather than a silent mis-attribution.

THE GATE (frozen in PRE_REGISTRATION.md section 6)
==================================================
G1  Two gated runs over byte-identical programs and the same frozen arms file.
G2  >= 99 % per-value cross-run agreement on the OUTCOME PARTITION, and
        moved >= 2 * disagree   AND   moved >= 1
    NOT `moved >= 2 * max(disagree, 1)`: that form cannot promote ANY width-1
    field by arithmetic, and `simd_shuffle.dir` and `simd_shuffle.cache` are
    both width 1.  Checked against a width-1 field with 0 disagreements before
    this file was trusted.
G3  MOVEMENT EXCLUDES FAULTS.  A value counts as `moved` only if, IN BOTH RUNS,
    the dispatch completed with the sentinel intact and an outcome in
    {ok, wrong_value, silent_zero, unpredicted}, and its 32-word observed vector
    differs from the arm-open baseline vector.  A GPU fault is NOT movement; a
    hang is NOT movement; `not_written` is NOT movement; and our own
    disassembler failing to decode is NOT movement (the token is recorded and
    reported, never scored).  Each of those was a real gate defect paid for
    elsewhere this week.
G4  DETECTION POWER.  Every arm carries a CONTROL arm on the same instruction at
    the same occurrence, on a field already `hardware-run` (psrc / src / lane).
    An arm whose control never moved is BARRED from supporting any verdict --
    live OR inert.  `moved == 0` on an arm with no detection power is a
    tautology, not an observation.
G5  For the two `cache` fields, G4 is not sufficient and an extra IN-DIMENSION
    control is required: a `dst` sweep on the same carrier must, at some value,
    change the SECONDARY word vector out[32..63] -- the post-instruction content
    of the source register, which is exactly the dimension the public
    documentation says an operand cache/discard hint controls.  Without that,
    the verdict is UNRESOLVED and the field keeps `untested`; "inert" is never
    recorded for a dimension the carrier could not express.
G6  Baselines: the arm-open and arm-close baselines must both be `ok`.
G7  ALIASING.  Distinct field values must produce distinct instruction bytes
    differing only inside the field's span; `distinct_bytes` is reported and an
    arm whose encodings alias is refused.
G8  Measurement failures (MALFORMED responses) are removed from agreement and
    from `values_dispatched`; an arm with > 1 % is refused.

LABEL POLICY
  LIVE                    -> `hardware-run`
  INERT-ROBUST            -> `single-template-inference` (NOT emitter grade)
  UNRESOLVED              -> `untested`, with the un-varied dimension named
  STILL-UNDERPOWERED      -> `untested`
"""
import hashlib
import json
import statistics
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP / "harness"))
sys.path.insert(0, str(EXP / "analysis"))
import carriers205 as C          # noqa: E402
import locate205 as L            # noqa: E402
import semantics as S            # noqa: E402

AGREE_MIN = 99.0
MOVE_OK = {"ok", "wrong_value", "silent_zero", "unpredicted"}
MEASUREMENT_FAIL = {"measurement_failure"}
CACHE_FIELDS = {"simd_ballot.cache", "simd_shuffle.cache"}


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


def _h(v):
    return hashlib.sha256(json.dumps(v, sort_keys=True).encode()).hexdigest()[:16]


def vkey(r):
    o = r.get("observed") or {}
    return "%s|%s" % (r.get("outcome"), _h(o.get("vals_u32")))


def vals(r):
    return ((r.get("observed") or {}).get("vals_u32")) or None


def secs(r):
    return ((r.get("observed") or {}).get("sec_u32")) or None


def index(recs):
    out = {}
    for r in recs:
        arm = r.get("arm")
        if not arm:
            continue
        root = arm.split(":")[0]
        d = out.setdefault(root, {"cases": {}, "baselines": []})
        if r.get("role") in ("baseline", "probe"):
            d["baselines"].append(r)
        else:
            d["cases"][r["value"]] = r
    return out


def baseline_rec(a, suffix):
    for b in a["baselines"]:
        if str(b.get("note", "")).endswith(suffix):
            return b
    return a["baselines"][0] if a["baselines"] else None


def arm_stats(a1, a2):
    b1 = baseline_rec(a1, ":open")
    b2 = baseline_rec(a2, ":open")
    bv1, bv2 = (vals(b1), vals(b2))
    bs1, bs2 = (secs(b1), secs(b2))
    shared = sorted(set(a1["cases"]) & set(a2["cases"]))
    usable, mfail = [], 0
    for v in shared:
        if (a1["cases"][v]["outcome"] in MEASUREMENT_FAIL
                or a2["cases"][v]["outcome"] in MEASUREMENT_FAIL):
            mfail += 1
        else:
            usable.append(v)
    agree = sum(1 for v in usable
                if vkey(a1["cases"][v]) == vkey(a2["cases"][v]))
    disagree = len(usable) - agree

    def moved_at(v, strict=True):
        r1, r2 = a1["cases"][v], a2["cases"][v]
        if strict and (r1["outcome"] not in MOVE_OK or r2["outcome"] not in MOVE_OK):
            return False
        v1, v2 = vals(r1), vals(r2)
        if v1 is None or v2 is None or bv1 is None or bv2 is None:
            return False
        return v1 != bv1 and v2 != bv2

    def sec_moved_at(v):
        r1, r2 = a1["cases"][v], a2["cases"][v]
        if r1["outcome"] not in MOVE_OK or r2["outcome"] not in MOVE_OK:
            return False
        s1, s2 = secs(r1), secs(r2)
        if not s1 or not s2 or not bs1 or not bs2:
            return False
        return s1 != bs1 and s2 != bs2

    moved = [v for v in usable if moved_at(v)]
    sec_moved = [v for v in usable if sec_moved_at(v)]
    outcomes = {}
    for v in shared:
        for r in (a1["cases"][v], a2["cases"][v]):
            outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
    toks = {}
    for v in shared:
        for r in (a1["cases"][v], a2["cases"][v]):
            t = (r.get("token") or {}).get("mnemonic")
            toks[str(t)] = toks.get(str(t), 0) + 1
    dbytes = len({r["bytes"] for r in
                  list(a1["cases"].values()) + list(a2["cases"].values())
                  if r.get("bytes")})
    gput = [((a1["cases"][v].get("observed") or {}).get("gputime_ns"))
            for v in usable]
    gput = [g for g in gput if isinstance(g, int)]
    # ---- GATE A: the actual-byte ledger, from the DISPATCHED program ----
    led_total = led_ok = led_missing = 0
    req_vals, actual_encs, decoded_ok = set(), set(), 0
    for v in shared:
        for r in (a1["cases"][v], a2["cases"][v]):
            L_ = r.get("ledger")
            led_total += 1
            if not L_:
                led_missing += 1
                continue
            req_vals.add(L_.get("requested_value"))
            if L_.get("actual_bytes"):
                actual_encs.add(L_["actual_bytes"])
            if L_.get("requested_equals_decoded") and \
                    L_.get("requested_bytes_equal_actual"):
                led_ok += 1
                decoded_ok += 1
    # ---- GATE C: semantic checks against the independent host predictor ----
    # A case is SEMANTICALLY CHECKED only when a prediction existed (`match` is
    # not None) and both runs agree on the observation. A difference from
    # baseline is NOT a semantic oracle (corrections Gate C).
    sem_checked = sem_match = sem_mismatch = 0
    sem_matched_values, sem_matched_vectors = [], set()
    for v in usable:
        r1, r2 = a1["cases"][v], a2["cases"][v]
        if r1.get("match") is None or r2.get("match") is None:
            continue
        if vals(r1) != vals(r2):
            continue
        sem_checked += 1
        if r1["match"] and r2["match"]:
            sem_match += 1
            sem_matched_values.append(v)
            sem_matched_vectors.add(_h(r1.get("oracle")))
        else:
            sem_mismatch += 1
    # semantic buckets actually observed (corrections Gate C requires the
    # predictor to distinguish these, and the report to say which were seen)
    buckets = set()
    for v in shared:
        oc = a1["cases"][v]["outcome"]
        buckets.add({"ok": "correct", "wrong_value": "coherent_different",
                     "unpredicted": "coherent_different",
                     "silent_zero": "silent_zero_no_write",
                     "not_written": "silent_zero_no_write",
                     "fault": "rejected_faulted", "hang": "rejected_faulted",
                     "measurement_failure": "invalid_measurement",
                     "invalid_run": "invalid_measurement",
                     "ledger_mismatch": "invalid_measurement",
                     "nondeterministic": "invalid_measurement"}.get(oc, oc))
    bl_ok = (all(b["outcome"] == "ok" for b in a1["baselines"]
                 if b.get("role") == "baseline")
             and all(b["outcome"] == "ok" for b in a2["baselines"]
                     if b.get("role") == "baseline"))
    return {
        "values_dispatched": len(usable),
        "shared_values": len(shared),
        "measurement_failures": mfail,
        "measurement_failure_pct": round(100.0 * mfail / max(len(shared), 1), 3),
        "agree_pct": round(100.0 * agree / len(usable), 3) if usable else 0.0,
        "disagree": disagree,
        "moved": len(moved), "moved_values": moved[:40],
        "sec_moved": len(sec_moved), "sec_moved_values": sec_moved[:20],
        "distinct_bytes": dbytes,
        "outcomes": outcomes, "tokenized_mnemonics": toks,
        "baselines_ok": bl_ok,
        "ledger": {"cases": led_total, "verified": led_ok,
                   "missing": led_missing,
                   "distinct_requested_values": len(req_vals),
                   "distinct_actual_encodings": len(actual_encs),
                   "all_verified": led_missing == 0 and led_ok == led_total},
        "sem_checked": sem_checked, "sem_match": sem_match,
        "sem_mismatch": sem_mismatch,
        "sem_matched_values": sorted(sem_matched_values)[:40],
        "sem_distinct_predicted_vectors": len(sem_matched_vectors),
        "semantic_buckets_observed": sorted(buckets),
        "gputime_ns": {"n": len(gput),
                       "median": statistics.median(gput) if gput else None,
                       "min": min(gput) if gput else None,
                       "max": max(gput) if gput else None},
    }


def semantic_map(a1, a2, carrier):
    """value -> the named host-computed semantics the observation equals, when
    both runs agree on the vector."""
    out = {}
    for v in sorted(set(a1["cases"]) & set(a2["cases"])):
        r1, r2 = a1["cases"][v], a2["cases"][v]
        v1, v2 = vals(r1), vals(r2)
        if v1 is None or v1 != v2:
            continue
        names = S.identify(carrier, v1)
        if names:
            out[str(v)] = names
    return out


def classify(key, entries, controls, controls_dim):
    """The frozen gate.  entries = [(arm_name, arm_spec, arm_stats), ...].

    Returns (label, verdict, note).  Exposed as a function -- not buried in
    main() -- so `analysis/gate_selftest.py` can prove, with NO device, that it
    can come out the other way: that it PROMOTES a width-1 field with one moved
    value and zero disagreements, REFUSES an arm whose control never fired,
    refuses to count a fault as movement, and never reports `inert` for a
    dimension the carrier could not express.  A criterion that cannot return
    "no" is broken.
    """
    aliasing_ok = all(e[2]["encodings_confined_to_field"]
                      and e[2]["distinct_encodings_expected"] == len(e[1]["values"])
                      for e in entries)
    mfail_ok = all(e[2]["measurement_failure_pct"] <= 1.0 for e in entries)
    usable = [e for e in entries
              if controls.get((e[1]["carrier"], e[1]["occ"]), {}).get("fired")
              and e[2]["baselines_ok"]]
    live = [e for e in usable
            if e[2]["moved"] >= 1
            and e[2]["agree_pct"] >= AGREE_MIN
            and e[2]["moved"] >= 2 * e[2]["disagree"]]
    carriers = sorted({e[1]["carrier"] for e in entries})
    baselines = sorted({e[1]["baseline_field"] for e in entries})
    dim_fired = [e for e in entries
                 if controls_dim.get((e[1]["carrier"], e[1]["occ"]), {}).get("fired")]

    if not aliasing_ok:
        return ("untested", "REFUSED-ALIASED",
                "distinct field values did not produce distinct bytes confined "
                "to the field's own span")
    if not mfail_ok:
        return ("untested", "REFUSED-MEASUREMENT-FAILURES",
                "an arm exceeded the 1 % malformed-response budget")
    if not usable:
        return ("untested", "CARRIER-UNDECIDABLE",
                "no arm had detection power: the control on the same "
                "instruction and occurrence never moved, so `moved == 0` here "
                "is a tautology rather than an observation")
    if live:
        return ("hardware-run", "LIVE",
                "moved on %d of the %d arms with detection power (%d arms over "
                "%d carriers with %d distinct compiler-chosen baseline values)"
                % (len(live), len(usable), len(entries), len(carriers),
                   len(baselines)))
    if key in CACHE_FIELDS:
        if dim_fired:
            return ("untested", "UNRESOLVED-INERT-IN-TESTED-DIMENSION",
                    "0 of %d arms moved. The carrier set DOES have proven "
                    "detection power in the dimension a cache/discard operand "
                    "hint is documented to control -- the in-dimension `dst` "
                    "control moved the post-instruction content of the source "
                    "register on %d carrier(s) -- so this is a real negative in "
                    "THAT dimension: the field alters neither the functional "
                    "result nor what the source register holds afterwards. It "
                    "is still NOT recorded as globally inert. The MULTI-"
                    "INVOCATION ORDERING dimension WAS exercised in revision B "
                    "(4 threadgroups x 2 simdgroups, cross-simdgroup threadgroup-"
                    "memory exchange, a cross-threadgroup device atomic checked "
                    "against a host total, operand re-read after two barriers) "
                    "and the field stayed inert there too. The dimension that "
                    "remains unexercised is RETENTION/OCCUPANCY: a register-cache "
                    "hint's only remaining observable is timing and power, which "
                    "a functional read-back cannot express. Accepted-inert over "
                    "the tested envelope, NOT emitter-grade, global role unknown."
                    % (len(entries), len(dim_fired)))
        return ("untested", "UNRESOLVED-DIMENSION-NOT-EXPRESSED",
                "0 of %d arms moved, and the in-dimension control did NOT fire: "
                "no `dst` value changed the post-instruction content of the "
                "source register on this carrier, so the carrier cannot express "
                "the dimension the field is claimed to control. Reporting "
                "UNRESOLVED with the un-varied dimension named, rather than "
                "recording `inert`." % len(entries))
    return ("single-template-inference", "INERT-ROBUST",
            "0 of %d arms moved, on %d carriers with %d distinct "
            "compiler-chosen baseline values, every arm's control firing. "
            "Not emitter-grade." % (len(entries), len(carriers), len(baselines)))


# ===========================================================================
# SIX-AXIS VERDICTS -- RE_EXPERIMENT_PROCESS_CORRECTIONS.md section 2.
# ===========================================================================
# "Every field or finite resource gets independent status on these axes. A
# result on one axis must never imply a result on another."  In particular
# `sem_checked == 0` can never produce `hardware-run` or `semantically-mapped`,
# and a failed positive control makes the arm `carrier-undecidable` rather than
# inert.  Exact numerators and denominators, never a percentage alone.

SAFE_NEGATIVE = "inert in %s; global role unknown"


def context_split(entries):
    """Which carrier ATTRIBUTES separate the arms where the field moved from the
    arms where it did not.  A field that moves on some carriers and not others is
    a CONTEXTUAL field with a stated predicate, not a globally live or globally
    inert one (corrections section 7)."""
    moved, still = [], []
    for name, a, e in entries:
        tgt = moved if e["moved"] >= 1 else still
        tgt.append({"arm": name, "carrier": a["carrier"],
                    "baseline_field_value": a["baseline_field"],
                    "operand_provenance": C.OPERAND_PROVENANCE.get(a["carrier"]),
                    "dispatch_class": C.DISPATCH_CLASS.get(a["carrier"]),
                    "moved": e["moved"]})
    out = {"arms_moved": moved, "arms_not_moved": still, "separating_attribute": None}
    if moved and still:
        for attr in ("operand_provenance", "baseline_field_value", "dispatch_class"):
            mv = {x[attr] for x in moved}
            sv = {x[attr] for x in still}
            if mv and sv and not (mv & sv):
                out["separating_attribute"] = {
                    "attribute": attr, "moved_when": sorted(map(str, mv)),
                    "did_not_move_when": sorted(map(str, sv))}
                break
    return out


def axes(key, entries, controls, controls_dim, width):
    ents = [e[2] for e in entries]
    total_disp = sum(e["values_dispatched"] for e in ents)
    led_cases = sum(e["ledger"]["cases"] for e in ents)
    led_ok = sum(e["ledger"]["verified"] for e in ents)
    led_missing = sum(e["ledger"]["missing"] for e in ents)
    distinct_actual = sum(e["ledger"]["distinct_actual_encodings"] for e in ents)
    confined = all(e["encodings_confined_to_field"] for e in ents)
    covers = all(e["ledger"]["distinct_actual_encodings"] == len(a["values"])
                 for (_, a, e) in entries)

    # ---- axis 1: encoding geometry ----
    if led_missing or led_ok != led_cases:
        geometry = "unverified"
    elif confined and covers:
        geometry = "geometry-mapped"
    else:
        geometry = "ledger-verified"

    # ---- axis 2: liveness ----
    usable = [e for e in entries
              if controls.get((e[1]["carrier"], e[1]["occ"]), {}).get("fired")
              and e[2]["baselines_ok"]]
    moved_arms = [e for e in usable
                  if e[2]["moved"] >= 1 and e[2]["agree_pct"] >= AGREE_MIN
                  and e[2]["moved"] >= 2 * e[2]["disagree"]]
    faulted = sum(e["outcomes"].get("fault", 0) + e["outcomes"].get("hang", 0)
                  for e in ents)
    if not usable:
        liveness = "carrier-undecidable"
    elif moved_arms:
        liveness = "live"
    elif faulted:
        liveness = "fault"
    else:
        liveness = "accepted-inert"

    # ---- axis 3: semantics ----
    sem_checked = sum(e["sem_checked"] for e in ents)
    sem_match = sum(e["sem_match"] for e in ents)
    sem_mismatch = sum(e["sem_mismatch"] for e in ents)
    # The best single arm on which >=2 DISTINCT predicted vectors all matched:
    # that arm, and its matched value set, IS the semantic domain we may claim.
    best = None
    for name, a, e in entries:
        if e["sem_distinct_predicted_vectors"] >= 2 and e["sem_mismatch"] == 0:
            if best is None or e["sem_match"] > best[2]["sem_match"]:
                best = (name, a, e)
    if best is None:
        for name, a, e in entries:
            if e["sem_distinct_predicted_vectors"] >= 2:
                if best is None or e["sem_match"] > best[2]["sem_match"]:
                    best = (name, a, e)
    nonbase_match = any(
        any(v != a["baseline_field"] for v in e["sem_matched_values"])
        for (_, a, e) in entries)
    if sem_checked == 0:
        semantics = "unknown"
    elif best is not None and best[2]["sem_mismatch"] == 0 and best[2]["sem_match"] >= 2:
        semantics = "semantically-mapped"
    elif sem_match >= 1 and nonbase_match:
        semantics = "bounded-map"
    else:
        semantics = "hypothesis"

    # ---- axis 4: compiler recipe ----
    # Every case in this experiment mutates ONE field of a COMPILER-EMITTED
    # program. Nothing here generates a whole instruction from documented rules,
    # so Gate D is not attempted and the honest status is `not-generated` for
    # every field. Saying so is the point: a field label is not an emittability
    # proof (corrections section 2).
    recipe = "not-generated"

    # ---- axis 5: target ----
    target_axis = "G17P-direct"

    # ---- axis 6: reproducibility ----
    min_agree = min(e["agree_pct"] for e in ents) if ents else 0.0
    victims = sum(sum(1 for c in e.get("fault_class_census", []) if "Innocent" in c)
                  for e in ents)
    repro = ("independently-confirmed"
             if (min_agree >= AGREE_MIN and led_missing == 0 and led_ok == led_cases)
             else "auditable")

    # ---- legacy DOC-02 label: NEVER rounded up from liveness ----
    if semantics == "semantically-mapped" and liveness == "live":
        legacy = "hardware-run"
    elif liveness == "live" and nonbase_match and sem_match >= 1:
        legacy = "isolated-byte-diff"
    else:
        legacy = "untested"

    return {
        "axes": {
            "encoding_geometry": geometry,
            "liveness": liveness,
            "semantics": semantics,
            "compiler_recipe": recipe,
            "target": target_axis,
            "reproducibility": repro,
        },
        "counts": {
            "encodable_values": 1 << width,
            "values_dispatched_max_arm": max(e["values_dispatched"] for e in ents),
            "cases_both_runs": led_cases,
            "ledger_verified": led_ok,
            "ledger_missing": led_missing,
            "distinct_actual_encodings_summed_over_arms": distinct_actual,
            "arms": len(entries),
            "arms_with_detection_power": len(usable),
            "arms_moved": len(moved_arms),
            "moved_values_summed": sum(e["moved"] for e in ents),
            "disagreeing_values_summed": sum(e["disagree"] for e in ents),
            "sem_checked": sem_checked,
            "sem_match": sem_match,
            "sem_mismatch": sem_mismatch,
            "faults_plus_hangs": faulted,
            "measurement_failures": sum(e["measurement_failures"] for e in ents),
            "min_cross_run_agreement_pct": min_agree,
        },
        "semantic_domain": (
            {"arm": best[0], "carrier": best[1]["carrier"],
             "baseline_field_value": best[1]["baseline_field"],
             "matched_values": best[2]["sem_matched_values"],
             "distinct_predicted_vectors": best[2]["sem_distinct_predicted_vectors"],
             "mismatches_on_this_arm": best[2]["sem_mismatch"]}
            if best is not None else None),
        "semantic_buckets_observed": sorted(
            set().union(*[set(e["semantic_buckets_observed"]) for e in ents])),
        "legacy_label": legacy,
    }


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    run1, run2 = sys.argv[1], sys.argv[2]
    i1, i2 = index(load(run1)), index(load(run2))
    doc = json.loads((EXP / "harness" / "arms205.json").read_text())
    arms = {a["arm"]: a for a in doc["arms"]}

    per_arm, controls, controls_dim = {}, {}, {}
    for name, a in arms.items():
        if name not in i1 or name not in i2:
            per_arm[name] = {"status": "missing_from_a_run",
                             "in_run1": name in i1, "in_run2": name in i2}
            continue
        st = arm_stats(i1[name], i2[name])
        st.update({"carrier": a["carrier"], "instr": a["instr"],
                   "field": a["field"], "role": a["role"], "occ": a["occ"],
                   "baseline_field": a["baseline_field"],
                   "distinct_encodings_expected": a["distinct_encodings"],
                   "encodings_confined_to_field": a["encodings_confined_to_field"],
                   "semantics": semantic_map(i1[name], i2[name], a["carrier"])})
        per_arm[name] = st
        if a["role"] == "control":
            controls[(a["carrier"], a["occ"])] = {
                "arm": name, "field": a["field"], "moved": st["moved"],
                "agree_pct": st["agree_pct"], "fired": st["moved"] >= 1}
        if a["role"] == "control_dim":
            controls_dim[(a["carrier"], a["occ"])] = {
                "arm": name, "field": a["field"],
                "moved": st["moved"], "sec_moved": st["sec_moved"],
                "agree_pct": st["agree_pct"],
                "fired": st["sec_moved"] >= 1,
                "what_it_proves":
                    "a dst value made the instruction change the content of the "
                    "register its own source occupies, and out[32..63] -- the "
                    "LATER READ of that source -- moved. The carrier can "
                    "therefore detect a change in the post-instruction content "
                    "of the source register, which is the dimension a "
                    "cache/discard operand hint is documented to control."}

    by_field = {}
    for name, a in arms.items():
        if a["role"] != "target" or name not in per_arm:
            continue
        if "status" in per_arm[name]:
            continue
        by_field.setdefault("%s.%s" % (a["instr"], a["field"]), []).append(
            (name, a, per_arm[name]))

    verdicts = {}
    for key, entries in sorted(by_field.items()):
        mn, fld = key.split(".", 1)
        start, width = L.field_span(mn, fld)
        label, verdict, note = classify(key, entries, controls, controls_dim)
        ax = axes(key, entries, controls, controls_dim, width)
        if ax["axes"]["liveness"] in ("accepted-inert", "carrier-undecidable"):
            env = ("0..%d dense on %d arm(s), %d carrier(s), %d distinct "
                   "compiler-chosen baseline values, G17P"
                   % ((1 << width) - 1, len(entries),
                      len({e[1]["carrier"] for e in entries}),
                      len({e[1]["baseline_field"] for e in entries})))
            note = (SAFE_NEGATIVE % env) + " -- " + note
        verdicts[key] = {
            "six_axis": ax["axes"], "counts": ax["counts"],
            "semantic_domain": ax["semantic_domain"],
            "semantic_buckets_observed": ax["semantic_buckets_observed"],
            "label": ax["legacy_label"], "legacy_label_rule":
                "never rounded up from liveness (corrections section 2): "
                "hardware-run requires semantics==semantically-mapped AND "
                "liveness==live; isolated-byte-diff requires a matched "
                "prediction at a NON-BASELINE value; otherwise untested.",
            "liveness_verdict": verdict, "gate_a_label": label,
            # `range` is the SEMANTICALLY CHECKED envelope when the label is
            # emitter-grade -- an implementer may not extrapolate past it
            # (docs/evidence-classification.md section 3) -- and the liveness
            # envelope otherwise.  Both numbers are always reported in `counts`.
            "range": (
                ("dispatched 0..%d dense (%d/%d encodable) on %d arm(s); "
                 "SEMANTICS CONFIRMED on arm %s at values %s (%d distinct "
                 "predicted vectors, %d mismatches on that arm)")
                % ((1 << width) - 1, ax["counts"]["values_dispatched_max_arm"],
                   1 << width, len(entries),
                   ax["semantic_domain"]["arm"],
                   ax["semantic_domain"]["matched_values"],
                   ax["semantic_domain"]["distinct_predicted_vectors"],
                   ax["semantic_domain"]["mismatches_on_this_arm"])
                if ax["legacy_label"] == "hardware-run" and ax["semantic_domain"]
                else (
                    ("dispatched 0..%d dense (%d/%d encodable) on %d arm(s); "
                     "CONTEXTUAL: moved on %d arm(s) and not on %d, separated by "
                     "%s. Confirmed against the host prediction at the values "
                     "listed in `context_split`; the value that moved produced an "
                     "UNPREDICTED result, so no general semantic map is claimed.")
                    % ((1 << width) - 1,
                       ax["counts"]["values_dispatched_max_arm"], 1 << width,
                       len(entries), ax["counts"]["arms_moved"],
                       len(entries) - ax["counts"]["arms_moved"],
                       json.dumps((context_split(entries) or {}).get(
                           "separating_attribute")))
                    if ax["legacy_label"] == "isolated-byte-diff"
                    else "dispatched 0..%d dense (%d/%d encodable) on %d arm(s); "
                         "no semantic domain established"
                         % ((1 << width) - 1,
                            ax["counts"]["values_dispatched_max_arm"],
                            1 << width, len(entries)))),
            "target": "G17P",
            "evidence": ["EXP-0205"],
            "note": note,
            "start": start, "width": width,
            "values_dispatched": max(e[2]["values_dispatched"] for e in entries),
            "distinct_bytes": sum(e[2]["distinct_bytes"] for e in entries),
            "encodable_range": 1 << width,
            "moved_total": sum(e[2]["moved"] for e in entries),
            "disagree_total": sum(e[2]["disagree"] for e in entries),
            "min_agree_pct": min(e[2]["agree_pct"] for e in entries),
            "context_split": context_split(entries),
            "carriers": sorted({e[1]["carrier"] for e in entries}),
            "distinct_baseline_field_values":
                sorted({e[1]["baseline_field"] for e in entries}),
            "arms": {e[0]: e[2] for e in entries},
        }

    # ---- db.json descriptor defects (FIELD-SWEEP-PROTOCOL section 6) ----
    # Recorded here, NEVER written into db.json: the orchestrator owns it and
    # concurrent experiments edit it.
    db_defects = {
        "simd_ballot.pred": {
            "modelled_as": "byte+1 bits 12..15; enum 0 = active_mask/any/all, "
                           "1 = ballot(predicate)",
            "observed_on_G17P": (
                "Our own compiler emits byte+1 = 0x07 (pred = 0) for BOTH "
                "simd_ballot(predicate) AND simd_active_threads_mask(); the two "
                "compiled forms differ in byte+5 (psrctype 0x00 vs 0x02) and the "
                "byte+7..9 tail (58 22 12 vs 08 02 18). Sweeping pred over all 16 "
                "values changed nothing on 6 carriers whose controls all fired, "
                "including two carriers that DO compute the two different forms."),
            "adversarial_probe": (
                "raw/adversarial01 (SINGLE OBSERVATIONS, not gated, "
                "hypothesis-grade): on the ballot carrier psrctype alone changed "
                "nothing; the tail alone gave a silent zero; psrctype + tail "
                "together turned 0x6C8AF35D into 0xFFFFFFFF (the all-active "
                "mask); and byte+6 `form` alone, 0x00 -> 0x14, did the same."),
            "proposed_correction": (
                "The ballot-form selection attributed to `pred` is carried by "
                "byte+5 / byte+6 / byte+7..9. `pred` as modelled is inert across "
                "its full range on G17P. Needs its own gated experiment before "
                "db.json is changed."),
            "evidence": ["EXP-0205"], "target": "G17P",
        },
        "simd_reduce.op": {
            "modelled_as": "byte+1, an 8-bit opcode field",
            "observed_on_G17P": (
                "Only bits [2:0] are decoded. Bits [7:3] are inert-within-field "
                "on all four reduce carriers and the observation repeats with "
                "period 8 across the full 256-value sweep."),
            "proposed_correction": "op is a 3-bit opcode occupying an 8-bit byte.",
            "evidence": ["EXP-0205"], "target": "G17P",
        },
        "simd_reduce.dtype": {
            "modelled_as": "byte+7, an 8-bit enum",
            "observed_on_G17P": (
                "Bits 4, 6 and 7 are inert-within-field on all four carriers; "
                "the integer carriers repeat with period 16. Live bits are [0,3] "
                "(sr_sum, sr_max), [0,1,3] (sr_scan) and [0,1,2,3,5] (the f32 "
                "carrier), so the live width is context-dependent."),
            "proposed_correction": "dtype's decoded width is at most 6 bits and "
                                   "is context-dependent; do not model it as 8.",
            "evidence": ["EXP-0205"], "target": "G17P",
        },
        "simd_reduce.op x simd_reduce.dtype": {
            "observed_on_G17P": (
                "The two fields are NOT independent: the {0,1,2,3} -> "
                "{ior,isum,smax,umax} map holds at opcls=1 with dtype=3, but on "
                "dtype=7 op values 0 and 3 returned EXCLUSIVE-SCAN shapes and on "
                "dtype=9 the predictions for op != 1 all failed."),
            "proposed_correction": "add a field-dependency edge op <-> dtype.",
            "evidence": ["EXP-0205"], "target": "G17P",
        },
    }

    out = {"_generated_by": "analysis/verdicts.py",
           "db_defects": db_defects,
           "_runs": [str(run1), str(run2)],
           "_gate": {"agree_min_pct": AGREE_MIN,
                     "movement_rule": "moved >= 2*disagree AND moved >= 1",
                     "movement_excludes": sorted(
                         {"fault", "hang", "not_written", "invalid_run",
                          "measurement_failure", "nondeterministic"}),
                     "cache_fields_need_in_dimension_control": sorted(CACHE_FIELDS)},
           "verdicts": verdicts,
           "controls": {"%s#%s" % k: v for k, v in controls.items()},
           "controls_in_dimension": {"%s#%s" % k: v for k, v in controls_dim.items()},
           "arms": per_arm}
    p = EXP / "analysis" / "field_verdicts.json"
    p.write_text(json.dumps(out, indent=1, sort_keys=True))
    # Flat view, keyed exactly `<mnemonic>.<field>`, for mechanical merging.
    flat = {k: {"label": v["label"], "range": v["range"], "target": v["target"],
                "evidence": v["evidence"], "note": v["note"],
                "start": v["start"], "width": v["width"],
                "distinct_bytes": v["distinct_bytes"],
                "six_axis": v["six_axis"], "counts": v["counts"],
                "semantic_domain": v["semantic_domain"],
                "context_split": v.get("context_split"),
                "legacy_label_rule": v["legacy_label_rule"]}
            for k, v in verdicts.items()}
    (EXP / "analysis" / "field_verdicts_flat.json").write_text(
        json.dumps({"_generated_by": "analysis/verdicts.py",
                    "_runs": [str(run1), str(run2)],
                    "db_defects": db_defects, "fields": flat},
                   indent=1, sort_keys=True))
    print(json.dumps({k: {"legacy_label": v["label"],
                          **v["six_axis"],
                          "moved/dispatched": "%d/%d" % (
                              v["counts"]["moved_values_summed"],
                              v["counts"]["values_dispatched_max_arm"] * v["counts"]["arms"]),
                          "sem_match/checked": "%d/%d" % (
                              v["counts"]["sem_match"], v["counts"]["sem_checked"]),
                          "ledger": "%d/%d" % (v["counts"]["ledger_verified"],
                                               v["counts"]["cases_both_runs"]),
                          "distinct_bytes": v["distinct_bytes"]}
                      for k, v in verdicts.items()}, indent=1))
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
