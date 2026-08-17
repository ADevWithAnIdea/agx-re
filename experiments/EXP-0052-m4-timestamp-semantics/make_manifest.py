#!/usr/bin/env python3
"""Emit the EXP-0052 inventory; manifest.json intentionally excludes itself."""

import datetime
import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(argv):
    return subprocess.run(
        argv, check=True, capture_output=True, text=True, timeout=15
    ).stdout.strip()


def main():
    artifacts = []
    for path in sorted(HERE.rglob("*")):
        relative = path.relative_to(HERE)
        if (not path.is_file() or relative.as_posix() == "manifest.json" or
                "__pycache__" in relative.parts):
            continue
        artifacts.append({
            "path": relative.as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        })
    result = {
        "schema": 1,
        "experiment": "EXP-0052-m4-timestamp-semantics",
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "head_at_manifest": command(["git", "-C", str(REPO), "rev-parse", "HEAD"]),
        "pre_registration_sha256":
            "92ffe845be42a8dee30f4116cb239156eb3111295bf4dcd9d8b71048887625fa",
        "canonical_runs": ["m4_20260817_run03", "m4_20260817_run04"],
        "preserved_failed_runs": ["m4_20260817_run01", "m4_20260817_run02"],
        "apple_binary_introspection": "NONE",
        "artifacts": artifacts,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
