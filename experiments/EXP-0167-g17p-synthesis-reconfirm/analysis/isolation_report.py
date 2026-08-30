#!/usr/bin/env python3
"""EXP-0167: turn `raw/isolation/*.jsonl` into the isolation evidence RESULTS.md
quotes, and compare the two witness-gated 5-repeat passes (EXP-0158's contended
one against this experiment's isolated one) case by case.

No GPU. `EXP-0158-*` is read-only.
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
PRIOR = EXP.parent / "EXP-0158-g17p-generator-synthesis"


def load(p):
    p = Path(p)
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def isolation():
    out = {}
    for f in sorted((EXP / "raw" / "isolation").glob("*.jsonl")):
        rows = [r for r in load(f) if "n_foreign" in r]
        if not rows:
            continue
        foreign_rows = [r for r in rows if r["n_foreign"]]
        # every distinct process ever reported foreign, with why we can or cannot
        # attribute it: `ps` renders a process whose argv is momentarily
        # unreadable (fork/exec transition) as "(name)" in BOTH comm and args.
        procs = {}
        for r in foreign_rows:
            for p in r["foreign"]:
                procs.setdefault((p["comm"], p["args"]), []).append(
                    {"utc": r["utc"], "pid": p["pid"], "ppid": p["ppid"],
                     "etime": p["etime"], "cpu": p["cpu"]})
        out[f.name] = {
            "samples": len(rows),
            "span_seconds": round(rows[-1]["t"] - rows[0]["t"], 1),
            "first_utc": rows[0]["utc"], "last_utc": rows[-1]["utc"],
            "samples_with_foreign": len(foreign_rows),
            "max_concurrent_foreign": max(r["n_foreign"] for r in rows),
            "max_concurrent_mine": max(r.get("n_mine", 0) for r in rows),
            "max_unresolved_unreadable": max(
                r.get("n_unresolved_unreadable", 0) for r in rows),
            "mtlcompiler_instances": sorted(set(r["n_mtlcompiler"] for r in rows)),
            "samples_with_busy_mtlcompiler": sum(
                1 for r in rows if r["mtlcompiler_busy"]),
            "distinct_foreign_processes": [
                {"comm": k[0], "args": k[1], "n_samples": len(v), "sightings": v[:6],
                 "argv_unreadable": k[1].strip().startswith("(") and k[1].strip().endswith(")")}
                for k, v in procs.items()],
            "loadavg_first": rows[0]["loadavg"], "loadavg_last": rows[-1]["loadavg"],
        }
    return out


def reconfirm_compare():
    iso = {}
    for name in ("reconfirm_iso.jsonl", "reconfirm_iso_stratified.jsonl"):
        for r in load(EXP / "work" / "reconfirm" / name):
            iso[r["name"]] = r
    pri = dict((r["name"], r) for r in
               load(PRIOR / "work" / "reconfirm" / "reconfirm02.jsonl"))
    common = sorted(set(iso) & set(pri))
    changed, agree = [], 0
    for n in common:
        a, b = iso[n], pri[n]
        if a["majority_outcome"] != b["majority_outcome"] or (len(b["tally"]) > 1):
            changed.append({"name": n, "group": a["group"],
                            "iso_tally": a["tally"], "iso_majority": a["majority_outcome"],
                            "iso_discards": a["discarded_cascade_attempts"],
                            "prior_tally": b["tally"], "prior_majority": b["majority_outcome"],
                            "prior_discards": b["discarded_cascade_attempts"],
                            "prior_was_MIXED": len(b["tally"]) > 1,
                            "majority_flipped": a["majority_outcome"] != b["majority_outcome"]})
        else:
            agree += 1
    return {
        "iso_cases": len(iso),
        "iso_observations": sum(r["reps"] for r in iso.values()),
        "iso_MIXED": sum(1 for r in iso.values() if len(r["tally"]) > 1),
        "iso_discarded_cascade_attempts": sum(
            r["discarded_cascade_attempts"] for r in iso.values()),
        "iso_outcome_counts": dict(Counter(r["majority_outcome"] for r in iso.values())),
        "prior_cases": len(pri),
        "prior_observations": sum(r["reps"] for r in pri.values()),
        "prior_MIXED": sum(1 for r in pri.values() if len(r["tally"]) > 1),
        "prior_discarded_cascade_attempts": sum(
            r["discarded_cascade_attempts"] for r in pri.values()),
        "prior_outcome_counts": dict(Counter(r["majority_outcome"] for r in pri.values())),
        "common_cases": len(common),
        "agreed_and_prior_was_unanimous": agree,
        "differed_or_prior_was_mixed": changed,
        "majority_flipped": [c for c in changed if c["majority_flipped"]],
    }


def cascade():
    out = {}
    for rid in ("g17p-20260830-iso01", "g17p-20260830-iso02"):
        rows = load(EXP / "raw" / rid / "03_cascade.jsonl")
        out[rid] = {"checks": len(rows), "ok": sum(1 for r in rows if r["witness_ok"])}
    for rid in ("g17p-20260830-run03", "g17p-20260830-run04"):
        rows = load(PRIOR / "raw" / rid / "03_cascade.jsonl")
        out[rid] = {"checks": len(rows), "ok": sum(1 for r in rows if r["witness_ok"])}
    return out


def main():
    rep = {"isolation": isolation(), "reconfirm_compare": reconfirm_compare(),
           "cascade_witness": cascade()}
    (HERE / "isolation_report.json").write_text(
        json.dumps(rep, indent=2, sort_keys=True) + "\n")
    print(json.dumps(rep, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
