#!/usr/bin/env python3
"""EXP-0213 -- map one arm's outcome-by-value and compare it across captures.

    python3 analysis/hazard_map.py <arm-substring> <run1.jsonl> ... <runN.jsonl>

Prints, per run, the outcome class of every dispatched value of that arm, then the
ok / not-ok PARTITION as a set comparison between runs.  EXP-0210 sec.9's claim is that the
partition is load-independent while the SEVERITY of the not-ok outcome is not; this is the
computation that checks it over a whole 256-value arm instead of 14 values.
"""
import json
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pairwise import load                                            # noqa: E402

HARD = {"fault", "hang", "measurement_failure", "invalid_run", "undecodable", "timeout"}


def main():
    sub = sys.argv[1]
    runs = sys.argv[2:]
    per = []
    for p in runs:
        d = {}
        for r in load(p):
            if sub in str(r.get("arm") or r.get("carrier") or "") and \
                    isinstance(r.get("value"), int) and r["value"] >= 0:
                d[r["value"]] = r.get("outcome")
        per.append((p.split("/")[-1].replace(".jsonl", ""), d))
    for name, d in per:
        c = Counter(d.values())
        print("  %-34s values=%4d  %s" % (name, len(d), dict(c)))
    if len(per) < 2:
        return
    print("  --- partition comparison (ok/not-ok, over the values each pair shares) ---")
    for i in range(len(per)):
        for j in range(i + 1, len(per)):
            (na, a), (nb, b) = per[i], per[j]
            common = sorted(set(a) & set(b))
            same_part = sum(1 for v in common
                            if (a[v] in HARD) == (b[v] in HARD))
            sev = sorted(v for v in common
                         if a[v] in HARD and b[v] in HARD and a[v] != b[v])
            flip = sorted(v for v in common if (a[v] in HARD) != (b[v] in HARD))
            print("  %-20s x %-20s shared=%4d same_partition=%4d  severity_differs_at=%d %s  "
                  "PARTITION_FLIPS=%d %s"
                  % (na[-20:], nb[-20:], len(common), same_part, len(sev), sev[:10],
                     len(flip), flip[:10]))


if __name__ == "__main__":
    main()
