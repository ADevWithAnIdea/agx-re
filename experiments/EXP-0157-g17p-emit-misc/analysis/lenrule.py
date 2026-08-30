#!/usr/bin/env python3
"""EXP-0157 arm-N analysis: derive the `byte0` low-nibble-4 group's LENGTH RULE
from the hardware measurement.

Input: `raw/<run>/sweep.jsonl` produced by `harness/run_lm.py --arms N`, in
which every record carries `measured_length` -- the number of bytes the GPU
actually consumed, read off a register-witness pattern rather than inferred
from a tokenizer.

Output: `analysis/length_rule.json` -- per swept byte position, the partition of
its 256 values by measured length, and the exact (mask, value) rule when one
exists.

WHY THIS IS DIFFERENT FROM EXP-0148. EXP-0148 scored six candidate STATIC length
rules by how well they tokenized a corpus and found all six worse than the
status quo, leaving `op04_len8` OPEN. Corpus tokenization cannot see
over-consumption at all (round-trip is blind to it by construction). This asks
the silicon.
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(p):
    out = []
    p = Path(p)
    files = sorted(p.rglob("sweep.jsonl")) if p.is_dir() else [p]
    for f in files:
        for line in open(f):
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def exact_rule(groups):
    """groups: {length: [values]}. Returns {length: '(v & M) == V'} where a
    single mask/value characterises that length exactly."""
    rules = {}
    allv = [v for vs in groups.values() for v in vs]
    for L, vs in groups.items():
        other = [v for v in allv if v not in set(vs)]
        if not other:
            rules[L] = "all values"
            continue
        m = 0xFF
        first = vs[0]
        for v in vs:
            m &= ~(v ^ first) & 0xFF
        val = first & m
        if m and all((v & m) == val for v in vs) and all((v & m) != val for v in other):
            rules[L] = "(value & 0x%02x) == 0x%02x" % (m, val)
        else:
            rules[L] = None
    return rules


def qtables(recs):
    """Arms Q/Q2: the measured length of `04 b1 b2 b3` as a joint function of
    byte+1 and byte+2. Emitted as an explicit MAP rather than a fitted formula,
    because the map is what was measured; the regularities are described in
    RESULTS.md and are not smoothed over here."""
    out = collections.defaultdict(dict)
    for r in recs:
        if r.get("arm") not in ("Q", "Q2"):
            continue
        out[r["field"]][r["value"]] = r.get("measured_length")
    tables = {}
    for k, m in out.items():
        part = collections.defaultdict(list)
        for v, L in sorted(m.items()):
            part[str(L)].append(v)
        low3 = collections.defaultdict(collections.Counter)
        for v, L in m.items():
            low3[str(L)][v & 7] += 1
        tables[k] = {"n": len(m),
                     "by_length": {L: len(v) for L, v in sorted(part.items())},
                     "values_by_length": {L: v for L, v in sorted(part.items())},
                     "low3_of_swept_byte": {L: dict(c) for L, c in sorted(low3.items())}}
    return tables


def main():
    allrecs = load(sys.argv[1])
    qt = qtables(allrecs)
    if qt:
        Path(HERE / "length_map_q.json").write_text(
            json.dumps(qt, indent=1, sort_keys=True) + "\n")
        for k, v in sorted(qt.items()):
            print("%-26s n=%d  %s" % (k, v["n"], v["by_length"]))
    recs = [r for r in allrecs
            if r.get("arm") == "N" and str(r.get("field", "")).startswith("lenmap")]
    if not recs:
        return
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    outcomes = collections.defaultdict(collections.Counter)
    for r in recs:
        cand = r["case"].split("_")[1]
        pos = r["field"]
        outcomes[(cand, pos)][r["outcome"]] += 1
        L = r.get("measured_length")
        if L is None:
            continue
        by[(cand, pos)][L].append(r["value"])
    out = {}
    for k, groups in sorted(by.items()):
        cand, pos = k
        rules = exact_rule({L: sorted(v) for L, v in groups.items()})
        out["%s@%s" % (pos, cand)] = {
            "measured": {str(L): len(v) for L, v in sorted(groups.items())},
            "exact_rule_per_length": {str(L): rules[L] for L in sorted(rules)},
            "outcomes": dict(outcomes[k]),
            "unmeasurable": outcomes[k].total() - sum(len(v) for v in groups.values()),
        }
    Path(HERE / "length_rule.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    for k, v in sorted(out.items()):
        print("%-28s %s   %s" % (k, v["measured"], v["exact_rule_per_length"]))


if __name__ == "__main__":
    main()
