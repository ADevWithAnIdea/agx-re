#!/usr/bin/env python3
"""EXP-0201 CAPTURE_CONTRACT freezer. Runs on the M4 (the evidence store).

    python3 analysis/contract.py freeze      # write/refresh CAPTURE_CONTRACT.json
    python3 analysis/contract.py check       # verify the local tree matches it

A frozen contract hashes what we AUTHORED. It says nothing about what the DEVICE
is running -- `harness/verify_remote.py` is the separate step that checks that,
and it must never be chained behind the push it checks.

The repo revision is recorded HERE, at freeze time, and captures are gated
against THAT recorded value -- never against live `HEAD`. Sibling experiments
land continuously; a gate written "HEAD must not move" aborts mid-sequence
through no fault of this experiment (it happened to EXP-0082).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
AUTHORED = ["run.py", "PRE_REGISTRATION.md", "PRE_REGISTRATION-A.md",
            "README.md",
            "kernels/k_falu201.metal",
            "harness/carriers201.py", "harness/models201.py",
            "harness/locate201.py", "harness/saferunner201.py",
            "harness/gpuwatch.py", "harness/gated_run.sh", "harness/sync.sh",
            "harness/verify_remote.py",
            "analysis/gen_arms.py", "analysis/oracle_check.py",
            "analysis/verdicts.py", "analysis/contract.py",
            "analysis/maps.py", "analysis/manifest_build.py"]
PINNED = ["pinned/db.json", "pinned/isadb.py", "pinned/agxparse.py",
          "pinned/persistrun.py", "pinned/shdump.m"]


def sha(p):
    return hashlib.sha256((EXP / p).read_bytes()).hexdigest()


def git(*a):
    try:
        return subprocess.check_output(["git", "-C", str(EXP)] + list(a),
                                       text=True, timeout=30).strip()
    except Exception as e:                                      # noqa: BLE001
        return "ERR %s" % e


def build():
    arms = EXP / "harness" / "arms201.json"
    return {
        "experiment": "EXP-0201-g17p-float-alu-sixfield",
        "frozen_utc": subprocess.check_output(
            ["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"], text=True).strip(),
        "target": {"device": "Apple A18 Pro / G17P", "arch": "applegpu_g17p",
                   "accelerator": "AGXAcceleratorG17P", "cores": 5,
                   "host": "192.168.170.254", "os": "26.6",
                   "metal_family": "Apple9"},
        "repo": {"revision": git("rev-parse", "HEAD"),
                 "dirty": bool(git("status", "--porcelain"))},
        "fields": [
            {"instr": "falu3", "field": "op", "start": 16, "width": 8, "values": 256},
            {"instr": "falu3_ext", "field": "op", "start": 16, "width": 8, "values": 256},
            {"instr": "fspecial_est", "field": "srcA", "start": 8, "width": 8, "values": 256},
            {"instr": "falu3_srcmod12", "field": "opsel", "start": 16, "width": 3, "values": 8},
            {"instr": "falu3_srcmod12", "field": "ctrl", "start": 32, "width": 7, "values": 128},
            {"instr": "copysign", "field": "operands", "start": 24, "width": 8, "values": 256},
        ],
        "timeouts": {"request_s": 8.0, "confirm_attempts": 3,
                     "innocent_retries": 3, "canary_retries": 3,
                     "compile_s": 600, "ssh_alarm_s": 180},
        "amendment": {
            "name": "AMENDMENT A",
            "trigger": "RE_EXPERIMENT_PROCESS_CORRECTIONS.md (normative, added "
                       "while runs 01-04 were executing)",
            "frozen_before_run_ids": ["g17p_20260830_a_run01",
                                      "g17p_20260830_a_run02"],
            "retained_unamended_runs": ["g17p_20260830_run01",
                                        "g17p_20260830_run02",
                                        "g17p_20260830_run03",
                                        "g17p_20260830_run04"],
            "adds": ["Gate A caller->actual-byte ledger per case",
                     "Gate C adversarial float inputs (signed zero, inf, NaN, "
                     "denormal, 2^24 rounding boundary)",
                     "Gate E reversed case order + strict quiet requirement",
                     "six independent verdict axes"],
        },
        "gate": {"min_gated_runs": 2, "min_agree_pct": 99.0,
                 "rule": "moved >= 2*disagree AND moved > 0",
                 "min_distinct_bytes": 2,
                 "case_c_rule": "V (distinct valid payloads) <= 1 => NOT PROMOTED"},
        "authored_sha256": {p: sha(p) for p in AUTHORED},
        "pinned_inputs_sha256": {p: sha(p) for p in PINNED},
        "arms_sha256": (hashlib.sha256(arms.read_bytes()).hexdigest()
                        if arms.exists() else None),
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "freeze"
    path = EXP / "CAPTURE_CONTRACT.json"
    if mode == "freeze":
        c = build()
        path.write_text(json.dumps(c, indent=1) + "\n")
        print("frozen: %d authored + %d pinned blobs, arms=%s, rev=%s"
              % (len(c["authored_sha256"]), len(c["pinned_inputs_sha256"]),
                 (c["arms_sha256"] or "-")[:12], c["repo"]["revision"][:8]))
        return 0
    c = json.loads(path.read_text())
    bad = [p for p, h in {**c["authored_sha256"],
                          **c["pinned_inputs_sha256"]}.items() if sha(p) != h]
    for p in bad:
        print("DRIFTED since freeze: %s" % p)
    print("contract check: %d drifted" % len(bad))
    return 3 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
