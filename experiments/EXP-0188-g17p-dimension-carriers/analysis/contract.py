#!/usr/bin/env python3
"""EXP-0188 CAPTURE_CONTRACT freeze / verify / amend.

    python3 analysis/contract.py freeze            # write CAPTURE_CONTRACT.json
    python3 analysis/contract.py amend  "<reason>" # retain the old one, re-freeze
    python3 analysis/contract.py verify            # exit 0 iff every LOCAL blob matches

`verify` checks the blobs on THIS machine. It says nothing about the device --
that is `harness/verify_remote.py`, which must be run as its OWN command after
every push (a contract hashes what you AUTHORED, not what the DEVICE is running).

The repo revision is recorded ONCE, at freeze time, and captures are gated on the
authored blob hashes, never on live HEAD: sibling experiments land continuously
and a "HEAD must not move" gate aborts mid-sequence through no fault of this
experiment (EXP-0082).
"""
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent
CONTRACT = EXP / "CAPTURE_CONTRACT.json"
PREFREEZE = EXP / "raw" / "prefreeze"

BLOBS = ["PRE_REGISTRATION.md", "README.md", "run.py",
         "harness/carriers188.py", "harness/locate188.py",
         "harness/saferunner188.py", "harness/targets188.py",
         "harness/sync.sh", "harness/verify_remote.py",
         "kernels/k_cf188.metal", "kernels/k_sd188.metal", "kernels/k_ia188.metal",
         "analysis/census.py", "analysis/gen_arms.py", "analysis/verdicts.py",
         "analysis/contract.py",
         "pinned/db.json", "pinned/isadb.py", "pinned/agxparse.py",
         "pinned/persistrun.py", "pinned/shdump.m"]
OPTIONAL = ["harness/arms188.json"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    blobs = {}
    for rel in BLOBS:
        p = EXP / rel
        if not p.exists():
            sys.stderr.write("FATAL: contract blob missing: %s\n" % rel)
            raise SystemExit(2)
        blobs[rel] = sha(p)
    for rel in OPTIONAL:
        p = EXP / rel
        if p.exists():
            blobs[rel] = sha(p)
    try:
        rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(EXP),
                                      text=True, timeout=30).strip()
    except Exception:                                           # noqa: BLE001
        rev = "unknown"
    return {
        "experiment": "EXP-0188",
        "frozen_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "repo_revision_at_pre_registration":
            "45d97d6237c9b0324ed97aba7ad0a2aa83193384",
        "repo_revision_at_freeze": rev,
        "gate_is_on": "authored blob hashes, NOT live HEAD (EXP-0082)",
        "target": {"host": "users-MacBook-Neo.local", "ip": "192.168.10.243",
                   "user": "user", "soc": "T8140", "gpu": "AGXAcceleratorG17P",
                   "arch": "applegpu_g17p", "cores": 5, "os": "macOS 26.6",
                   "family": "Apple9", "remote_dir": "~/agxre/EXP-0188"},
        "concurrency": "UNLOCKED and concurrent with sibling experiments "
                       "(FIELD-SWEEP-PROTOCOL section 7). No GPU lease exists. "
                       "concurrent_gpu_procs is sampled into every run's env.json.",
        "timeouts_s": {"request_watchdog": 8.0, "compile": 600,
                       "remote_command": 120, "runner_ready": 30},
        "abort_path": "NONE. No per-field or per-arm hang budget anywhere "
                      "(FIELD-SWEEP-PROTOCOL 3c). Every value of every arm is "
                      "dispatched.",
        "gate": {"runs": 2,
                 "agree_min_pct": 99.0,
                 "movement_rule": "moved >= 2*disagree AND moved >= 1",
                 "movement_rule_rejected": "moved >= 2*max(disagree,1) -- cannot "
                                           "promote any width-1 field",
                 "detection_power": "at least one control field of the SAME "
                                    "instruction at the SAME occurrence must move",
                 "measurement_failure_ceiling_pct": 1.0},
        "raw_schema": {
            "path": "raw/<run_id>/sweep.jsonl",
            "one_json_object_per_case_flushed_and_fsynced": True,
            "keys": ["carrier", "arm", "instr", "field", "value", "bytes",
                     "token", "observed", "oracle", "match", "outcome",
                     "status", "statuses", "fault_classes", "innocent_retries",
                     "role", "occ", "off", "instr_len", "start", "width",
                     "note", "ts"],
            "outcomes": ["ok", "silent_zero", "wrong_value", "not_written",
                         "fault", "hang", "nondeterministic", "invalid_run",
                         "measurement_failure", "carrier_ready",
                         "carrier_start_failed"],
            "env": "raw/<run_id>/env.json"},
        "run_ids": "g17p_<YYYYMMDD>_runNN -- NEVER reused; a partial capture is "
                   "retained as-is and the replacement takes a NEW id",
        "authored_sha256": blobs,
    }


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "freeze":
        if CONTRACT.exists():
            sys.stderr.write("REFUSING: contract exists; use `amend \"reason\"`\n")
            return 2
        CONTRACT.write_text(json.dumps(build(), indent=1, sort_keys=True))
        print("froze", CONTRACT)
        return 0
    if cmd == "amend":
        reason = sys.argv[2] if len(sys.argv) > 2 else "(no reason given)"
        PREFREEZE.mkdir(parents=True, exist_ok=True)
        n = 1
        while (PREFREEZE / ("CAPTURE_CONTRACT.v%d.json" % n)).exists():
            n += 1
        (PREFREEZE / ("CAPTURE_CONTRACT.v%d.json" % n)).write_bytes(
            CONTRACT.read_bytes())
        doc = build()
        doc["amendment"] = {"n": n + 1, "reason": reason,
                            "supersedes": "raw/prefreeze/CAPTURE_CONTRACT.v%d.json" % n}
        CONTRACT.write_text(json.dumps(doc, indent=1, sort_keys=True))
        print("amended to v%d (previous retained as v%d): %s" % (n + 1, n, reason))
        return 0
    doc = json.loads(CONTRACT.read_text())
    bad = []
    for rel, want in sorted(doc["authored_sha256"].items()):
        p = EXP / rel
        if not p.exists():
            bad.append((rel, "MISSING"))
        elif sha(p) != want:
            bad.append((rel, "STALE"))
    for rel, why in bad:
        print("%-8s %s" % (why, rel))
    print("%d/%d local blobs match" % (len(doc["authored_sha256"]) - len(bad),
                                       len(doc["authored_sha256"])))
    return 3 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
