#!/usr/bin/env python3
"""EXP-0210 -- decide Q1..Q4 over one capture's quiet samples.  Runs on the repo host.

    python3 harness/quietcheck.py raw/<tag>/quiet.jsonl

Prints a JSON verdict.  Q1 zero foreign GPU processes in every sample; Q2 recoveryCount
unchanged first-to-last; Q3 fLastSubmissionPID never a PID outside our subtree (reported as
the set of observed submitter PIDs, adjudicated by the caller against the known-idle
SecurityAgent PID recorded at freeze); Q4 sampler alive throughout.
"""
import json
import sys


def main():
    recs = []
    with open(sys.argv[1]) as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                recs.append(json.loads(ln))
    if not recs:
        print(json.dumps({"error": "no samples"}))
        return 2
    n = len(recs)
    foreign = [r.get("n_foreign", -1) for r in recs]
    # AMENDMENT 01: Q1 is stated on dispatch runners.  Older samples (e0203_q41/q42) have no
    # n_foreign_runner key; they fall back to n_foreign and are NOT scored under the amended
    # criterion -- they are retained and reported as captured.
    amended = all("n_foreign_runner" in r for r in recs)
    frunner = [r.get("n_foreign_runner", r.get("n_foreign", -1)) for r in recs]
    comp = [r.get("n_compiler_svc", None) for r in recs]
    comp = [c for c in comp if c is not None]
    comp_rows = [pr for r in recs for pr in r.get("procs", [])
                 if pr.get("kind") == "compiler"]
    foreign_rows = [r for r in recs if r.get("n_foreign_runner", r.get("n_foreign", 0)) > 0]
    rc = [r["gpu"].get("recovery_count") for r in recs if isinstance(r.get("gpu"), dict)]
    rc = [x for x in rc if x is not None]
    subs = sorted({r["gpu"].get("last_submission_pid")
                   for r in recs if isinstance(r.get("gpu"), dict)}
                  - {None})
    busy = sorted({r["gpu"].get("busy_count")
                   for r in recs if isinstance(r.get("gpu"), dict)} - {None})
    ssc = sorted({r["gpu"].get("submissions_since_check")
                  for r in recs if isinstance(r.get("gpu"), dict)} - {None})
    rend = sorted({r["gpu"].get("renderer_util")
                   for r in recs if isinstance(r.get("gpu"), dict)} - {None})
    span = recs[-1]["ts"] - recs[0]["ts"]
    ioerr = sum(1 for r in recs if isinstance(r.get("gpu"), dict)
                and "ioreg_error" in r["gpu"])
    out = {
        "samples": n,
        "span_s": round(span, 1),
        "sample_rate_s": round(span / max(n - 1, 1), 2),
        "amended_instrument": amended,
        "Q1_zero_foreign_runner": max(frunner) == 0,
        "max_foreign_runner": max(frunner),
        "max_foreign_legacy_incl_compiler_svc": max(foreign),
        "Q1b_compiler_svc_max": (max(comp) if comp else None),
        "Q1b_compiler_svc_all_new_since_start": (
            all(pr.get("new_since_start") for pr in comp_rows) if comp_rows else None),
        "Q1b_compiler_svc_pids": sorted({pr["pid"] for pr in comp_rows}),
        "foreign_examples": [r["procs"] for r in foreign_rows[:3]],
        "Q2_recovery_stable": (len(rc) > 0 and rc[0] == rc[-1]),
        "recovery_first_last": [rc[0], rc[-1]] if rc else None,
        "Q3_submitter_pids": subs,
        "Q4_sampler_alive": (span / max(n - 1, 1)) < 10.0,
        "busy_count_values": busy,
        "submissions_since_check_values": ssc,
        "renderer_util_values": rend,
        "ioreg_errors": ioerr,
        "loadavg_max": max(r["loadavg"][0] for r in recs if "loadavg" in r),
    }
    out["QUIET"] = bool(out["Q1_zero_foreign_runner"] and out["Q2_recovery_stable"]
                        and out["Q4_sampler_alive"] and ioerr == 0)
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
