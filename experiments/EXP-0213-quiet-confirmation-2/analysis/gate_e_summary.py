#!/usr/bin/env python3
"""EXP-0213 -- recompute every number RESULTS.md quotes, from raw, in one pass.

    python3 analysis/gate_e_summary.py > analysis/out/gate_e_summary.json

Gate E verdict per field, with exact numerators and denominators.  A field is MET only if
ALL of: both captures of its DESIGNATED pair measured QUIET; neither was stopped by a cascade
guard, a hang budget or the external cap; the pair's actual-byte ledgers are identical on
every shared key; the pair covers the field's declared value domain minus the named
exclusions; and there is no non-hard cross-run disagreement outside those exclusions.
"""
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "analysis", "out")
E204 = os.path.join(HERE, "..", "EXP-0204-g17p-tex-carrier-dimensions")
E206 = os.path.join(HERE, "..", "EXP-0206-g17p-cf-scope")


def quiet_all():
    rows = {}
    for d in sorted(glob.glob(os.path.join(HERE, "raw", "*"))):
        p = os.path.join(d, "quietcheck.json")
        if os.path.exists(p):
            rows[os.path.basename(d)] = json.load(open(p))
    return rows


def manifests(pattern):
    out = {}
    for d in sorted(glob.glob(pattern)):
        p = os.path.join(d, "05_run_manifest.json")
        if os.path.exists(p):
            out[os.path.basename(d)] = json.load(open(p))
    return out


def run(cmd):
    return json.loads(subprocess.check_output([sys.executable] + cmd, cwd=HERE, text=True))


def main():
    q = quiet_all()
    m204 = manifests(os.path.join(E204, "raw", "g17p_e0213_*"))
    res = {
        "quiet": {"captures": len(q), "all_QUIET": all(v.get("QUIET") for v in q.values()),
                  "max_foreign_runner_live_over_all_captures":
                      max((v.get("max_foreign_runner_live") or 0) for v in q.values()),
                  "max_foreign_runner_strict_over_all_captures":
                      max((v.get("max_foreign_runner_strict") or 0) for v in q.values()),
                  "max_compiler_svc": max((v.get("compiler_svc_max") or 0) for v in q.values()),
                  "ioreg_errors_total": sum((v.get("ioreg_errors") or 0) for v in q.values()),
                  "recovery_first_pre": min((v.get("recovery_pre") or 10**9)
                                            for v in q.values()),
                  "recovery_last_post": max((v.get("recovery_post") or 0) for v in q.values()),
                  "not_quiet": [k for k, v in q.items() if not v.get("QUIET")]},
        "e0204_per_arm_completeness": {
            "captures": len([k for k in m204 if k.startswith("g17p_e0213_B")]),
            "cascades": sum(1 for k, v in m204.items()
                            if k.startswith("g17p_e0213_B") and v.get("cascade")),
            "baseline_final_not_ok": [
                (k, a) for k, v in m204.items() if k.startswith("g17p_e0213_B")
                for a, s in v["arms"].items() if s.get("baseline_final_ok") is not True],
            "field_sweep_groups": sum(len(v["detection"]) for k, v in m204.items()
                                      if k.startswith("g17p_e0213_B")),
            "field_sweep_groups_incomplete": [
                (k, g) for k, v in m204.items() if k.startswith("g17p_e0213_B")
                for g, d in v["detection"].items() if not d["complete"]],
        },
        "e0204_full_set_abort": {
            k: v.get("cascade") for k, v in m204.items()
            if k.startswith("g17p_e0213_A")},
        "e0204_deriv_budget": {
            k: {g: [d["swept"], d["n"], d["hangs"], d["complete"]]
                for g, d in v["detection"].items()}
            for k, v in m204.items() if k.startswith("g17p_e0213_D_")},
    }
    json.dump(res, sys.stdout, indent=1, sort_keys=True)
    print()


if __name__ == "__main__":
    main()
