#!/usr/bin/env python3
"""EXP-0141 analysis: per-arm outcome tables and per-field working-value sets.

Reads ONLY the append-only raw/<run>/sweep.jsonl files. Never mutates raw.
Usage: python3 -B analysis/summarize.py [run_id ...]
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent


def load(run):
    p = EXP / "raw" / run / "sweep.jsonl"
    return [json.loads(l) for l in p.open()] if p.exists() else []


def compress(vals):
    """[1,3,5,...] -> compact run/stride description."""
    if not vals:
        return "none"
    vs = sorted(set(vals))
    if len(vs) == 1:
        return str(vs[0])
    d = {vs[i + 1] - vs[i] for i in range(len(vs) - 1)}
    if len(d) == 1:
        st = d.pop()
        return "%d..%d step %d (%d values)" % (vs[0], vs[-1], st, len(vs))
    runs, s, prev = [], vs[0], vs[0]
    for v in vs[1:]:
        if v == prev + 1:
            prev = v
            continue
        runs.append((s, prev)); s = prev = v
    runs.append((s, prev))
    txt = ",".join("%d" % a if a == b else "%d-%d" % (a, b) for a, b in runs[:8])
    return "%s%s (%d values)" % (txt, "..." if len(runs) > 8 else "", len(vs))


def arm_table(rows):
    order, seen = [], set()
    for r in rows:
        if r["arm"] not in seen:
            seen.add(r["arm"]); order.append(r["arm"])
    out = []
    for a in order:
        rs = [r for r in rows if r["arm"] == a]
        c = collections.Counter(r["outcome"] for r in rs)
        ok = [r["value"] for r in rs if r["outcome"] == "ok" and not str(r["field"]).startswith("_")]
        out.append({"arm": a, "instr": rs[0]["instr"], "field": rs[0]["field"],
                    "carrier": rs[0]["carrier"], "n": len(rs),
                    "outcomes": dict(c), "n_ok": len(ok),
                    "ok_values": compress(ok),
                    "invalid": c.get("invalid_run", 0) + c.get("nondeterministic", 0)})
    return out


def main():
    runs = sys.argv[1:] or ["m4-20260828-run11", "m4-20260828-run12"]
    report = {}
    for run in runs:
        rows = load(run)
        if not rows:
            continue
        report[run] = {"records": len(rows), "arms": arm_table(rows)}
        health = [r for r in rows if r["arm"] == "_HEALTH"]
        report[run]["health"] = {"checks": len(health),
                                 "failures": sum(1 for r in health if not r["match"])}
        report[run]["control_violations"] = [
            {"arm": r["arm"], "field": r["field"], "match": r["match"],
             "expect": r["expect_match"]}
            for r in rows if r["expect_match"] is not None
            and r["match"] != r["expect_match"] and r["arm"] != "_HEALTH"]
        report[run]["fault_classes"] = dict(collections.Counter(
            fc for r in rows for fc in (r.get("fault_classes") or [])))
    if len(report) == 2:
        a, b = [load(r) for r in runs]
        ka = {(r["carrier"], r["arm"], r["i"]): r for r in a if r["arm"] != "_HEALTH"}
        kb = {(r["carrier"], r["arm"], r["i"]): r for r in b if r["arm"] != "_HEALTH"}
        common = set(ka) & set(kb)
        diff = [k for k in common if ka[k]["outcome"] != kb[k]["outcome"]]
        report["cross_run"] = {
            "common_cases": len(common),
            "only_in_one": len(set(ka) ^ set(kb)),
            "outcome_disagreements": len(diff),
            "agreement_pct": round(100.0 * (len(common) - len(diff)) / max(1, len(common)), 3),
            "examples": [{"carrier": k[0], "arm": k[1], "i": k[2], "value": ka[k]["value"],
                          "run01": ka[k]["outcome"], "run02": kb[k]["outcome"]}
                         for k in sorted(diff)[:40]]}
    (EXP / "analysis" / "summary.json").write_text(
        json.dumps(report, indent=1, sort_keys=True) + "\n")
    for run, d in sorted(report.items()):
        if run == "cross_run":
            print("cross-run:", json.dumps({k: v for k, v in d.items() if k != "examples"}))
            continue
        print("== %s: %d records, health %d/%d ok, %d control violations"
              % (run, d["records"], d["health"]["checks"] - d["health"]["failures"],
                 d["health"]["checks"], len(d["control_violations"])))
        for a in d["arms"]:
            print("  %-24s %-20s n=%-5d ok=%-5d %s" %
                  (a["arm"], a["field"], a["n"], a["n_ok"], a["ok_values"][:70]))


if __name__ == "__main__":
    main()
