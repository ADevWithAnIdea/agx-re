#!/usr/bin/env python3
"""Audit EXP-0239 target quietness and recovery state from immutable raw files."""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
EXP = HERE.parent
RUNS = {"g17p_e0239_run01": 466, "g17p_e0239_run02": 466}


def read_json(path):
    return json.loads(path.read_text())


def main():
    result = {"runs": {}, "pass": True}
    for run, dispatches in RUNS.items():
        root = EXP / "raw" / run
        procs = [json.loads(line) for line in open(root / "procs.jsonl")]
        pre, post = read_json(root / "gpu_pre.json"), read_json(root / "gpu_post.json")
        manifest = read_json(root / "05_run_manifest.json")
        sweep = [json.loads(line) for line in open(root / "sweep.jsonl")]
        row = {
            "quiet_samples": len(procs),
            "foreign_samples": sum(bool(x.get("n_foreign")) for x in procs),
            "foreign_runner_samples": sum(bool(x.get("n_foreign_runner")) for x in procs),
            "compiler_service_samples": sum(bool(x.get("n_compiler_svc")) for x in procs),
            "recovery_delta": post["recovery_count"] - pre["recovery_count"],
            "last_recovery_unchanged": post.get("last_recovery_time") == pre.get("last_recovery_time"),
            "manifest_dispatches": manifest.get("dispatched"), "records": len(sweep),
            "hangs": manifest.get("hangs"),
            "foreign_retries": sum(x.get("foreign_retries", 0) for x in sweep),
            "runner_restarts": sum(bool(x.get("restarted")) for x in sweep),
            "non_ok_status": sum(x.get("status") != "OK" for x in sweep),
        }
        row["pass"] = bool(row["quiet_samples"] > 0 and row["foreign_samples"] == 0
                           and row["foreign_runner_samples"] == 0
                           and row["compiler_service_samples"] == 0
                           and row["recovery_delta"] == 0 and row["last_recovery_unchanged"]
                           and row["manifest_dispatches"] == dispatches
                           and row["records"] == dispatches and row["hangs"] == 0
                           and row["foreign_retries"] == 0 and row["runner_restarts"] == 0
                           and row["non_ok_status"] == 0)
        result["runs"][run] = row
        result["pass"] = result["pass"] and row["pass"]
    (HERE / "gate_e_result.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
