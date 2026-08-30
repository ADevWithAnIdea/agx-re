#!/usr/bin/env python3
"""EXP-0167 analysis: per-program comparison of the ISOLATED runs against
EXP-0158's CONTENDED runs, plus the four pre-registered metrics M1..M4.

No GPU. Runs on the repo host. `EXP-0158-*` is opened READ-ONLY and is never
written to (`CLAUDE.md`: it is committed, append-only, and the orchestrator's).

Emits `analysis/comparison.json` and prints a human summary. Every metric here
is the definition frozen in PRE_REGISTRATION.md section 3, computed by the same
code path for both experiments so the two columns cannot drift apart.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
EXPS = EXP.parent
PRIOR = EXPS / "EXP-0158-g17p-generator-synthesis"
PRIOR_RUNS = ("g17p-20260830-run03", "g17p-20260830-run04")
WRONG = ("wrong_value", "silent_zero", "no_write")
CONTAM = ("fault", "hang", "victim", "invalid_run", "missing")

WATCH_NO_OK = ["dag_009_n11", "dag_010_n12", "dag_012_n14", "dagi_016_n20",
               "dagi_019_n26", "dagi_023_n35", "regb_R000", "regb_R031",
               "regb_R047", "regb_R063", "regb_R063_poison_r63",
               "regb_R005_extlsb1", "inl_k01", "inl_k08", "inl_k12"]
WATCH_KNOWN_FAIL = ["iaddsyn_A33_B44_N13_D9_sub", "iaddsyn_A127_B1_N15_D10_add",
                    "iaddsyn_A11_B22_N1_D95_add", "iaddsyn_A7_B120_N4_D47_add"]
WATCH_SINGLED = ["dag_040_n20"]


def load_jsonl(p):
    p = Path(p)
    if not p.exists():
        return None
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def load_pair(root, runs):
    out = []
    for rid in runs:
        r = load_jsonl(Path(root) / "raw" / rid / "01_results.jsonl")
        if r is None:
            return None
        out.append(r)
    return out


def reval_map(root, rid):
    r = load_jsonl(Path(root) / "raw" / rid / "04_revalidate.jsonl") or []
    return dict((x["name"], x) for x in r)


def reconfirm_map(root, fname):
    r = load_jsonl(Path(root) / "work" / "reconfirm" / fname) or []
    return dict((x["name"], x) for x in r)


def zero_copied_expect(recs):
    return [r for r in recs if r.get("prov") and not r["prov"]["copied"] and r["expect_match"]]


def m1_strict_pair(a, b):
    """Cases with zero COPIED fields and expect_match, match==True in BOTH runs."""
    bb = dict((r["name"], r) for r in b)
    z = zero_copied_expect(a)
    names = [r["name"] for r in z if r["match"] and bb[r["name"]]["match"]]
    return names, len(z)


def all_observations(name, pair, revals, recon):
    obs = []
    for recs, rv in zip(pair, revals):
        rec = next((x for x in recs if x["name"] == name), None)
        if rec:
            obs.append(rec["outcome"])
        if name in rv:
            obs += [o["outcome"] for o in rv[name]["observations"]]
    if name in recon:
        obs += [o["outcome"] for o in recon[name]["observations"]]
    return obs


def m3_attributable(pair, revals, recon):
    z = zero_copied_expect(pair[0])
    good, bad, none = [], [], []
    for r in z:
        obs = all_observations(r["name"], pair, revals, recon)
        if any(o in WRONG for o in obs):
            bad.append((r["name"], obs))
        elif "ok" in obs:
            good.append(r["name"])
        else:
            none.append((r["name"], obs))
    return good, bad, none, len(z)


def describe(root, runs, recon_file):
    pair = load_pair(root, runs)
    if pair is None:
        return None
    revals = [reval_map(root, rid) for rid in runs]
    recon = reconfirm_map(root, recon_file)
    m1, denom = m1_strict_pair(pair[0], pair[1])
    good, bad, none, d3 = m3_attributable(pair, revals, recon)
    adv = [r for r in pair[0] if not r["expect_match"]]
    bb = dict((r["name"], r) for r in pair[1])
    adv_still_fail = [r["name"] for r in adv
                      if not r["match"] and not bb[r["name"]]["match"]]
    return {
        "runs": list(runs),
        "n_cases": len(pair[0]),
        "denominator_Z": denom,
        "M1_strict_pair": len(m1),
        "M1_names": m1,
        "M3_attributable": len(good),
        "M3_attributably_wrong": [n for n, _ in bad],
        "M3_attributably_wrong_obs": dict(bad),
        "M3_no_observation": [n for n, _ in none],
        "M3_no_observation_obs": dict(none),
        "adversarials_n": len(adv),
        "adversarials_still_fail": len(adv_still_fail),
        "outcome_counts": [dict(Counter(r["outcome"] for r in recs)) for recs in pair],
        "victim_retries_total": [sum(r["victim_retries"] for r in recs) for recs in pair],
        "victim_retries_cases": [sum(1 for r in recs if r["victim_retries"]) for recs in pair],
        "_pair": pair,
        "_revals": revals,
        "_recon": recon,
    }


def per_program(iso, prior):
    """One row per zero-copied predicted-to-match program: outcome under
    isolation, outcome under contention, and whether they agree."""
    rows = []
    pi = dict((r["name"], r) for r in prior["_pair"][0])
    pj = dict((r["name"], r) for r in prior["_pair"][1])
    ii = dict((r["name"], r) for r in iso["_pair"][0])
    ij = dict((r["name"], r) for r in iso["_pair"][1])
    for r in iso["_pair"][0]:
        n = r["name"]
        iso_o = (ii[n]["outcome"], ij[n]["outcome"])
        pri_o = (pi[n]["outcome"], pj[n]["outcome"]) if n in pi else (None, None)
        iso_obs = all_observations(n, iso["_pair"], iso["_revals"], iso["_recon"])
        pri_obs = all_observations(n, prior["_pair"], prior["_revals"], prior["_recon"])

        def verdict(obs):
            if any(o in WRONG for o in obs):
                return "WRONG"
            if "ok" in obs:
                return "CORRECT"
            if obs:
                return "NO-OBSERVATION"
            return "ABSENT"
        rows.append({
            "name": n, "group": r["group"], "expect_match": r["expect_match"],
            "zero_copied": bool(r.get("prov") and not r["prov"]["copied"]),
            "iso_outcomes": list(iso_o), "prior_outcomes": list(pri_o),
            "iso_verdict": verdict(iso_obs), "prior_verdict": verdict(pri_obs),
            "agree": verdict(iso_obs) == verdict(pri_obs),
            "iso_fault_classes": sorted(set(
                x["fault_class"] for x in (ii[n], ij[n]) if x["fault_class"])),
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, str(EXP))
    import run as RUN  # noqa: E402

    iso = describe(EXP, RUN.RUNS, "reconfirm_iso.jsonl")
    if iso is None:
        raise SystemExit("EXP-0167 gated pair not present yet: %s" % (RUN.RUNS,))
    prior = describe(PRIOR, PRIOR_RUNS, "reconfirm02.jsonl")
    if prior is None:
        raise SystemExit("EXP-0158 gated pair not readable")

    rows = per_program(iso, prior)
    changed = [r for r in rows if not r["agree"]]
    watch = [r for r in rows if r["name"] in
             (WATCH_NO_OK + WATCH_KNOWN_FAIL + WATCH_SINGLED)]

    out = {
        "isolated": dict((k, v) for k, v in iso.items() if not k.startswith("_")),
        "contended_EXP0158": dict((k, v) for k, v in prior.items() if not k.startswith("_")),
        "per_program": rows,
        "verdict_changed": changed,
        "n_verdict_changed": len(changed),
        "watch_list": watch,
    }
    if a.write:
        (HERE / "comparison.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    print("%-34s %10s %10s" % ("metric", "ISOLATED", "EXP-0158"))
    print("%-34s %10d %10d" % ("M1 strict-pair (of Z)", iso["M1_strict_pair"], prior["M1_strict_pair"]))
    print("%-34s %10d %10d" % ("M3 attributable (of Z)", iso["M3_attributable"], prior["M3_attributable"]))
    print("%-34s %10d %10d" % ("  attributably WRONG", len(iso["M3_attributably_wrong"]), len(prior["M3_attributably_wrong"])))
    print("%-34s %10d %10d" % ("  no observation at all", len(iso["M3_no_observation"]), len(prior["M3_no_observation"])))
    print("%-34s %10d %10d" % ("Z denominator", iso["denominator_Z"], prior["denominator_Z"]))
    print("%-34s %10d %10d" % ("adversarials still fail", iso["adversarials_still_fail"], prior["adversarials_still_fail"]))
    print("%-34s %10s %10s" % ("victim retries (run1/run2)",
                               iso["victim_retries_total"], prior["victim_retries_total"]))
    print("\nISO outcome counts:  ", iso["outcome_counts"])
    print("PRIOR outcome counts:", prior["outcome_counts"])
    print("\nprograms whose VERDICT changed: %d" % len(changed))
    for r in changed:
        print("  %-32s %-8s %-14s -> %-14s iso=%s prior=%s"
              % (r["name"], r["group"], r["prior_verdict"], r["iso_verdict"],
                 r["iso_outcomes"], r["prior_outcomes"]))
    print("\nnamed watch list (%d):" % len(watch))
    for r in watch:
        print("  %-32s prior=%-14s iso=%-14s %s"
              % (r["name"], r["prior_verdict"], r["iso_verdict"],
                 "AGREE" if r["agree"] else "*** CHANGED ***"))


if __name__ == "__main__":
    main()
