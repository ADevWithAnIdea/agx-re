#!/usr/bin/env python3
"""Assembles CAPTURE_CONTRACT.json from provenance/cases_generated.json plus
the schema/gate metadata verify.py expects. Run once to freeze the contract;
re-run only if an authored source file changes BEFORE any capture begins
(never after -- a changed hash after raw/ exists breaks the evidence chain).
"""
import json, hashlib
from pathlib import Path
HERE = Path(__file__).resolve().parent.parent
cases = json.loads((HERE / "provenance/cases_generated.json").read_text())

AUTH = ("PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json", "kernels/matrix.metal", "kernels/direct128.metal",
        "kernels/gen_direct128.py", "harness/probe.m", "run.py", "analysis.py", "make_manifest.py", "verify.py")

PAYLOAD_KEYS = ["schema","family","case","status","library_ok","library_error","pipelines","resource_ok",
    "resource_error","command_buffer_status","command_buffer_error","device","machine","os",
    "prefix_guard_ok","suffix_guard_ok","out_hex","out_words"]
DESCRIPTOR_KEYS = ["bytes_needed","case","device","family","schema","texture_ok","width"]
REC_KEYS = ["argv","cwd","exception","exit","started_utc","stderr","stdout","timed_out","timeout_seconds"]
INPUT_KEYS = ["authored_sha256","boundary","device_model","git_dirty","git_revision","machine","schema","sw_vers","xcrun_version"]
RUN_MANIFEST_KEYS = ["schema","run_id","cases","fresh_process_per_case","runner_sha256","harness_sha256",
    "matrix_kernel_sha256","direct128_kernel_sha256","contract_sha256"]

SMOKE_STEP = "run.py --execute pre-capture smoke invocation (capture.pre_capture_smoke) must pass before raw/ is created"
PRE_CAPTURE_GATE = ["python3 -B verify.py --selftest", "python3 -B verify.py --seqtest",
                    "python3 -B make_manifest.py --check", "python3 -B verify.py --preflight", SMOKE_STEP]
PRE_SECOND_RUN_GATE = ["python3 -B verify.py --selftest", "python3 -B verify.py --seqtest",
                       "python3 -B make_manifest.py --check", "python3 -B verify.py --between-runs", SMOKE_STEP]

blob_sha = {p: hashlib.sha256((HERE / p).read_bytes()).hexdigest() for p in AUTH if p != "CAPTURE_CONTRACT.json"}

contract = {
  "schema": 1,
  "experiment": "EXP-0095-m4-texture-image-matrix",
  "state": "PRE_GPU",
  "target": {"device": "Apple M4 (G16G)", "os": "macOS 26.6.2 (25G82)", "machine": "arm64",
             "note": "local M4 only; A18 Pro/G17P is hands-off per CLAUDE.md"},
  "boundary": "public Metal only; owned in-bounds resources; no binary/archive/BO inspection",
  "cases": cases,
  "blob_sha256": blob_sha,
  "capture": {
    "runs": ["m4-20260829-run01", "m4-20260829-run02"],
    "payload_keys": sorted(PAYLOAD_KEYS), "descriptor_keys": sorted(DESCRIPTOR_KEYS),
    "receipt_keys": sorted(REC_KEYS), "inputs_keys": sorted(INPUT_KEYS),
    "run_manifest_keys": RUN_MANIFEST_KEYS,
    "pre_capture_gate": PRE_CAPTURE_GATE, "pre_second_run_gate": PRE_SECOND_RUN_GATE,
    "pre_capture_smoke": {
        "case": "a05_1d_read_first",
        "invoked_by": "run.py --execute, once per contracted run, after the host build",
        "recorded": False, "receipt_path": "work/<run-id>/smoke/smoke.json", "required": True,
        "rules": [
            "receipt: exit 0, no timeout, no OS exception, argv equals the case argv template",
            "stdout parses as exactly one JSON object with the complete contracted payload key set",
            "payload identity matches the contract case; status ok; library_ok and resource_ok true; command buffer status 4",
            "prefix_guard_ok and suffix_guard_ok both true, and out_words derived correctly from out_hex"
        ],
        "on_failure": "STOP before raw/ is created; work/<run-id>/ is retained with STOP.json; pre-capture repair of the harness/runner is authorized because nothing was captured"
    },
    "between_runs_gate": "run01 must be a complete closed successful raw tree and work must be absent or empty before run02 is created",
    "cross_run_provenance_gate": "run02 current Git revision and authored hashes must equal run01's, from CAPTURE_CONTRACT.json",
    "failure_record": "STOP.json is append-only and ends that run; a case failure never triggers automatic retry",
    "pre_capture_failure_record": "a pre-capture failure (environment, host build, or smoke) writes work/<run-id>/STOP.json, never creates raw/, and authorizes a pre-capture repair",
    "statuses_exit_zero": ["ok"]
  },
  "timeouts_seconds": {"environment": 5, "host_build": 120, "smoke": 60, "case_default": 60, "case_max": 90, "gate": 900}
}
(HERE / "CAPTURE_CONTRACT.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
print("wrote CAPTURE_CONTRACT.json", (HERE / "CAPTURE_CONTRACT.json").stat().st_size, "bytes,", len(cases), "cases")
