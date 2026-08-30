#!/usr/bin/env python3
"""EXP-0184 freeze/refresh of CAPTURE_CONTRACT.json.

`python3 analysis/contract.py freeze` writes the contract; `... check` re-hashes
and exits non-zero on any drift. The contract records the repo revision AT
PRE-REGISTRATION TIME and captures are compared against THAT recorded value, not
against live `HEAD`: the orchestrator commits sibling experiments continuously
and a cross-run gate written as "HEAD must not move" aborts mid-sequence through
no fault of this experiment (SUBAGENT_BRIEF; it happened to EXP-0082).
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
FILES = ["PRE_REGISTRATION.md", "README.md", "run.py",
         "harness/carriers184.py", "harness/locate184.py",
         "harness/saferunner184.py", "harness/sync.sh",
         "harness/verify_remote.py", "harness/agxrun_persist_as.m",
         "analysis/census.py", "analysis/gen_arms.py", "analysis/verdicts.py",
         "analysis/contract.py", "analysis/gen_pilot.py",
         "harness/arms184.json", "harness/arms_pilot.json",
         "kernels/k_cs184.metal", "kernels/k_cvt184.metal",
         "kernels/k_cf184.metal", "kernels/k_rq184.metal"]
PINNED = ["pinned/db.json", "pinned/isadb.py", "pinned/agxparse.py",
          "pinned/persistrun.py", "pinned/shdump.m"]


def sha(p):
    return hashlib.sha256((EXP / p).read_bytes()).hexdigest()


def build():
    rev = subprocess.check_output(["git", "-C", str(EXP), "rev-parse", "HEAD"],
                                  text=True).strip()
    dirty = subprocess.check_output(["git", "-C", str(EXP), "status",
                                     "--porcelain"], text=True).strip()
    return {
        "experiment": "EXP-0184-g17p-onefield-b",
        "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo_revision_at_pre_registration": rev,
        "repo_dirty_paths_at_pre_registration": len(dirty.splitlines()),
        "gate_note": "captures are compared against the RECORDED revision above, "
                     "never against live HEAD (SUBAGENT_BRIEF / EXP-0082)",
        "target": {"device": "Apple A18 Pro / G17P", "host": "users-MacBook-Neo.local",
                   "ip": "192.168.10.243", "arch": "applegpu_g17p",
                   "os": "macOS 26.6", "cores": 5, "family": "Apple9"},
        "remote_workdir": "~/agxre/EXP-0184",
        "timeouts_s": {"request_compute": 8.0, "request_rt": 20.0,
                       "shdump": 600, "ssh_connect": 15},
        "gate": {"gated_runs": 2,
                 "per_value_cross_run_agreement_min_pct": 99.0,
                 "movement_rule": "moved >= 2 * disagree AND moved >= 1",
                 "movement_rule_note":
                     "NOT `moved >= 2 * max(disagree,1)`: that form silently "
                     "cannot promote any width-1 field, since a 1-bit field has "
                     "only 2 values and moved can be 1.",
                 "hang_budget": None,
                 "hang_budget_note":
                     "DELIBERATELY ABSENT. FIELD-SWEEP-PROTOCOL 3(c): a per-field "
                     "hang budget cannot characterise a CONTIGUOUS hazard -- it "
                     "guarantees the region is never mapped. Every value is "
                     "dispatched."},
        "raw_schema": ["carrier", "arm", "instr", "field", "value", "bytes",
                       "token", "observed", "oracle", "match", "outcome",
                       "status", "statuses", "fault_classes",
                       "innocent_retries", "role", "occ", "off", "instr_len",
                       "start", "width", "note", "ts"],
        "outcomes": ["ok", "silent_zero", "wrong_value", "fault", "hang",
                     "undecodable", "not_written", "invalid_run",
                     "nondeterministic", "measurement_failure",
                     "carrier_ready", "carrier_start_failed"],
        "authored_sha256": {f: sha(f) for f in FILES},
        "pinned_inputs_sha256": {f: sha(f) for f in PINNED},
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    p = EXP / "CAPTURE_CONTRACT.json"
    new = build()
    if mode == "freeze":
        p.write_text(json.dumps(new, indent=1, sort_keys=True))
        print("frozen", p)
        return 0
    old = json.loads(p.read_text())
    bad = []
    for k, v in old["authored_sha256"].items():
        if new["authored_sha256"].get(k) != v:
            bad.append("DRIFT %s" % k)
    for k, v in old["pinned_inputs_sha256"].items():
        if new["pinned_inputs_sha256"].get(k) != v:
            bad.append("DRIFT %s" % k)
    for b in bad:
        print(b)
    print("contract check: %d drifted" % len(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
