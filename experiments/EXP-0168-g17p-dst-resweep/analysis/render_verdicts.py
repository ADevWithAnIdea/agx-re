#!/usr/bin/env python3
"""render_verdicts.py -- EXP-0168 RENDER-arm verdicts, derived from the raw.

    python3 analysis/render_verdicts.py raw/g17p_YYYYMMDD_run01 [raw/..._run02 ...]
    python3 analysis/render_verdicts.py --md raw/...            # markdown tables

Reads only the append-only `sweep.jsonl` of each run directory plus its
`00_inputs.json` / `05_run_manifest.json`, and recomputes EVERYTHING -- the
detection gate included.  The in-run `ladder_pass` summary is NOT trusted:
EXP-0163 lost exactly this by trusting its in-run predicate, which scored a
FAULTED control as a live control because its comparison required both statuses
to be OK.  Here the gate is recomputed from the records:

    a control counts as LIVE only if the case was status OK, `validity ==
    "valid"`, `accepted`, and the patched bytes still decode as the control's own
    mnemonic -- and the arm needs >= 2 distinct observed surface hashes among
    such cases.

THE VERDICT RULES, stated so they cannot drift:

  eligible arm      = baseline OK, ladder PASSED, >= 1 falsifier HELD, the
                      dense sweep COMPLETE, and carrier_dim not `secondary:`
  LIVE              = >= 1 eligible arm where the field moved an observation
  INERT-ROBUST      = 0 movement, on >= 3 DISTINCT carrier_dim values
  STILL-UNDERPOWERED= 0 movement, fewer than 3 distinct carrier_dim values
  LADDER-FAILED     = no arm could demonstrate detection power

Labels use only the eight from docs/evidence-classification.md:
LIVE -> `hardware-run`; INERT-ROBUST -> `single-template-inference` (a negative
result must never inflate the emittable count -- EXP-0163's reasoning, adopted
verbatim); STILL-UNDERPOWERED / LADDER-FAILED -> `untested`.

CLEAN-ROOM: pure analysis of our own captured data.  No Apple binary is touched.
"""
import argparse
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(EXP, "harness"))

import renderarms as RA          # noqa: E402
import rendercarriers as RC      # noqa: E402

MOVED_OUTCOMES = ("wrong_value", "silent_zero", "moved", "undecodable")
ORDER_FAIL = ("lost_", "applied_", "inconsistent", "no_draw")


def load(runs):
    recs = collections.defaultdict(list)      # run_id -> [record]
    meta = {}
    for d in runs:
        rid = os.path.basename(d.rstrip("/"))
        p = os.path.join(d, "sweep.jsonl")
        if not os.path.exists(p):
            sys.exit("no sweep.jsonl in %s" % d)
        for ln in open(p):
            ln = ln.strip()
            if ln:
                recs[rid].append(json.loads(ln))
        m = {}
        for f in ("00_inputs.json", "05_run_manifest.json"):
            q = os.path.join(d, f)
            if os.path.exists(q):
                m[f] = json.load(open(q))
        meta[rid] = m
    return recs, meta


def accepted_valid(r):
    return r.get("accepted") and r.get("validity") == "valid"


# ---------------------------------------------------------------------------
# detection gate, recomputed
# ---------------------------------------------------------------------------
def ladder_gate(rs):
    """Per arm: which ladders demonstrated >= 2 distinct hashes under the STRICT
    rule, and which merely produced faults."""
    out = {}
    for r in rs:
        if r["role"] != "ladder":
            continue
        arm, lid = r["arm"], r["field"].split(":", 1)[0]
        e = out.setdefault(arm, {}).setdefault(
            lid, {"hashes": set(), "n": 0, "faults": 0, "skipped": None,
                  "moved": 0, "hazard": r.get("hazard", "low")})
        obs = r.get("observed", {})
        if obs.get("status") == "UNAVAILABLE":
            e["skipped"] = r.get("note", "")[:160]
            continue
        if not accepted_valid(r):
            continue
        e["n"] += 1
        if obs.get("status") != "OK":
            e["faults"] += 1
            continue
        note = r.get("note", "")
        # STRICT: the patched bytes must still decode as the control's own
        # mnemonic.  `renderrun.py` records `redecodes_as=<mnemonic>` in `note`.
        if "redecodes_as=" in note:
            dm = note.split("redecodes_as=", 1)[1].split()[0].strip()
            if dm != r["instr"]:
                continue
        e["hashes"].add(json.dumps(obs.get("hh"), sort_keys=True))
        if r.get("outcome") == "moved":
            e["moved"] += 1
    for arm, ls in out.items():
        for lid, e in ls.items():
            e["distinct_hashes"] = len(e.pop("hashes"))
            e["pass"] = e["distinct_hashes"] >= RA.LADDER_MIN_DISTINCT_HASHES
    return out


def falsifier_gate(rs):
    out = {}
    for r in rs:
        if r["role"] != "falsifier":
            continue
        fid = r["field"].split(":", 1)[0]
        out.setdefault(r["arm"], {})[fid] = {
            "outcome": r.get("outcome"), "predict": r.get("predict"),
            "held": r.get("outcome") == "falsifier_held",
            "available": r.get("observed", {}).get("status") != "UNAVAILABLE"}
    return out


# ---------------------------------------------------------------------------
# bit rules
# ---------------------------------------------------------------------------
def bit_rule(v2class, width):
    """Which bits of the field actually matter, and is the class a FUNCTION of
    exactly those bits?  Same shape as EXP-0163's analysis/rules.py."""
    live = []
    for b in range(width):
        m = 1 << b
        for v, c in v2class.items():
            w = v ^ m
            if w in v2class and v2class[w] != c:
                live.append(b)
                break
    mask = 0
    for b in live:
        mask |= 1 << b
    f, functional = {}, True
    for v, c in v2class.items():
        k = v & mask
        if k in f and f[k] != c:
            functional = False
        f[k] = c
    return {"live_bits": live, "mask": mask,
            "class_is_function_of_live_bits": functional,
            "n_classes": len(set(v2class.values()))}


def describe(v2class, width, baseline_class):
    """A human rule for the baseline-reproducing set, when one is expressible."""
    keep = sorted(v for v, c in v2class.items() if c == baseline_class)
    if not keep or len(keep) == len(v2class):
        return None
    always_set = (1 << width) - 1
    always_clear = (1 << width) - 1
    for v in keep:
        always_set &= v
        always_clear &= ~v & ((1 << width) - 1)
    pred = [v for v in v2class
            if (v & always_set) == always_set and (v & always_clear) == 0]
    exact = sorted(pred) == keep
    return {"always_set_mask": always_set, "always_clear_mask": always_clear,
            "exact": exact, "n_keep": len(keep)}


# ---------------------------------------------------------------------------
def per_arm_field(rs):
    """(arm, field) -> stats over ACCEPTED VALID sweep records."""
    out = {}
    for r in rs:
        if r["role"] != "sweep":
            continue
        if r["field"].startswith("_"):
            out.setdefault((r["arm"], r["field"]), {"markers": []})["markers"] \
                .append({"outcome": r.get("outcome"), "note": r.get("note", "")[:200]})
            continue
        key = (r["arm"], r["field"])
        e = out.setdefault(key, {
            "instr": r["instr"], "carrier": r["carrier"],
            "carrier_dim": r["carrier_dim"], "byte_index": r["byte_index"],
            "fstart": r["fstart"], "fwidth": r["fwidth"],
            "n": 0, "moved": 0, "ok": 0, "faults": 0, "hangs": 0,
            "invalid_seen": 0, "v2class": {}, "v2outcome": {},
            "predict_n": 0, "predict_held": 0, "markers": []})
        if not accepted_valid(r):
            e["invalid_seen"] += 1
            continue
        e["n"] += 1
        oc = r.get("outcome")
        e["v2outcome"][r["value"]] = oc
        obs = r.get("observed", {})
        e["v2class"][r["value"]] = (json.dumps(obs.get("hh"), sort_keys=True)
                                    if obs.get("status") == "OK" else "!" + str(oc))
        if oc == "ok":
            e["ok"] += 1
        elif oc == "hang":
            e["hangs"] += 1
        elif oc == "fault":
            e["faults"] += 1
        elif oc in MOVED_OUTCOMES or any(oc.startswith(p) for p in ORDER_FAIL):
            e["moved"] += 1
        if r.get("predict") is not None:
            e["predict_n"] += 1
            if r.get("predict_held"):
                e["predict_held"] += 1
    # attach markers (FIELD_STOPPED / ARM_STOPPED / DEADLINE) to their field
    for (arm, f), e in list(out.items()):
        if f.startswith("_"):
            continue
        mk = out.get((arm, f), {}).get("markers", [])
        e["markers"] = mk
    return out


def baseline_ok(rs):
    ok, final = {}, {}
    for r in rs:
        if r["role"] != "baseline":
            continue
        if r["field"] == "_baseline":
            ok[r["arm"]] = (r.get("observed", {}).get("status") == "OK",
                            bool(r.get("match")))
        if r["field"] == "_baseline_final":
            final[r["arm"]] = bool(r.get("match"))
    return ok, final


def analyse_run(rs):
    lad = ladder_gate(rs)
    fal = falsifier_gate(rs)
    stats = per_arm_field(rs)
    bok, bfin = baseline_ok(rs)
    arms = {}
    for (arm, f), e in sorted(stats.items()):
        if f.startswith("_"):
            continue
        ls = lad.get(arm, {})
        fs = fal.get(arm, {})
        complete = (e["n"] == (1 << e["fwidth"])) if e["fwidth"] else False
        rule = bit_rule(e["v2class"], e["fwidth"]) if e["v2class"] else None
        base_cls = None
        # the class of the values that reproduced the baseline
        for v, oc in e["v2outcome"].items():
            if oc == "ok":
                base_cls = e["v2class"].get(v)
                break
        arms[(arm, f)] = {
            "instr": e["instr"], "carrier": e["carrier"],
            "carrier_dim": e["carrier_dim"], "secondary":
                e["carrier_dim"].startswith("secondary:"),
            "byte_index": e["byte_index"], "fstart": e["fstart"],
            "fwidth": e["fwidth"],
            "swept": e["n"], "coverage_complete": complete,
            "moved": e["moved"], "unchanged": e["ok"], "faults": e["faults"],
            "hangs": e["hangs"], "invalid_retried": e["invalid_seen"],
            "baseline_ok": bok.get(arm, (False, False))[0],
            "baseline_oracle_exact": bok.get(arm, (False, False))[1],
            "baseline_final_ok": bfin.get(arm),
            "ladders": ls,
            "ladder_pass": any(v.get("pass") for v in ls.values()),
            "ladder_passed_by": sorted(k for k, x in ls.items() if x.get("pass")),
            "falsifiers": fs,
            "falsifier_held": sorted(k for k, v in fs.items() if v["held"]),
            "any_falsifier_held": any(v["held"] for v in fs.values()),
            "bit_rule": rule,
            "baseline_set_rule": (describe(e["v2class"], e["fwidth"], base_cls)
                                  if base_cls else None),
            "predict_n": e["predict_n"], "predict_held": e["predict_held"],
            "markers": e["markers"],
            "outcome_hist": dict(collections.Counter(e["v2outcome"].values())),
            "v2outcome": e["v2outcome"],
        }
    return arms


def eligible(a):
    """Eligible to support a LIVE verdict.

    COMPLETE COVERAGE IS DELIBERATELY NOT REQUIRED HERE, and the asymmetry is
    the point: MOVEMENT IS SELF-PROVING.  If a field changed an observation at
    even one value on an arm with a passing ladder and a held falsifier, it is
    live, whether or not the sweep later hit a hang budget.  ABSENCE of movement
    is what needs the whole value space, so `eligible_inert` adds that.
    (EXP-0155 truncated `frag_color_pack.dst` at value 194 in both of its gated
    runs; requiring completeness for LIVE would have thrown away a field that
    moved on 382 of the 404 values it did dispatch.)
    """
    return (a["baseline_ok"] and a["ladder_pass"] and a["any_falsifier_held"]
            and not a["secondary"])


def eligible_inert(a):
    return eligible(a) and a["coverage_complete"]


def verdicts(per_run):
    """Merge every run into one verdict per field, with cross-run agreement."""
    fields = collections.defaultdict(dict)         # "instr.field" -> run -> arms
    for rid, arms in per_run.items():
        for (arm, f), a in arms.items():
            fields["%s.%s" % (a["instr"], f)].setdefault(rid, {})[arm] = a
    out = {}
    for key, byrun in sorted(fields.items()):
        runs = sorted(byrun)
        allarms = sorted({arm for r in runs for arm in byrun[r]})
        # cross-run per-value agreement, on arms present in >= 2 runs
        agree = {"pairs": [], "worst": None}
        for i in range(len(runs)):
            for j in range(i + 1, len(runs)):
                a, b = runs[i], runs[j]
                common = same = 0
                for arm in allarms:
                    x = byrun[a].get(arm, {}).get("v2outcome", {})
                    y = byrun[b].get(arm, {}).get("v2outcome", {})
                    for v in set(x) & set(y):
                        common += 1
                        same += (x[v] == y[v])
                pct = (100.0 * same / common) if common else None
                agree["pairs"].append({"runs": [a, b], "common": common,
                                       "agree": same,
                                       "pct": None if pct is None else round(pct, 3)})
                if pct is not None and (agree["worst"] is None or pct < agree["worst"]):
                    agree["worst"] = round(pct, 3)
        # a field is LIVE only if it moved on an ELIGIBLE arm in EVERY run that
        # ran that arm
        live_arms, inert_dims, elig_arms, barred = [], set(), [], []
        for arm in allarms:
            per = [byrun[r][arm] for r in runs if arm in byrun[r]]
            if not all(eligible(a) for a in per):
                barred.append({"arm": arm,
                               "why": _why_barred(per[0])})
                continue
            elig_arms.append(arm)
            if all(a["moved"] > 0 for a in per):
                live_arms.append(arm)
            elif all(a["moved"] == 0 for a in per) and all(eligible_inert(a)
                                                           for a in per):
                inert_dims.add(per[0]["carrier_dim"])
        if not elig_arms:
            bucket, label = "LADDER-FAILED", "untested"
        elif live_arms:
            bucket, label = "LIVE", "hardware-run"
        elif len(inert_dims) >= RA.INERT_MIN_DISTINCT_CARRIER_DIMS:
            bucket, label = "INERT-ROBUST", "single-template-inference"
        else:
            bucket, label = "STILL-UNDERPOWERED", "untested"
        if len(runs) < 2:
            label_note = ("ONE RUN ONLY: cross-run agreement is the "
                          "pre-registered promotion gate and has not been "
                          "evaluated; this verdict is PROVISIONAL")
        elif agree["worst"] is not None and agree["worst"] < 99.0:
            bucket, label = "UNSTABLE", "untested"
            label_note = ("cross-run per-value agreement %.3f%% is below the "
                          "99%% bar" % agree["worst"])
        else:
            label_note = "cross-run agreement %.3f%%" % agree["worst"]
        rec = {"bucket": bucket, "label": label, "label_note": label_note,
               "runs": runs, "eligible_arms": elig_arms,
               "live_arms": live_arms,
               "inert_carrier_dims": sorted(inert_dims),
               "n_distinct_inert_carrier_dims": len(inert_dims),
               "barred_arms": barred, "cross_run": agree,
               "range": _range_str(byrun, runs, allarms),
               "target": "G17P",
               "arms": {arm: {r: byrun[r][arm] for r in runs if arm in byrun[r]}
                        for arm in allarms}}
        if key == "pixel_order.kind":
            rec["prereg_model"] = pixel_order_score(byrun, runs, allarms)
        out[key] = rec
    return out


def _why_barred(a):
    if not a["baseline_ok"]:
        return "baseline failed"
    if a["secondary"]:
        return ("cross-family `secondary:` arm: adds an observation but NOT a "
                "distinct carrier dimension")
    if not a["ladder_pass"]:
        return ("no liveness ladder reached %d distinct hashes under the strict "
                "gate, so this arm's inertness is NOT evidence"
                % RA.LADDER_MIN_DISTINCT_HASHES)
    if not a["any_falsifier_held"]:
        return "no falsifier held: the arm never demonstrated it can see a difference"
    if not a["coverage_complete"]:
        return "dense coverage incomplete (%d of %d values)" % (a["swept"],
                                                                1 << a["fwidth"])
    return "unknown"


def _range_str(byrun, runs, allarms):
    n = max((byrun[r][arm]["swept"] for r in runs for arm in byrun[r]), default=0)
    w = max((byrun[r][arm]["fwidth"] for r in runs for arm in byrun[r]), default=0)
    return "0..%d dense (%d of %d values), %d run(s)" % ((1 << w) - 1, n, 1 << w,
                                                         len(runs))


def pixel_order_score(byrun, runs, allarms):
    """Score against the PRE-REGISTERED partition derived from EXP-0162's raw.

    This is the only field of the four with a genuinely predictive oracle rather
    than an inert one, so it is scored as a prediction: per arm, how many of the
    256 values landed on the outcome the model named."""
    out = {"note": RA.PIXEL_ORDER_MODEL_NOTE, "arms": {}}
    for arm in allarms:
        for r in runs:
            a = byrun[r].get(arm)
            if not a:
                continue
            out["arms"].setdefault(arm, {})[r] = {
                "n_predicted": a["predict_n"], "held": a["predict_held"],
                "pct": (round(100.0 * a["predict_held"] / a["predict_n"], 3)
                        if a["predict_n"] else None)}
    return out


# ---------------------------------------------------------------------------
def structural_findings(meta, per_run):
    """First-class results that are not any field's verdict."""
    f = []
    for rid, m in meta.items():
        inp = m.get("00_inputs.json", {})
        for r in inp.get("refused", []):
            f.append({"kind": "arm_refused", "run": rid, **r})
    # a carrier with no occurrence of its target instruction is a fact about
    # when the compiler emits that instruction
    frozen = os.path.join(EXP, "work", "render_frozen_arms.json")
    if os.path.exists(frozen):
        for s in json.load(open(frozen)).get("skipped", []):
            if "no occurrence" in json.dumps(s):
                f.append({"kind": "instruction_absent", **s})
    return f


def tail_findings(recs):
    out = []
    for rid, rs in recs.items():
        n = sum(1 for r in rs
                if r.get("observed", {}).get("outbuf_tail_dirty") is True)
        d = sum(1 for r in rs if r.get("observed", {}).get("probe_pixels_disagree"))
        if n:
            out.append({"kind": "outbuf_tail_dirty", "run": rid, "cases": n,
                        "note": "a dispatch reported OK and wrote OUTSIDE the "
                                "slots any store names -- an out-of-bounds "
                                "vertex-stage write"})
        if d:
            out.append({"kind": "probe_pixels_disagree", "run": rid, "cases": d,
                        "note": "probe pixels of a full-screen triangle with "
                                "vertex-equal varyings disagreed, so the value "
                                "is position-dependent"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--md", action="store_true", help="markdown tables to stdout")
    ap.add_argument("-o", "--out", default=os.path.join(HERE, "render_verdicts.json"))
    args = ap.parse_args()

    recs, meta = load(args.runs)
    per_run = {rid: analyse_run(rs) for rid, rs in recs.items()}
    v = verdicts(per_run)
    doc = {"experiment": "EXP-0168", "arm": "RENDER (vertex + fragment)",
           "target": "G17P", "runs": sorted(recs),
           "cases_per_run": {k: len(x) for k, x in recs.items()},
           "verdict_rules": {
               "eligible_arm": "baseline OK, ladder passed the strict gate, >=1 "
                               "falsifier held, dense coverage complete, "
                               "carrier_dim not `secondary:`",
               "LIVE": ">=1 eligible arm moved, in every run that ran it "
                       "(complete coverage NOT required: movement is "
                       "self-proving)",
               "INERT-ROBUST": "0 movement on >=%d DISTINCT carrier_dim values, "
                               "each with COMPLETE dense coverage"
                               % RA.INERT_MIN_DISTINCT_CARRIER_DIMS,
               "STILL-UNDERPOWERED": "0 movement, too few distinct dimensions",
               "LADDER-FAILED": "no arm demonstrated detection power",
               "UNSTABLE": "cross-run per-value agreement below 99%"},
           "fields": v,
           "structural_findings": structural_findings(meta, per_run)
                                  + tail_findings(recs)}
    with open(args.out, "w") as f:
        json.dump(doc, f, indent=1, sort_keys=True, default=str)

    print("# EXP-0168 RENDER arm -- verdicts (target G17P)\n")
    print("runs: %s\n" % ", ".join(doc["runs"]))
    print("| field | bucket | label | eligible arms | live on | distinct inert dims |")
    print("|---|---|---|---|---|---|")
    for k, r in sorted(v.items()):
        print("| `%s` | **%s** | `%s` | %d | %s | %d |"
              % (k, r["bucket"], r["label"], len(r["eligible_arms"]),
                 ", ".join(r["live_arms"]) or "--",
                 r["n_distinct_inert_carrier_dims"]))
    print("\n## per-arm detail\n")
    print("| field | arm | carrier_dim | swept | moved | ladder | falsifier | live bits |")
    print("|---|---|---|---|---|---|---|---|")
    for k, r in sorted(v.items()):
        for arm, byrun in sorted(r["arms"].items()):
            a = byrun[sorted(byrun)[0]]
            br = a.get("bit_rule") or {}
            print("| `%s` | `%s` | %s | %d | %d | %s | %s | %s |"
                  % (k, arm, a["carrier_dim"][:44], a["swept"], a["moved"],
                     "PASS" if a["ladder_pass"] else "FAIL",
                     ",".join(a["falsifier_held"]) or "none",
                     ",".join(str(b) for b in br.get("live_bits", [])) or "--"))
    if "pixel_order.kind" in v:
        print("\n## pixel_order.kind vs the PRE-REGISTERED EXP-0162 partition\n")
        print("_%s_\n" % v["pixel_order.kind"]["prereg_model"]["note"])
        print("| arm | run | predicted | held | pct |")
        print("|---|---|---|---|---|")
        for arm, byrun in sorted(v["pixel_order.kind"]["prereg_model"]["arms"].items()):
            for rid, s in sorted(byrun.items()):
                print("| `%s` | %s | %d | %d | %s |"
                      % (arm, rid, s["n_predicted"], s["held"], s["pct"]))
    if doc["structural_findings"]:
        print("\n## structural findings (not any field's verdict)\n")
        for s in doc["structural_findings"]:
            print("- `%s` %s" % (s.get("kind"), json.dumps(
                {k: x for k, x in s.items() if k != "kind"}, sort_keys=True)[:300]))
    print("\nwrote %s" % args.out)


if __name__ == "__main__":
    main()
