#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""EXP-0196 -- recompute every `outcomes {...}` histogram a validation.json note
states, from the raw of the experiment(s) the row cites.

The note template is  "... carrier <C>; outcomes {'ok': 1, 'wrong_value': 12};
ok at {...}"  (EXP-0154/0155/0156/0161/0162 family) and the histogram is a
plain count of per-case `outcome` for (instr, field, carrier) in one run.  That
makes it the most directly falsifiable numeric claim in the corpus: no gate, no
threshold, just a count.

A note is SUPPORTED if SOME single committed run of SOME cited experiment
reproduces the stated histogram exactly (runs are separate captures; the note
does not say which one, so any exact match counts).  Anything else is reported
with the best run's histogram beside the claim.

Read-only.  Writes analysis/outcomes_check.json.
"""
import ast, collections, glob, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EXPS = os.path.join(ROOT, "experiments")

RX = re.compile(r"carrier ([^;|]+?); outcomes (\{[^}]*\})")
EMIT = ("hardware-run", "isolated-byte-diff")

_cache = {}


def run_hist(path):
    """-> {(instr, field, carrier): Counter(outcome)} for one raw run dir."""
    if path in _cache:
        return _cache[path]
    h = collections.defaultdict(collections.Counter)
    for p in sorted(glob.glob(os.path.join(path, "*.jsonl"))):
        if os.path.basename(p) != "sweep.jsonl":
            continue
        for ln in open(p, "rb"):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            h[(r.get("instr"), r.get("field"), r.get("carrier"))][r.get("outcome")] += 1
    _cache[path] = h
    return h


def main():
    val = json.load(open(os.path.join(ROOT, "tools/agx-isa/validation.json")))
    out = {}
    for m, entry in sorted(val["instructions"].items()):
        for f, r in sorted(entry.items()):
            if not isinstance(r, dict):
                continue
            nt = r.get("note") or ""
            hits = RX.findall(nt)
            if not hits:
                continue
            key = "%s.%s" % (m, f)
            rows = []
            for carrier, hist_s in hits:
                try:
                    claim = {k: v for k, v in ast.literal_eval(hist_s).items()}
                except Exception:
                    continue
                best, verdict = None, "NO-RAW"
                for ev in (r.get("evidence") or []):
                    for d in sorted(glob.glob(os.path.join(EXPS, ev.split("/")[0] + "*"))):
                        for rd in sorted(glob.glob(os.path.join(d, "raw", "*"))):
                            if not os.path.isdir(rd):
                                continue
                            h = run_hist(rd)
                            got = h.get((m, f, carrier.strip()))
                            if got is None:
                                continue
                            got = dict(got)
                            cand = {"run": os.path.relpath(rd, ROOT), "hist": got}
                            if got == claim:
                                best, verdict = cand, "SUPPORTED"
                                break
                            if best is None or sum(got.values()) > sum(best["hist"].values()):
                                best, verdict = cand, "MISMATCH"
                        if verdict == "SUPPORTED":
                            break
                    if verdict == "SUPPORTED":
                        break
                rows.append({"carrier": carrier.strip(), "claim": claim,
                             "verdict": verdict, "best": best})
            out[key] = {"grade": "EMIT" if (r.get("label") in EMIT and f != "_instruction") else "OTHER",
                        "label": r.get("label"), "evidence": r.get("evidence"), "rows": rows}
    json.dump(out, open(os.path.join(HERE, "outcomes_check.json"), "w"), indent=1, sort_keys=True)
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
                print("%-8s %-34s %-42s claim=%s got=%s"
                      % (v["grade"], k, row["carrier"][:42], row["claim"],
                         (row["best"] or {}).get("hist")))


if __name__ == "__main__":
    main()
