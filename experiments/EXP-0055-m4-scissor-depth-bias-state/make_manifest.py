#!/usr/bin/env python3
"""Generate EXP-0055 manifest only after exact state-payload preflight."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import stat
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import run as runner  # noqa: E402

RUNS = ["m4_20260817_run01", "m4_20260817_run02"]
STATIC_ARTIFACTS = {
    "PRE_REGISTRATION.md", "README.md", "RESULTS.md",
    "harness/allowtrace.c", "harness/probe.m", "run.py",
    "analysis/analyze.py", "analysis/run_analysis.py",
    "analysis/failures.md", "analysis/invocation.json",
    "analysis/report.txt", "analysis/summary.json",
    "make_manifest.py", "verify.py",
}
RUN_TOP = {"00_inputs.json", "01_environment.json", "02_build_allowtrace.json",
           "03_build_probe.json", "04_boundary_preflight.json",
           "failures.jsonl", "SHA256SUMS", "trials"}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_tree() -> tuple[set[str], set[str]]:
    files = set(STATIC_ARTIFACTS)
    directories = {"harness", "analysis", "raw"}
    for run_id in RUNS:
        base = f"raw/{run_id}"
        directories |= {base, f"{base}/trials"}
        files |= {f"{base}/{name}" for name in RUN_TOP if name != "trials"}
        for _, _, _, name in runner.TRIALS:
            trial = f"{base}/trials/{name}"
            directories |= {trial, f"{trial}/state"}
            files |= {f"{trial}/run.json", f"{trial}/trace.log"}
            files |= {f"{trial}/state/{item}" for item in runner.STATE_NAMES}
    return files, directories


def preflight_global_tree() -> set[str]:
    """Resolve the exact artifact/type matrix without opening file contents."""
    expected_files, expected_dirs = expected_tree()
    actual_files: set[str] = set()
    actual_dirs: set[str] = set()
    stack = [HERE]
    while stack:
        base = stack.pop()
        with os.scandir(base) as entries:
            for entry in entries:
                path = Path(entry.path)
                rel = path.relative_to(HERE).as_posix()
                mode = entry.stat(follow_symlinks=False).st_mode
                if entry.is_symlink():
                    raise AssertionError(f"symlink forbidden: {rel}")
                if stat.S_ISDIR(mode):
                    actual_dirs.add(rel)
                    stack.append(path)
                elif stat.S_ISREG(mode):
                    actual_files.add(rel)
                else:
                    raise AssertionError(f"special entry forbidden: {rel}")
    permitted_files = set(expected_files)
    if (HERE / "manifest.json").is_file():
        permitted_files.add("manifest.json")
    if actual_dirs != expected_dirs:
        raise AssertionError(
            f"exact directory set missing={sorted(expected_dirs-actual_dirs)} "
            f"extra={sorted(actual_dirs-expected_dirs)}")
    if actual_files != permitted_files:
        raise AssertionError(
            f"exact artifact set missing={sorted(permitted_files-actual_files)} "
            f"extra={sorted(actual_files-permitted_files)}")
    expected_bins = {
        rel for rel in expected_files
        if PurePosixPath(rel).suffix == ".bin"
    }
    if len(expected_bins) != 152:
        raise AssertionError("exact allowed binary path count")
    return expected_files


def stable_manifest_base() -> str:
    """Reuse the existing truthful anchor so regeneration is HEAD-durable."""
    manifest_path = HERE / "manifest.json"
    if manifest_path.is_file():
        prior = json.loads(manifest_path.read_text())
        base = prior.get("repository", {}).get("base_revision_at_manifest")
    else:
        base = subprocess.run(
            ["git", "-C", REPO, "rev-parse", "HEAD"], check=True,
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
    if not isinstance(base, str) or re.fullmatch(r"[0-9a-f]{40}", base) is None:
        raise AssertionError("manifest base syntax")
    ancestor = subprocess.run(
        ["git", "-C", REPO, "merge-base", "--is-ancestor", base, "HEAD"],
        timeout=15,
    )
    if ancestor.returncode != 0:
        raise AssertionError("manifest base must be an ancestor of HEAD")
    return base


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=HERE / "manifest.json")
    args = parser.parse_args()
    # Global names/types are proven before any artifact (including any .bin) is
    # opened or hashed. Unknown files therefore fail closed.
    expected_files = preflight_global_tree()
    roots = list((HERE / "raw").iterdir())
    if ({path.name for path in roots} != set(RUNS) or
            any(not path.is_dir() or path.is_symlink() for path in roots)):
        raise AssertionError("exact raw run set")

    # Mandatory: validate every exact payload path/metadata before any payload hash.
    for run in RUNS:
        runner.preflight_all_payloads(HERE / "raw" / run)

    artifacts = []
    for rel in sorted(expected_files):
        path = HERE / Path(*PurePosixPath(rel).parts)
        artifacts.append({"path": str(path.relative_to(HERE)),
                          "bytes": path.stat().st_size,
                          "sha256": digest(path)})

    head = stable_manifest_base()
    manifest = {
        "schema": 1,
        "experiment": "EXP-0055-m4-scissor-depth-bias-state",
        "target": {
            "model": "Mac16,10", "soc": "Apple M4",
            "gpu": "Apple M4 / G16G-class",
            "qualification": "local M4 DATA-TRACE only; A18 Pro untested",
        },
        "repository": {
            "base_revision_at_manifest": head,
            "base_must_be_ancestor_of_head": True,
            "authoritative_process": "CODEX.md",
            "gap": "AGX_RE_INFORMATION_GAPS.md P0.3",
        },
        "pre_registration": {
            "path": "PRE_REGISTRATION.md", "commit": runner.PRE_COMMIT,
            "sha256": runner.PRE_HASH, "committed_alone_before_build": True,
        },
        "prior_evidence": {
            "experiment": "EXP-0048-bg-eot-pbe",
            "artifact_commit": runner.PRIOR_COMMIT,
            "manifest_generation_revision": runner.PRIOR_PARENT,
            "manifest": {
                "path": "experiments/EXP-0048-bg-eot-pbe/manifest.json",
                "sha256": runner.PRIOR_MANIFEST_HASH,
            },
            "allowlist": [
                {"gpu_va": "0x58000", "role": "fixed-function-render-state",
                 "allocation_size": "0x8000", "cap": "0x10000"},
                {"gpu_va": "0x68000", "role": "tiling-state",
                 "allocation_size": "0x88e0", "cap": "0x10000"},
            ],
        },
        "provenance": {
            "categories": ["HW-PROBE", "DATA-TRACE", "OWN-SHADER"],
            "apple_binary_introspection": "NONE",
            "apple_auxiliary_or_helper_program_bytes_inspected": "NONE",
            "compiled_shader_bytes_inspected": "NONE",
            "command_bo_contents_inspected": "NONE",
            "unknown_bo_contents_inspected": "NONE",
            "pointer_following": "NONE",
            "generic_bo_or_memory_scan": "NONE",
            "command_memory_mutation_splice_replay": "NONE",
            "state_bo_allowlist": [
                {"gpu_va": "0x58000", "role": "fixed-function-render-state",
                 "expected_read": "0x8000", "cap": "0x10000"},
                {"gpu_va": "0x68000", "role": "tiling-state",
                 "expected_read": "0x88e0", "cap": "0x10000"},
            ],
        },
        "runs": {
            "canonical": [f"raw/{run}" for run in RUNS],
            "top_level_runs": 2, "fresh_gpu_processes": 76,
            "successful_gpu_processes": 76, "gpu_errors": 0,
            "timeouts": 0, "guard_errors": 0,
            "allowed_payload_pairs": 152,
            "metadata_preflight_before_payload_access": True,
        },
        "build_products": {
            "retention": "temporary rebuildable authored products; not committed",
            "identity": "exact size/SHA-256 recorded before execution in each build record",
            "semantic_inspection": "NONE",
        },
        "interpretation": {
            "evidence_level": "DATA-TRACE-VALIDATED for qualified bounded correlations",
            "p0_3": "OPEN",
            "hardware_consumption": "NOT ESTABLISHED",
            "linux_uapi_mapping": "UNKNOWN",
            "a18_pro": "UNTESTED",
        },
        "artifacts": artifacts,
    }
    args.output.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"WROTE {args.output} artifacts={len(artifacts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
