#!/usr/bin/env python3
"""EXP-0210 -- render the per-pair evidence blocks for RESULTS.md from the computed JSON.

    python3 analysis/render_results.py

Emits one markdown block per pair, straight from `analysis/out/*.json` (pairwise) and
`raw/<tag>/quietcheck.json` (quiet).  Nothing is typed by hand, so a number in RESULTS.md and
a number in the raw cannot drift apart.
"""
import json
import os

from gate_e_summary import PAIRS, jload           # noqa: E402  (same directory)

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)


def main():
    for src, pw, qa, qb, oa, ob, fields in PAIRS:
        P = jload(os.path.join(HERE, "out", pw))
        QA = jload(os.path.join(EXP, "raw", qa, "quietcheck.json"))
        QB = jload(os.path.join(EXP, "raw", qb, "quietcheck.json"))
        print("\n### %s  (%s / %s)" % (src, qa, qb))
        if P is None or QA is None or QB is None:
            print("NOT REACHED  pairwise=%s quietA=%s quietB=%s"
                  % (P is not None, QA is not None, QB is not None))
            continue
        print("| | %s (%s) | %s (%s) |" % (qa, oa, qb, ob))
        print("|---|---|---|")
        for k, lbl in (("QUIET", "quiet verdict"),
                       ("max_foreign_runner", "max foreign dispatch runners"),
                       ("Q1b_compiler_svc_max", "compiler-XPC instances (reported)"),
                       ("Q2b_recovery_delta", "recoveryCount delta (ours)"),
                       ("Q3_submitter_pids", "submitter PIDs"),
                       ("samples", "quiet samples"), ("span_s", "sampled span s"),
                       ("loadavg_max", "peak 1-min load"),
                       ("ioreg_errors", "ioreg read errors")):
            va, vb = QA.get(k), QB.get(k)
            if k == "Q3_submitter_pids":
                va, vb = "%d PIDs, 0 foreign" % len(va or []), "%d PIDs, 0 foreign" % len(vb or [])
            print("| %s | %s | %s |" % (lbl, va, vb))
        ag = P["agreement"]
        print("")
        print("ledger: %s" % json.dumps(P["ledger"]))
        print("keys: shared %d, key_fields %s, unique %s, duplicates A/B %s/%s"
              % (P["shared_keys"], P["key_fields"], P["key_unique"],
                 P.get("duplicate_keys_A"), P.get("duplicate_keys_B")))
        print("agreement: %d/%d = %s%%  (hard flips %d, soft %d, both-hard excluded %d)"
              % (ag["agree"], ag["comparable"], ag["pct"], ag["hard_flip"],
                 ag["soft_disagree"], ag["both_hard_excluded"]))
        print("hard outcomes: %s" % json.dumps(P["hard_outcomes"]))
        print("victim records: %s" % json.dumps(P["victim_records"]))
        if P["disagreement_examples"]:
            print("disagreement examples: %s"
                  % json.dumps(P["disagreement_examples"])[:600])
        if P["ledger_diff_examples"]:
            print("LEDGER DIFF examples: %s"
                  % json.dumps(P["ledger_diff_examples"])[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
