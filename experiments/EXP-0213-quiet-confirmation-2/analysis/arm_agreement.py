#!/usr/bin/env python3
"""EXP-0213 -- per-ARM agreement for EXP-0206 captures, with hard outcomes NOT hidden.

    python3 analysis/arm_agreement.py <runA.jsonl> <runB.jsonl>

pairwise.py excludes keys where BOTH runs recorded a hard outcome, so a `not_written` that
IS the expected payload (EXP-0206's synthesized mid-program `stop`, whose whole point is that
the program terminates and all 32 value words stay poison) disappears from the agreement
figure.  This prints, per arm: shared keys, keys where BOTH runs agree on the outcome LABEL,
keys where the payloads agree, and the exact hard-outcome key sets, so nothing is hidden.
"""
import json
import sys
from collections import defaultdict

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pairwise import load, payload, outcome                          # noqa: E402


def idx(R):
    d = {}
    for r in R:
        k = (r.get("arm"), r.get("field"), r.get("value"))
        d[k] = r
    return d


def main():
    A, B = idx(load(sys.argv[1])), idx(load(sys.argv[2]))
    shared = sorted(set(A) & set(B), key=str)
    per = defaultdict(lambda: {"shared": 0, "outcome_same": 0, "payload_same": 0,
                               "outcome_diff": [], "payload_diff": []})
    for k in shared:
        arm = k[0] or "?"
        s = per[arm]
        s["shared"] += 1
        oa, ob = outcome(A[k]), outcome(B[k])
        if oa == ob:
            s["outcome_same"] += 1
        else:
            s["outcome_diff"].append((k[2], oa, ob))
        if payload(A[k]) == payload(B[k]):
            s["payload_same"] += 1
        else:
            s["payload_diff"].append((k[2], oa, ob))
    tot = [0, 0, 0]
    for arm in sorted(per):
        s = per[arm]
        tot[0] += s["shared"]
        tot[1] += s["outcome_same"]
        tot[2] += s["payload_same"]
        flag = "" if (s["outcome_same"] == s["shared"] and
                      s["payload_same"] == s["shared"]) else "   <-- DISAGREES"
        print("  %-48s shared=%4d outcome_same=%4d payload_same=%4d%s"
              % (arm[:48], s["shared"], s["outcome_same"], s["payload_same"], flag))
        if s["outcome_diff"]:
            print("        outcome diffs:", s["outcome_diff"][:10])
        if s["payload_diff"]:
            print("        payload diffs (value, A, B):", s["payload_diff"][:12])
    print("  TOTAL shared=%d outcome_same=%d payload_same=%d" % tuple(tot))


if __name__ == "__main__":
    main()
