#!/usr/bin/env python3
"""Formal cross-run gate for EXP-0235 canonical ilogic reach."""

import json
import sys
from collections import Counter
from pathlib import Path


def load(path):
    rows = [json.loads(line) for line in open(Path(path) / "sweep.jsonl")]
    return {row["name"]: row for row in rows if row.get("kind") == "ilogic_reach"}


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: formal235.py RUN01 RUN02")
    a, b = load(argv[1]), load(argv[2])
    names = sorted(set(a) | set(b))
    main_names = [n for n in names if not n.startswith("ctl_")]
    controls = [n for n in names if n.startswith("ctl_")]
    missing = [n for n in names if n not in a or n not in b]
    counts = Counter()
    failures = {key: [] for key in (
        "byte_disagreements", "observation_disagreements", "undecidable",
        "semantic", "gate_a", "donor", "source_model", "high_exact",
        "high_mod16", "high_mod32")}

    for name in main_names + controls:
        if name not in a or name not in b:
            continue
        ra, rb = a[name], b[name]
        role = ra.get("ilogic_reach_probe", {}).get("role")
        if name in main_names:
            counts[role] += 1
        for rec in (ra, rb):
            ga, body = rec.get("gate_a", {}), rec.get("under_test", [])
            if not rec.get("dispatched_bytes_verified") or ga.get("n_bad") != 0 \
                    or ga.get("n_alias") != 0 or len(body) != 1 \
                    or body[0].get("mnemonic") != "ilogic":
                failures["gate_a"].append("%s:%s" % (name, rec.get("run")))
            ledger = rec.get("ledger", {})
            if rec.get("donor_fields") or ledger.get("COPIED") or ledger.get("CARRIER"):
                failures["donor"].append("%s:%s" % (name, rec.get("run")))
        if ra.get("prog_sha256") != rb.get("prog_sha256") \
                or ra.get("under_test") != rb.get("under_test"):
            failures["byte_disagreements"].append(name)
        pa, pb = ra.get("ilogic_reach_probe", {}), rb.get("ilogic_reach_probe", {})
        if pa.get("observed") != pb.get("observed"):
            failures["observation_disagreements"].append(name)
        if name in main_names:
            if not pa.get("semantic_decidable") or not pb.get("semantic_decidable"):
                failures["undecidable"].append(name)
            if not ra.get("match") or not rb.get("match"):
                failures["semantic"].append(name)
            if role in ("semantic_a", "semantic_b"):
                reg = pa.get("register")
                expected = "exact" if reg < 64 else "mod64"
                for probe in (pa, pb):
                    models = probe.get("matching_models", [])
                    if probe.get("oracle_model") != expected or expected not in models:
                        failures["source_model"].append(name)
                    if reg >= 64 and "exact" in models:
                        failures["high_exact"].append(name)
                    if reg >= 80 and "mod16" in models:
                        failures["high_mod16"].append(name)
                    if reg >= 96 and "mod32" in models:
                        failures["high_mod32"].append(name)

    control_fired = [n for n in controls if n in a and n in b
                     and not a[n].get("match") and not b[n].get("match")
                     and a[n].get("bucket_ok") and b[n].get("bucket_ok")]
    expected_counts = {"semantic_a": 128, "semantic_b": 128, "destination": 16}
    result = {
        "runs": [argv[1], argv[2]], "expected_counts": expected_counts,
        "seen_counts": dict(counts), "controls_seen": len(controls),
        "control_fired": control_fired, "missing_cross_run": missing,
        **{key: sorted(set(value)) for key, value in failures.items()},
    }
    result["pass"] = bool(dict(counts) == expected_counts and len(controls) == 2
                          and len(control_fired) == 2 and not missing
                          and all(not value for value in failures.values()))
    out = Path(__file__).with_name("formal_result.json")
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps({
        "pass": result["pass"], "seen_counts": result["seen_counts"],
        "controls_seen": len(controls), "controls_fired": len(control_fired),
        **{key: len(set(value)) for key, value in failures.items()},
        "missing": len(missing),
    }, indent=1, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
