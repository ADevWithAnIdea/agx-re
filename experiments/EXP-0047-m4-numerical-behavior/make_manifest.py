#!/usr/bin/env python3
"""Emit the EXP-0047 artifact manifest; manifest.json intentionally excludes itself."""

import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    raw = json.loads((HERE / "raw/m4-two-run-v3.json").read_text())
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
        "experiment": "EXP-0047-m4-numerical-behavior",
        "generated_at_utc": raw["captured_at_utc"],
        "base_revision": raw["repo_revision"],
        "target": raw["target"],
        "canonical_capture": "raw/m4-two-run-v3.json",
        "preserved_design_iterations": [
            "raw/m4-two-run.json",
            "raw/m4-two-run-v2.json",
        ],
        "apple_binary_introspection": "NONE",
        "artifacts": artifacts,
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
