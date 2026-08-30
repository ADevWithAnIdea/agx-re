#!/usr/bin/env python3
"""EXP-0210 -- per-FIELD cross-run agreement for one pair, from raw.

    python3 analysis/per_field.py <A.jsonl> <B.jsonl> [field ...]

Same key and volatile-exclusion rules as `analysis/pairwise.py`; this just reports the
numbers per field instead of per run, so a single disagreeing case can be attributed to the
field it belongs to rather than diluted across the whole capture.
"""
import json
import sys
from collections import defaultdict

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pairwise import (HARD, load, mkkey, outcome, payload,      # noqa: E402
                      pick_keyfields, actual_bytes)


def main():
    A, B = load(sys.argv[1]), load(sys.argv[2])
    want = set(sys.argv[3:])
    fs, uniq = pick_keyfields(A, B)
    ka, kb = defaultdict(list), defaultdict(list)
    for r in A:
        ka[mkkey(r, fs)].append(r)
    for r in B:
        kb[mkkey(r, fs)].append(r)
    per = defaultdict(lambda: {"agree": 0, "disagree": 0, "both_hard": 0,
                               "hard_flip": 0, "ledger_diff": 0, "cases": 0,
                               "examples": []})
    for k in sorted(set(ka) & set(kb)):
        ra = ka[k][0]
        f = ra.get("field")
        instr = ra.get("instr") or ""
        name = ("%s.%s" % (instr, f)) if instr else str(f)
        if want and name not in want and str(f) not in want:
            continue
        d = per[name]
        d["cases"] += 1
        if (sorted(str(actual_bytes(r)) for r in ka[k])
                != sorted(str(actual_bytes(r)) for r in kb[k])):
            d["ledger_diff"] += 1
        oas = sorted(outcome(r) for r in ka[k])
        obs = sorted(outcome(r) for r in kb[k])
        ha = all(o in HARD for o in oas)
        hb = all(o in HARD for o in obs)
        if ha and hb:
            d["both_hard"] += 1
            continue
        if ha != hb:
            d["hard_flip"] += 1
            d["disagree"] += 1
            if len(d["examples"]) < 5:
                d["examples"].append({"key": k, "A": oas, "B": obs, "cls": "hard_flip"})
            continue
        if (sorted(payload(r) for r in ka[k])
                == sorted(payload(r) for r in kb[k])):
            d["agree"] += 1
        else:
            d["disagree"] += 1
            if len(d["examples"]) < 5:
                d["examples"].append({"key": k, "A": oas, "B": obs, "cls": "soft"})
    out = {}
    for name, d in sorted(per.items()):
        comp = d["agree"] + d["disagree"]
        d["pct"] = round(100.0 * d["agree"] / comp, 4) if comp else None
        out[name] = d
    json.dump({"key_fields": fs, "key_unique": uniq, "fields": out},
              sys.stdout, indent=1, sort_keys=True)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
