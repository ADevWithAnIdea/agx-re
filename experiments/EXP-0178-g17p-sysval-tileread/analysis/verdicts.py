#!/usr/bin/env python3
"""EXP-0178 verdicts -> analysis/field_verdicts.json (FIELD-SWEEP-PROTOCOL §5).

Flat `<mnemonic>.<field>` keys. Labels come from docs/evidence-classification.md
§2 and NOTHING else. A dishonest label becomes someone else's silent-zero bug.

Promotion gate (frozen in CAPTURE_CONTRACT.json):
  gate_zero  the arm's liveness LADDER passed and its power probe landed;
             otherwise the arm has no demonstrated detection power and every
             reading from it -- live OR inert -- stays `untested`.
  agreement  >= 99.0 % per-VALUE cross-run outcome agreement.
  movement   moved >= 2.0 x the number of disagreeing values.
  common     >= 2 values present in both runs.
  coverage   `hardware-run` additionally requires the field's FULL encodable
             range for w <= 8 (or the protocol's boundary+power-of-two+interior
             set for w > 8). Otherwise the ceiling is `isolated-byte-diff`.
  never-move a field that never moved is promotable ONLY if the carriers differ
             in the dimension the field controls. Where that dimension is
             unknown -- which is the case for every `raw`-typed byte here -- the
             verdict is `untested` with the reason recorded, never "inert".

`distinct_bytes` counts DISTINCT spliced byte strings, never the dispatched
value count.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))

MIN_AGREE_PCT = 99.0
MOVED_OVER_DISAGREE = 2.0
MIN_COMMON = 2

LABELS = {"hardware-run", "isolated-byte-diff", "corpus-correlation",
          "tokenization-only", "single-template-inference", "api-accept-reject",
          "host-private", "untested"}


MAX_MEASUREMENT_FAILED_FRAC = 0.01

# Outcomes that are NOT OBSERVATIONS about the encoding and must never be scored
# as one -- not as `ok`, not as `fault`, and not as an inertness reading:
#   measurement_failed  a malformed/unparseable runner response (DEF-0178-1)
#   invalid_run         collateral damage from ANOTHER context's error or its
#                       recovery -- `kIOGPUCommandBufferCallbackErrorInnocentVictim`
#                       / "Discarded (victim of GPU error/recovery)" / "Ignored (for
#                       causing prior/excessive GPU errors)". A device reset
#                       discards in-flight command buffers in every context, so a
#                       victim says something about the MACHINE, never about our
#                       bytes. FIELD-SWEEP-PROTOCOL section 7.
# Both are removed from the agreement computation AND from `values_dispatched`,
# and both keep their raw (the OS fault-class string in `victim`, the response
# lines in `raw_lines`).
NON_OBSERVATIONS = ("measurement_failed", "invalid_run")


def gate(rows1, rows2, ladder_ok):
    """The frozen promotion gate. rows are per-case dicts with value/outcome/moved.

    DEF-0178-1: `measurement_failed` cases are NOT OBSERVATIONS -- a malformed or
    unparseable runner response says nothing about the encoding. They are removed
    from the agreement computation rather than counted as agreement (which would
    inflate the percentage) or as disagreement (which would penalise the field for
    a harness problem), AND the count is reported. A field whose measurement
    failures exceed 1% of the dispatched values is REFUSED, because its null
    result would be sitting on top of a measurement problem."""
    a = {r["value"]: r for r in rows1}
    b = {r["value"]: r for r in rows2}
    nmf = sum(1 for r in list(rows1) + list(rows2)
              if r["outcome"] == "measurement_failed")
    nvic = sum(1 for r in list(rows1) + list(rows2)
               if r["outcome"] == "invalid_run")
    for d in (a, b):
        for v in [v for v, r in d.items() if r["outcome"] in NON_OBSERVATIONS]:
            del d[v]
    common = sorted(set(a) & set(b))
    agree = [v for v in common if a[v]["outcome"] == b[v]["outcome"]]
    disagree = [v for v in common if a[v]["outcome"] != b[v]["outcome"]]
    moved = [v for v in agree if a[v].get("moved") and b[v].get("moved")]
    pct = (100.0 * len(agree) / len(common)) if common else 0.0
    ok_common = len(common) >= MIN_COMMON
    ok_pct = pct >= MIN_AGREE_PCT
    ok_move = len(moved) >= MOVED_OVER_DISAGREE * max(len(disagree), 1) and len(moved) > 0
    ndispatched = len(rows1) + len(rows2)
    ok_mf = (nmf <= MAX_MEASUREMENT_FAILED_FRAC * ndispatched) if ndispatched else True
    return {
        "promote": bool(ladder_ok and ok_common and ok_pct and ok_move and ok_mf),
        "ladder_ok": bool(ladder_ok),
        "common_values": len(common), "agree": len(agree),
        "disagree": len(disagree), "moved": len(moved),
        "measurement_failed": nmf, "invalid_run_victims": nvic,
        "agreement_pct": round(pct, 3),
        "failed": [k for k, v in (("gate_zero_ladder", ladder_ok),
                                  ("min_common_values", ok_common),
                                  ("min_agree_pct", ok_pct),
                                  ("moved_over_disagree", ok_move),
                                  ("measurement_failures", ok_mf)) if not v],
    }


def load(rundir):
    recs = []
    with open(os.path.join(rundir, "sweep.jsonl")) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                recs.append(json.loads(ln))
    return recs


def build(run1, run2):
    r1, r2 = load(run1), load(run2)
    meta = {}
    for recs in (r1, r2):
        for r in recs:
            if r.get("kind") == "arm_meta":
                meta[r["arm"]] = r

    def ladder_state(recs):
        st = collections.defaultdict(lambda: {"ladder": [], "power": [], "sens": []})
        base = {}
        for r in recs:
            if r.get("kind") == "baseline":
                base[r["arm"]] = r
            elif r.get("kind") == "ladder":
                st[r["arm"]]["ladder"].append(r)
            elif r.get("kind") == "power_probe":
                st[r["arm"]]["power"].append(r)
            elif r.get("kind") == "sensitivity":
                st[r["arm"]]["sens"].append(r)
        return st, base

    s1, _ = ladder_state(r1)
    s2, _ = ladder_state(r2)

    def arm_ladder_ok(arm):
        out = {}
        for tag, s in (("run01", s1), ("run02", s2)):
            L = s[arm]["ladder"]
            P = s[arm]["power"]
            S = s[arm]["sens"]
            out[tag] = {
                "ladder_steps": len(L),
                "ladder_all_moved": bool(L) and all(x.get("moved") for x in L),
                "power_probe_landed": bool(P) and all(
                    x["outcome"] in ("ok", "silent_zero") or x.get("moved") for x in P),
                "sensitivity_failed_as_preregistered": bool(S) and all(
                    (x.get("moved") is True) or x["outcome"] in
                    ("fault", "hang", "no_draw", "no_dispatch") for x in S),
            }
        ok = all(v["ladder_all_moved"] and v["sensitivity_failed_as_preregistered"]
                 for v in out.values())
        return ok, out

    cases = collections.defaultdict(lambda: collections.defaultdict(list))
    for tag, recs in (("run01", r1), ("run02", r2)):
        for r in recs:
            if r.get("kind") != "case":
                continue
            cases[(r["instr"], r["field"], r["arm"])][tag].append(r)

    per_field = collections.defaultdict(dict)
    for (instr, field, arm), byrun in cases.items():
        per_field[(instr, field)][arm] = byrun

    out = {}
    for (instr, field), arms in sorted(per_field.items()):
        key = "%s.%s" % (instr, field)
        entries, best = {}, None
        anyforeign = False
        for arm, byrun in sorted(arms.items()):
            rows1, rows2 = byrun.get("run01", []), byrun.get("run02", [])
            anyforeign = anyforeign or any(r.get("foreign") for r in rows1 + rows2)
            lok, ldet = arm_ladder_ok(arm)
            g = gate(rows1, rows2, lok)
            g["ladder_detail"] = ldet
            obs1 = [r for r in rows1 if r["outcome"] not in NON_OBSERVATIONS]
            g["values_dispatched"] = len({r["value"] for r in obs1})
            g["distinct_bytes"] = len({r["bytes"] for r in obs1})
            g["values_attempted"] = len({r["value"] for r in rows1})
            g["non_observations_run01"] = len(rows1) - len(obs1)
            g["encodable_range"] = (rows1 or rows2)[0].get("encodable_range")
            g["start"] = (rows1 or rows2)[0].get("start")
            g["width"] = (rows1 or rows2)[0].get("width")
            g["outcomes_run01"] = dict(collections.Counter(r["outcome"] for r in rows1))
            g["outcomes_run02"] = dict(collections.Counter(r["outcome"] for r in rows2))
            g["hangs"] = sum(1 for r in rows1 + rows2 if r["outcome"] == "hang")
            entries[arm] = g
            if best is None or (g["promote"], g["common_values"]) > \
                              (entries[best]["promote"], entries[best]["common_values"]):
                best = arm
        b = entries[best]
        full = (b["width"] is not None and b["width"] <= 8 and
                b["values_dispatched"] == b["encodable_range"])
        if anyforeign:
            label, note = "untested", ("SWEPT AND RECORDED BUT NOT RULED ON: another "
                                       "experiment owns this field name.")
        elif b["promote"]:
            label = "hardware-run" if full else "isolated-byte-diff"
            note = ""
        elif b["moved"] == 0 and not b["failed"]:
            label, note = "untested", (
                "never moved on %d carrier(s). A never-moving field is promotable "
                "only if the carriers differ in the dimension the field controls; "
                "that dimension is unknown for this field, so this is reported as "
                "a limit of the carriers, NOT as `inert`." % len(entries))
        else:
            label, note = "untested", "gate failed: " + ", ".join(b["failed"])
        assert label in LABELS
        out[key] = {
            "label": label, "target": "G17P",
            "range": "%d of %d encodable values, %d distinct byte strings, "
                     "%d carrier(s)" % (b["values_dispatched"], b["encodable_range"],
                                        b["distinct_bytes"], len(entries)),
            "evidence": ["EXP-0178"],
            "values_dispatched": b["values_dispatched"],
            "distinct_bytes": b["distinct_bytes"],
            "encodable_range": b["encodable_range"],
            "start": b["start"], "width": b["width"],
            "carriers": sorted(entries), "best_carrier": best,
            "gate": {k: v for k, v in entries.items()},
            "note": note,
        }
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run01", required=True)
    ap.add_argument("--run02", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "field_verdicts.json"))
    a = ap.parse_args()
    d = build(a.run01, a.run02)
    json.dump(d, open(a.out, "w"), indent=1, sort_keys=True)
    print(json.dumps({k: v["label"] for k, v in sorted(d.items())}, indent=1))
