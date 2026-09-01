#!/usr/bin/env python3
"""Audit the two isolated EXP-0239 first-invalid destination captures."""

import json
import sys
from pathlib import Path


def load(root):
    root = Path(root)
    rows = [json.loads(line) for line in open(root / "sweep.jsonl")]
    boundary = [row for row in rows if row.get("kind") == "cvt_i2f_boundary"]
    manifest = json.loads((root / "05_run_manifest.json").read_text())
    pre = json.loads((root / "gpu_pre.json").read_text())
    post = json.loads((root / "gpu_post.json").read_text())
    procs = [json.loads(line) for line in open(root / "procs.jsonl")]
    rec = boundary[0] if len(boundary) == 1 else {}
    body = rec.get("under_test", [])
    probe = rec.get("cvt_i2f_boundary_probe", {})
    result = {
        "run": root.name,
        "records": len(rows),
        "slot_probes": sum(row.get("kind") == "s0_slot" for row in rows),
        "boundary_records": len(boundary),
        "manifest_dispatches": manifest.get("dispatched"),
        "status": rec.get("status"),
        "errorhang": bool(probe.get("errorhang")),
        "body_exact": bool(len(body) == 1
                           and body[0].get("mnemonic") == "cvt_i2f"
                           and body[0].get("decoded_actual", {}).get("dst") == 192
                           and len(bytes.fromhex(body[0].get("bytes", ""))) == 8),
        "dispatched_bytes_verified": rec.get("dispatched_bytes_verified"),
        "donor_fields": len(rec.get("donor_fields", [])),
        "carrier_fields": rec.get("ledger", {}).get("CARRIER"),
        "copied_fields": rec.get("ledger", {}).get("COPIED"),
        "recovery_delta": post["recovery_count"] - pre["recovery_count"],
        "last_recovery_changed": post.get("last_recovery_time") != pre.get("last_recovery_time"),
        "foreign_samples": sum(bool(row.get("n_foreign")) for row in procs),
        "foreign_runner_samples": sum(bool(row.get("n_foreign_runner")) for row in procs),
        "compiler_service_samples": sum(bool(row.get("n_compiler_svc")) for row in procs),
        "responsive_recorded": (root / "07_responsive.txt").exists()
                               and (root / "07_responsive.txt").stat().st_size > 0,
    }
    result["pass"] = bool(
        result["records"] == 9 and result["slot_probes"] == 8
        and result["boundary_records"] == 1 and result["manifest_dispatches"] == 9
        and result["status"] == "CMDBUF_ERROR" and result["errorhang"]
        and result["body_exact"] and result["dispatched_bytes_verified"]
        and result["donor_fields"] == 0 and result["carrier_fields"] == 0
        and result["copied_fields"] == 0 and result["recovery_delta"] == 1
        and result["last_recovery_changed"] and result["foreign_samples"] == 0
        and result["foreign_runner_samples"] == 0
        and result["compiler_service_samples"] == 0 and result["responsive_recorded"])
    return result


def main(argv):
    if len(argv) != 3:
        raise SystemExit("usage: boundary239.py BOUNDARY01 BOUNDARY02")
    runs = [load(argv[1]), load(argv[2])]
    result = {"runs": runs, "pass": all(run["pass"] for run in runs)}
    out = Path(__file__).with_name("boundary_result.json")
    out.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    print(json.dumps(result, indent=1, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
