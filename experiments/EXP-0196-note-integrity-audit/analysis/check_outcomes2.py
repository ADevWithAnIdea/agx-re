#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0196 -- second pass at the `outcomes {...}` histograms, this time using
the CROSS-RUN GATE the producing experiments document, instead of a naive
per-run count.

Pass 1 (check_outcomes.py) counted every record in one run and reported 20
mismatches.  Reading EXP-0154 analysis/verdicts.py:167-181 shows why: a case is
DROPPED if any run recorded `victim: true` (an innocent-victim command-buffer
error) and DROPPED if its `outcome` disagrees across runs.  Those drops are the
whole difference -- e.g. `fault: 64` naive vs `fault: 4` gated.  Reporting pass
1's mismatches as note defects would have been a method artefact, so pass 1 is
kept in the tree as the negative control for this one.

Here the gate is applied: cases keyed by `idx`, victim-excluded,
disagreement-excluded, over every subset of the cited experiment's runs that
contains at least two, plus each single run.  A claim is SUPPORTED if ANY of
those reproduces it exactly.

Read-only.  Writes analysis/outcomes_check2.json.
"""
import ast, collections, glob, itertools, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXPS = os.path.join(ROOT, "experiments")
RX = re.compile(r"carrier ([^;|]+?); outcomes (\{[^}]*\})")
EMIT = ("hardware-run", "isolated-byte-diff")

_runs = {}


def load_run(path):
    if path in _runs:
        return _runs[path]
    d = {}
    p = os.path.join(path, "sweep.jsonl")
    if os.path.exists(p):
        for ln in open(p, "rb"):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            k = r.get("idx")
            if k is None:
                k = (r.get("instr"), r.get("field"), r.get("carrier"), r.get("value"),
                     r.get("byte_index"))
            d[k] = r
    _runs[path] = d
    return d


def gated_hist(paths):
    loaded = [load_run(p) for p in paths]
    keys = set()
    for L in loaded:
        keys |= set(L)
    h = collections.defaultdict(collections.Counter)
    for k in keys:
        rs = [L[k] for L in loaded if k in L]
        if not rs:
            continue
        if any(r.get("victim") for r in rs):
            continue
        if any(a.get("victim") for r in rs for a in (r.get("attempts") or [])
               if isinstance(a, dict)):
            continue
        if len({r.get("outcome") for r in rs}) > 1:
            continue
        r = rs[0]
        h[(r.get("instr"), r.get("field"), r.get("carrier"))][r.get("outcome")] += 1
    return h


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    out = {}
    for m, entry in sorted(val["instructions"].items()):
        for f, r in sorted(entry.items()):
            if not isinstance(r, dict):
                continue
            hits = RX.findall(r.get("note") or "")
            if not hits:
                continue
            key = "%s.%s" % (m, f)
            rundirs = []
            for ev in (r.get("evidence") or []):
                for d in sorted(glob.glob(os.path.join(EXPS, ev.split("/")[0] + "*"))):
                    for rd in sorted(glob.glob(os.path.join(d, "raw", "*"))):
                        if os.path.isdir(rd) and os.path.exists(os.path.join(rd, "sweep.jsonl")):
                            rundirs.append(rd)
            rows = []
            for carrier, hist_s in hits:
                try:
                    claim = dict(ast.literal_eval(hist_s))
                except Exception:
                    continue
                verdict, best, how = "NO-RAW", None, None
                combos = [(p,) for p in rundirs]
                for n in range(2, min(len(rundirs), 4) + 1):
                    combos += list(itertools.combinations(rundirs, n))
                for combo in combos:
                    got = gated_hist(list(combo)).get((m, f, carrier.strip()))
                    if got is None:
                        continue
                    got = dict(got)
                    if got == claim:
                        verdict, best, how = "SUPPORTED", got, [os.path.relpath(x, ROOT) for x in combo]
                        break
                    if best is None:
                        verdict, best, how = "MISMATCH", got, [os.path.relpath(x, ROOT) for x in combo]
                rows.append({"carrier": carrier.strip(), "claim": claim, "verdict": verdict,
                             "best_seen": best, "runs": how})
            out[key] = {"grade": "EMIT" if (r.get("label") in EMIT and f != "_instruction") else "OTHER",
                        "label": r.get("label"), "evidence": r.get("evidence"), "rows": rows}
    json.dump(out, open(os.path.join(HERE, "outcomes_check2.json"), "w"), indent=1, sort_keys=True)
    c = collections.Counter()
    for k, v in out.items():
        for row in v["rows"]:
            c[(v["grade"], row["verdict"])] += 1
    for k in sorted(c):
        print(k, c[k])
    print()
    for k, v in sorted(out.items()):
        for row in v["rows"]:
            if row["verdict"] != "SUPPORTED":
                print("%-6s %-30s %-40s claim=%s best=%s"
                      % (v["grade"], k, row["carrier"][:40], row["claim"], row["best_seen"]))


if __name__ == "__main__":
    main()
