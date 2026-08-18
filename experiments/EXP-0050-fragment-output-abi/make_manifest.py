#!/usr/bin/env python3
"""Generate the complete committable EXP-0050 artifact inventory."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import platform
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PREREG = "99cd47d7c75687c1ce816826c57507b73a9d827f0deed56243a1122d2959748f"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(argv: list[str]) -> str:
    return subprocess.run(argv, check=True, capture_output=True, text=True,
                          timeout=15).stdout.strip()


def main() -> None:
    artifacts = []
    for path in sorted(HERE.rglob("*")):
        if (not path.is_file() or path.name == "manifest.json" or
                "work" in path.parts or "__pycache__" in path.parts):
            continue
        artifacts.append({
            "path": str(path.relative_to(HERE)),
            "bytes": path.stat().st_size,
            "sha256": digest(path),
        })
    case_records = []
    for path in sorted((HERE / "raw").glob("*/case_*.json")):
        record = json.loads(path.read_text())
        case_records.append({
            "run": path.parent.name,
            "case": record["case"],
            "archive_bytes": record["archive_bytes"],
            "archive_sha256": record["archive_sha256"],
            "archive_local_work_path": record["archive_local_work_path"],
            "committed": False,
        })
    manifest = {
        "experiment": "EXP-0050-fragment-output-abi",
        "generated": datetime.now().astimezone().isoformat(),
        "target": {
            "model": command(["sysctl", "-n", "hw.model"]),
            "soc": "Apple M4",
            "gpu": "Apple M4 / G16G",
            "qualification": "local M4 only; no A18 Pro validation",
        },
        "host": {
            "platform": platform.platform(),
            "sw_vers": command(["sw_vers"]),
            "clang": command(["clang", "--version"]).splitlines()[0],
        },
        "repository": {
            "head_at_manifest": command(["git", "-C", str(REPO), "rev-parse", "HEAD"]),
            "process": "CODEX.md",
            "gap": "AGX_RE_INFORMATION_GAPS.md P0.8",
        },
        "pre_registration": {"path": "PRE_REGISTRATION.md", "sha256": PREREG},
        "provenance": {
            "categories": ["HW-PROBE", "OWN-SHADER-DIFF", "bounded-HW-splice"],
            "apple_binary_introspection": "NONE",
            "apple_auxiliary_or_helper_program_inspection": "NONE",
            "unknown_bo_inspection": "NONE",
            "command_state_bo_inspection": "NONE",
            "compiled_constant_program_inspection": "NONE",
            "permitted_compiled_bytes": "selected fragment _agc.main from kernels/output_matrix.metal only",
        },
        "runs": {
            "raw": ["raw/m4_20260817_run01", "raw/m4_20260817_run02"],
            "intact_cases_per_run": 21,
            "checked_splices_per_run": 1,
            "formal_failures": 0,
            "formal_timeouts": 0,
            "forced_archive_executions": 44,
        },
        "temporary_own_archives": {
            "policy": "not committed; exact selected _agc.main retained; size/hash/local ignored work path recorded",
            "records": case_records,
        },
        "artifacts": artifacts,
    }
    (HERE / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
