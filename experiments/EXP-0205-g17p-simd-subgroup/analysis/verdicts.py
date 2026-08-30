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
        return ("untested", "STILL-UNDERPOWERED",
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
                    "is still NOT recorded as inert. The dimension we could not "
                    "vary is RETENTION/OCCUPANCY: a register-cache hint's only "
                    "remaining observable is timing and power, which a "
                    "functional read-back cannot express. UNRESOLVED, not "
                    "inert, and not emitter-grade."
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
        verdicts[key] = {
            "label": label, "verdict": verdict,
            "range": "0..%d dense (all %d values), %d arm(s)"
                     % ((1 << width) - 1, 1 << width, len(entries)),
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
            "carriers": sorted({e[1]["carrier"] for e in entries}),
            "distinct_baseline_field_values":
                sorted({e[1]["baseline_field"] for e in entries}),
            "arms": {e[0]: e[2] for e in entries},
        }

    out = {"_generated_by": "analysis/verdicts.py",
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
    print(json.dumps({k: {"label": v["label"], "verdict": v["verdict"],
                          "moved": v["moved_total"],
                          "agree": v["min_agree_pct"],
                          "distinct_bytes": v["distinct_bytes"]}
                      for k, v in verdicts.items()}, indent=1))
    print("wrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
