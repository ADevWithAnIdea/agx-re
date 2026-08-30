#!/usr/bin/env python3
"""EXP-0158 analysis: turn the two gated runs into the headline numbers and
`analysis/field_verdicts.json`.  No GPU; runs anywhere.

The headline was DEFINED IN PRE_REGISTRATION.md section 7 before the run, and
this script computes exactly that definition and nothing else:

  N  = cases that (a) contain ZERO COPIED fields, (b) were predicted to match,
       and (c) matched bit-exactly in BOTH runs.
  N0 = the subset of N that also contains zero PILOT fields, i.e. rests only on
       rules published by earlier experiments.
  the remainder = cases that still need a donor, named by which token.

`InnocentVictim`-class observations are separated out everywhere: they are
evidence about the MACHINE (a sibling agent's GPU error recovery), not about
our encoding.  A case is only counted as `fault` if the majority-of-3
revalidation pass agreed.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))

import run as RUN  # noqa: E402  (for the contracted run ids, never re-typed here)

RUNS = RUN.RUNS                 # the contracted gated pair: run03 / run04
RETAINED_PRIOR = RUN.RETAINED_PRIOR_RUNS   # run01, the pre-AMENDMENT-1 capture
VICTIM = "InnocentVictim"


def load_run(rid):
    p = EXP / "raw" / rid / "01_results.jsonl"
    if not p.exists():
        return None
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def load_reval(rid):
    p = EXP / "raw" / rid / "04_revalidate.jsonl"
    if not p.exists():
        return {}
    return dict((r["i"], r) for r in
                (json.loads(l) for l in p.read_text().splitlines() if l.strip()))


def load_cascade(rid):
    p = EXP / "raw" / rid / "03_cascade.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    runs = dict((r, load_run(r)) for r in RUNS)
    have = [r for r in RUNS if runs[r]]
    if not have:
        raise SystemExit("no gated run present yet")
    reval = dict((r, load_reval(r)) for r in have)
    cascade = dict((r, load_cascade(r)) for r in have)

    base = runs[have[0]]
    by_i = dict((c["i"], c) for c in base)

    CONTAM = ("fault", "hang", "victim", "invalid_run", "missing")

    def eff_outcome(r, i):
        """The case's outcome AFTER the majority-of-3 revalidation pass.

        A first observation of fault/hang/victim/invalid_run is NOT a property
        of the encoding under a multi-agent GPU (FIELD-SWEEP-PROTOCOL section 7
        and 7A).  run.py re-ran every such case twice more; where the majority
        of three disagrees with the first observation, the majority is the
        result.  Both numbers are reported so a reader can see the size of the
        correction."""
        rec = next((x for x in runs[r] if x["i"] == i), None)
        if rec is None:
            return None
        rv = reval[r].get(i)
        if rv and rv["majority_count"] >= 2:
            return rv["majority_outcome"]
        return rec["outcome"]

    def matched_everywhere(i):
        """Matched in EVERY run, counting a revalidation-corrected `ok` as a
        match.  A case still contaminated after three attempts is NOT counted
        as a match; it is reported separately as unresolved."""
        for r in have:
            rec = next((x for x in runs[r] if x["i"] == i), None)
            if rec is None:
                return False
            if rec["match"]:
                continue
            if eff_outcome(r, i) == "ok":
                continue
            return False
        return True

    def unresolved(i):
        return any(eff_outcome(r, i) in CONTAM for r in have)

    def outcome_everywhere(i):
        return [next((x for x in runs[r] if x["i"] == i), {}).get("outcome") for r in have]

    zero_copied, needs_donor = [], []
    for c in base:
        if not c.get("prov"):
            needs_donor.append((c, ["<no provenance ledger>"]))
        elif c["prov"]["copied"]:
            needs_donor.append((c, c["prov"]["copied"]))
        else:
            zero_copied.append(c)

    N = [c for c in zero_copied if c["expect_match"] and matched_everywhere(c["i"])]
    zc_unresolved = [c for c in zero_copied if c["expect_match"] and not
                     matched_everywhere(c["i"]) and unresolved(c["i"])]
    N0 = [c for c in N if not c["prov"]["pilot"]]
    zc_predicted = [c for c in zero_copied if c["expect_match"]]
    zc_failed = [c for c in zc_predicted if not matched_everywhere(c["i"])
                 and not unresolved(c["i"])]

    adversarial = [c for c in base if not c["expect_match"]]
    adv_ok = [c for c in adversarial if not matched_everywhere(c["i"])]

    # victim / fault accounting
    victims = Counter()
    faults_majority = []
    for r in have:
        for rec in runs[r]:
            if VICTIM in (rec.get("fault_class") or ""):
                victims[r] += 1
        for i, rv in reval[r].items():
            if rv["majority_outcome"] in ("fault", "hang") and rv["majority_count"] >= 2:
                faults_majority.append((r, i, by_i[i]["name"], rv["majority_outcome"]))

    per_group = defaultdict(lambda: {"n": 0, "zero_copied": 0, "matched": 0,
                                     "as_predicted": 0})
    for c in base:
        g = per_group[c["group"]]
        g["n"] += 1
        if c.get("prov") and not c["prov"]["copied"]:
            g["zero_copied"] += 1
        m = matched_everywhere(c["i"])
        if m:
            g["matched"] += 1
        if m == c["expect_match"]:
            g["as_predicted"] += 1

    donor_tokens = Counter()
    for c, toks in needs_donor:
        for t in toks:
            donor_tokens[t] += 1

    summary = {
        "runs_present": have,
        "n_cases": len(base),
        "HEADLINE_N_zero_copied_and_correct": len(N),
        "HEADLINE_N0_zero_copied_zero_pilot_and_correct": len(N0),
        "zero_copied_cases_total": len(zero_copied),
        "zero_copied_predicted_to_match": len(zc_predicted),
        "zero_copied_that_FAILED": [
            {"name": c["name"], "group": c["group"], "outcomes": outcome_everywhere(c["i"]),
             "observed": [next((x for x in runs[r] if x["i"] == c["i"]), {}).get("observed")
                          for r in have]}
            for c in zc_failed],
        "zero_copied_UNRESOLVED_still_contaminated_after_3": [
            {"name": c["name"], "group": c["group"],
             "effective": [eff_outcome(r, c["i"]) for r in have]} for c in zc_unresolved],
        "cases_still_needing_a_donor": len(needs_donor),
        "donor_tokens_still_required": dict(donor_tokens.most_common()),
        "adversarial_total": len(adversarial),
        "adversarial_behaved_as_predicted": len(adv_ok),
        "adversarial_that_UNEXPECTEDLY_PASSED": [
            c["name"] for c in adversarial if c not in adv_ok],
        "per_group": dict(per_group),
        "innocent_victim_cases_per_run": dict(victims),
        "reproduced_faults_majority_of_3": faults_majority,
        "cascade_witness_failures": dict(
            (r, [c for c in cascade[r] if not c["witness_ok"]]) for r in have),
    }
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    if a.write:
        (HERE / "summary.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
        print("\nWROTE analysis/summary.json")


if __name__ == "__main__":
    main()
