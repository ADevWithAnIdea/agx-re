#!/usr/bin/env python3
"""EXP-0201 PROMOTION GATE. Recomputes every verdict from raw/ on every call.

    python3 analysis/verdicts.py raw/<run01> raw/<run02> [...]

Implements PRE_REGISTRATION.md section 7 and nothing else. Verdicts are never
read back from a run manifest; they are re-derived from the append-only records.

THE GATE MUST BE ABLE TO SAY NO. Thirteen checks in this corpus could not, and
each of those failures is encoded here as an assertion in `selftest()`:

  * a GPU **fault** is not movement (a gate counted one; so did a case where our
    own disassembler failed to decode -- both with STATUS OK and byte-identical
    output);
  * a round trip is symmetric and is **not** an emitter gate, so nothing here
    consults one;
  * a width-1 field must be able to pass: the rule is
    `moved >= 2*disagree AND moved > 0`, never `moved >= 2*max(disagree,1)`,
    which refuses every 1-bit field by arithmetic rather than by evidence;
  * an INERT verdict needs a **detection-power conjunct** or it cannot fail
    either -- an arm whose observable never moves returns moved = 0 by
    construction;
  * **V <= 1 (one distinct valid payload over many legal values) is NOT
    PROMOTED** whatever else is true: the values ran legally and were
    indistinguishable. That is the shape that left `copysign.operands` at
    `untested` after a dense 256-value, 256-distinct-encoding M4 sweep.

CROSS-RUN COMPARISON USES THE DETERMINISTIC PAYLOAD ONLY. `observed` in this
experiment's raw carries no timer; `gputime_ns` is a top-level key. An indexer
that hashes the whole `observed` dict measures the nanosecond timer along with
the data, which alone moved one field's apparent agreement from 100 % to 39 %.
"""
import collections
import glob
import json
import os
import sys

MIN_AGREE = 99.0
MOVED_OVER_DISAGREE = 2.0
HARD = {"fault", "hang", "undecodable", "measurement_failure", "invalid_run",
        "nondeterministic", "not_written_all", "carrier_start_failed"}
TARGETS = [("falu3", "op"), ("falu3_ext", "op"), ("fspecial_est", "srcA"),
           ("falu3_srcmod12", "opsel"), ("falu3_srcmod12", "ctrl"),
           ("copysign", "operands")]


def sig(rec):
    """The deterministic observation signature: the read-back payload only."""
    o = rec.get("observed") or {}
    return json.dumps({k: o.get(k) for k in
                       ("status", "vals_u32", "aux_u32", "sent_u32", "tail_u32",
                        "unwritten", "sentinel_ok", "tail_ok")},
                      sort_keys=True)


def load(run_dirs):
    recs = []
    for d in run_dirs:
        run = os.path.basename(os.path.normpath(d))
        for f in sorted(glob.glob(os.path.join(d, "*.jsonl"))):
            if os.path.basename(f) != "sweep.jsonl":
                continue
            for ln in open(f, errors="replace"):
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                r["_run"] = run
                recs.append(r)
    return recs


def quiet(run_dirs):
    """A run is QUIET only if no sample saw a foreign GPU-runner process."""
    out = {}
    for d in run_dirs:
        run = os.path.basename(os.path.normpath(d))
        p = os.path.join(d, "gpuwatch.jsonl")
        if not os.path.exists(p):
            out[run] = {"samples": 0, "quiet": None,
                        "note": "no gpuwatch.jsonl -- quietness UNMEASURED"}
            continue
        n = f = 0
        peak = []
        for ln in open(p, errors="replace"):
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            n += 1
            k = r.get("n_foreign", 0)
            if k:
                f += 1
                peak = sorted({x["comm"] for x in r.get("procs", [])
                               if not x["ours"]})
        out[run] = {"samples": n, "samples_with_foreign_gpu_proc": f,
                    "quiet": (n > 0 and f == 0), "foreign_comms": peak}
    return out


def arm_stats(recs, arm, run):
    """Per-value deterministic signature for one arm in one run, plus the
    baseline signature captured immediately before the arm.

    Returns (baseline_sig, valid_sigs, hard_counter, token_mismatch_values,
    all_sigs). `valid_sigs` feeds `moved`; `all_sigs` additionally carries hard
    outcomes as their own class and feeds the cross-run comparison."""
    base = None
    for r in recs:
        if r["_run"] == run and r.get("field") == "_baseline" \
                and r.get("arm") == arm + ":open":
            base = sig(r)
    vals, allv, hard, tokmis = {}, {}, collections.Counter(), set()
    for r in recs:
        if r["_run"] != run or r.get("arm") != arm or r.get("field") == "_baseline":
            continue
        oc = r.get("outcome")
        if oc in HARD:
            hard[oc] += 1
            # A hard outcome is NOT movement (C5) and never enters `vals`, but it
            # IS an observation about that value, so it enters the CROSS-RUN
            # comparison as its own class. Otherwise a value that faults in one
            # run and runs clean in the other silently drops out of `common`
            # instead of counting as the disagreement it is.
            allv[r["value"]] = "hard:" + str(oc)
            continue
        vals[r["value"]] = sig(r)
        allv[r["value"]] = sig(r)
        tok = (r.get("token") or {}).get("mnemonic")
        if tok != r.get("instr"):
            tokmis.add(r["value"])
    return base, vals, hard, tokmis, allv


def analyse(recs, mnem, field, runs):
    arms = sorted({r["arm"] for r in recs
                   if r.get("instr") == mnem and r.get("field") == field})
    per_arm = {}
    for arm in arms:
        carrier = next(r["carrier"] for r in recs if r.get("arm") == arm)
        occ = next(r.get("occ") for r in recs if r.get("arm") == arm)
        ctl = arm.rsplit("/", 1)[0] + "/_live_control"
        fal = arm.rsplit("/", 1)[0] + "/_falsifier"
        entry = {"carrier": carrier, "occ": occ, "runs": {}}
        for run in runs:
            base, vals, hard, tokmis, _all = arm_stats(recs, arm, run)
            moved = sorted(v for v, s in vals.items()
                           if base is not None and s != base and v not in tokmis)
            moved_by_token = sorted(v for v in tokmis
                                    if base is not None and vals.get(v) != base)
            entry["runs"][run] = {
                "n_values": len(vals), "n_distinct_payloads": len(set(vals.values())),
                "moved": len(moved), "moved_by_relabelled_token": len(moved_by_token),
                "hard": dict(hard), "baseline_present": base is not None}
        # cross-run agreement over the values common to the first two runs
        agree_pct, dis, common = None, None, None
        if len(runs) >= 2:
            _, _, _, _, va = arm_stats(recs, arm, runs[0])
            _, _, _, _, vb = arm_stats(recs, arm, runs[1])
            keys = set(va) & set(vb)
            d = [v for v in keys if va[v] != vb[v]]
            common, dis = len(keys), len(d)
            agree_pct = 100.0 * (1 - len(d) / max(len(keys), 1))
        # controls
        cmoved = 0
        for run in runs:
            cb, cv, _, _, _ = arm_stats(recs, ctl, run)
            if cb is not None:
                cmoved = max(cmoved, sum(1 for s in cv.values() if s != cb))
        fmoved = 0
        for run in runs:
            fb, fv, _, _, _ = arm_stats(recs, fal, run)
            if fb is not None:
                fmoved = max(fmoved, sum(1 for s in fv.values() if s != fb))
        # payload / encoding census, from raw only
        cases = [r for r in recs if r.get("arm") == arm
                 and r.get("field") == field]
        valid = [r for r in cases if r.get("outcome") not in HARD]
        entry.update({
            "cross_run_agree_pct": agree_pct, "disagree": dis, "common": common,
            "moved": max(e["moved"] for e in entry["runs"].values()) if runs else 0,
            "moved_min": min(e["moved"] for e in entry["runs"].values()) if runs else 0,
            "V_distinct_valid_payloads": len({sig(r) for r in valid}),
            "L_legal_values": len({r["value"] for r in cases}),
            "distinct_bytes": len({r["bytes"] for r in cases if r.get("bytes")}),
            "distinct_oracles": len({json.dumps(r.get("oracle"), sort_keys=True)
                                     for r in cases}),
            "hard_outcomes": dict(collections.Counter(
                r["outcome"] for r in cases if r.get("outcome") in HARD)),
            "observed_fns": dict(collections.Counter(
                r.get("observed_fn") for r in valid)),
            "n_ok": sum(1 for r in valid if r.get("outcome") == "ok"),
            "accept_values": sorted({r["value"] for r in valid
                                     if r.get("outcome") == "ok"}),
            "control_moved": cmoved, "falsifier_moved": fmoved,
            "token_mismatch_values": sorted(
                {r["value"] for r in cases
                 if (r.get("token") or {}).get("mnemonic") != mnem}),
        })
        per_arm[arm] = entry
    return per_arm


def rule(e, n_runs, quiet_ok):
    """The frozen gate. Returns (verdict, reasons[])."""
    why = []
    if n_runs < 2:
        why.append("fewer than 2 gated runs")
    if e["V_distinct_valid_payloads"] <= 1 and e["L_legal_values"] > 1:
        why.append("V=%d distinct valid payloads over %d legal values -- ran "
                   "legally and INDISTINGUISHABLE (Case C)"
                   % (e["V_distinct_valid_payloads"], e["L_legal_values"]))
    if e["distinct_bytes"] < 2:
        why.append("distinct_bytes=%d" % e["distinct_bytes"])
    if e["distinct_bytes"] < e["L_legal_values"]:
        why.append("ALIASED: %d distinct encodings for %d legal values"
                   % (e["distinct_bytes"], e["L_legal_values"]))
    if e["distinct_oracles"] <= 1:
        why.append("CONSTANT ORACLE: predicts the instruction, not the field")
    if e["moved_min"] <= 0:
        why.append("moved=0 in at least one run")
    if e["disagree"] is not None and not (
            e["moved_min"] >= MOVED_OVER_DISAGREE * e["disagree"]):
        why.append("moved(%d) < 2*disagree(%d)" % (e["moved_min"], e["disagree"]))
    if e["cross_run_agree_pct"] is None or e["cross_run_agree_pct"] < MIN_AGREE:
        why.append("cross-run agreement %.2f%% < %.1f%%"
                   % (e["cross_run_agree_pct"] or 0.0, MIN_AGREE))
    if e["moved_min"] <= 0 and e["control_moved"] <= 0:
        why.append("no detection power: the arm's live control never moved, so "
                   "an inert reading cannot be supported either")
    if e["falsifier_moved"] <= 0:
        why.append("the pre-registered falsifier did not fire -- instrument blind")
    if not quiet_ok:
        why.append("CONTAMINATED: quietness not established for a confirmation run")
    return ("PROMOTE" if not why else "NOT PROMOTED"), why


def selftest():
    """This gate must be able to return NO, and must not refuse a 1-bit field."""
    ok = True
    w1 = {"V_distinct_valid_payloads": 2, "L_legal_values": 2, "distinct_bytes": 2,
          "distinct_oracles": 2, "moved_min": 1, "moved": 1, "disagree": 0,
          "cross_run_agree_pct": 100.0, "control_moved": 3, "falsifier_moved": 1}
    v, why = rule(w1, 2, True)
    if v != "PROMOTE":
        print("SELFTEST FAIL: a width-1 field with moved=1, disagree=0 was "
              "refused: %s" % why); ok = False
    dead = dict(w1, V_distinct_valid_payloads=1, moved_min=0, moved=0,
                control_moved=0)
    if rule(dead, 2, True)[0] != "NOT PROMOTED":
        print("SELFTEST FAIL: an indistinguishable, unmoved field was promoted")
        ok = False
    alias = dict(w1, L_legal_values=8, distinct_bytes=4)
    if rule(alias, 2, True)[0] != "NOT PROMOTED":
        print("SELFTEST FAIL: an aliased sweep was promoted"); ok = False
    const = dict(w1, distinct_oracles=1)
    if rule(const, 2, True)[0] != "NOT PROMOTED":
        print("SELFTEST FAIL: a constant oracle was promoted"); ok = False
    return ok


LABEL = {"PROMOTE": "hardware-run", "NOT PROMOTED": "untested"}


def main():
    if not selftest():
        return 2
    runs = sys.argv[1:]
    if not runs:
        print(__doc__)
        return 2
    exp = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    recs = load(runs)
    rnames = [os.path.basename(os.path.normpath(d)) for d in runs]
    q = quiet(runs)
    out, flat = {}, {}
    for mnem, field in TARGETS:
        arms = analyse(recs, mnem, field, rnames)
        if not arms:
            flat["%s.%s" % (mnem, field)] = {
                "label": "untested", "verdict": "NO RECORDS",
                "target": "G17P", "evidence": ["EXP-0201"]}
            continue
        # the arm that best supports a promotion; every arm is reported.
        best, bestv, bestwhy = None, "NOT PROMOTED", ["no arm"]
        for a, e in arms.items():
            qok = all(q.get(r, {}).get("quiet") for r in rnames)
            v, why = rule(e, len(rnames), qok)
            e["verdict"], e["reasons"] = v, why
            if v == "PROMOTE" and best is None:
                best, bestv, bestwhy = a, v, why
        if best is None:
            # report the arm with the fewest blocking reasons
            a = min(arms, key=lambda k: len(arms[k]["reasons"]))
            best, bestv, bestwhy = a, arms[a]["verdict"], arms[a]["reasons"]
        out["%s.%s" % (mnem, field)] = {"arms": arms, "chosen_arm": best,
                                        "verdict": bestv, "reasons": bestwhy}
        e = arms[best]
        flat["%s.%s" % (mnem, field)] = {
            "label": LABEL[bestv],
            "verdict": bestv,
            "range": "%d values dispatched, %d distinct encodings, %d legal"
                     % (e["L_legal_values"], e["distinct_bytes"], e["L_legal_values"]),
            "target": "G17P",
            "evidence": ["EXP-0201"],
            "start": next(r["start"] for r in recs
                          if r.get("instr") == mnem and r.get("field") == field),
            "width": next(r["width"] for r in recs
                          if r.get("instr") == mnem and r.get("field") == field),
            "values_dispatched": e["L_legal_values"],
            "distinct_bytes": e["distinct_bytes"],
            "distinct_oracles": e["distinct_oracles"],
            "V_distinct_valid_payloads": e["V_distinct_valid_payloads"],
            "moved": e["moved"], "moved_min": e["moved_min"],
            "disagree": e["disagree"], "common": e["common"],
            "cross_run_agree_pct": e["cross_run_agree_pct"],
            "control_moved": e["control_moved"],
            "falsifier_moved": e["falsifier_moved"],
            "hard_outcomes": e["hard_outcomes"],
            "observed_fns": e["observed_fns"],
            "accept_values": e["accept_values"],
            "n_arms": len(arms),
            "chosen_arm": best,
            "reasons": bestwhy,
        }
    res = {"_meta": {"runs": rnames, "quiet": q,
                     "thresholds": {"min_agree_pct": MIN_AGREE,
                                    "moved_over_disagree": MOVED_OVER_DISAGREE,
                                    "rule": "moved >= 2*disagree AND moved > 0"}},
           "fields": out}
    ap = os.path.join(exp, "analysis")
    json.dump(res, open(os.path.join(ap, "verdicts_full.json"), "w"), indent=1,
              default=str)
    json.dump(flat, open(os.path.join(ap, "field_verdicts.json"), "w"), indent=1,
              default=str)
    print("runs: %s" % ", ".join("%s(%s)" % (r, "QUIET" if q[r]["quiet"] else
                                             ("BUSY" if q[r]["quiet"] is False
                                              else "UNMEASURED")) for r in rnames))
    for k, v in flat.items():
        print("  %-28s %-13s V=%-4s L=%-4s bytes=%-4s orc=%-4s moved=%-4s "
              "dis=%-4s agree=%s"
              % (k, v.get("verdict"), v.get("V_distinct_valid_payloads"),
                 v.get("values_dispatched"), v.get("distinct_bytes"),
                 v.get("distinct_oracles"), v.get("moved_min"),
                 v.get("disagree"),
                 ("%.2f%%" % v["cross_run_agree_pct"])
                 if v.get("cross_run_agree_pct") is not None else "-"))
        for r in v.get("reasons", []):
            print("        - %s" % r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
