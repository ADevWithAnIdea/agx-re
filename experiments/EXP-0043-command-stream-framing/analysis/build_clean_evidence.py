#!/usr/bin/env python3
"""Build the explicit allowlist of artifacts used by RESULTS.md."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re

INPUT_PATH = re.compile(r"(?:INPUT|INPUT_A|INPUT_B) path=([^\s]+)")


def digest(path: pathlib.Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=pathlib.Path)
    args = parser.parse_args()
    root = args.root.resolve()
    selected: set[pathlib.Path] = set()
    clean_dir = root / "raw" / "clean-analysis"
    for report in clean_dir.rglob("*.txt"):
        selected.add(report.resolve())
        for match in INPUT_PATH.finditer(report.read_text(errors="replace")):
            value = pathlib.Path(match.group(1))
            if not value.is_absolute():
                value = (root.parent.parent / value).resolve()
            selected.add(value)
    for run in ("m4-20260817-a", "m4-20260817-boundaries-a"):
        run_dir = root / "raw" / "runs" / run
        selected.add(run_dir / "target.txt")
        for case in (run_dir / "cases").iterdir():
            for name in ("command.txt", "exit-status.txt", "stdout.txt", "stderr.txt", "iotrace.log"):
                selected.add(case / name)
    selected.update(
        {
            root / "README.md",
            root / "RESULTS.md",
            root / "run.sh",
            root / "run-boundaries.sh",
            root / "raw" / "evidence-audit.txt",
            root / "harness" / "framing.m",
            root / "analysis" / "capturelib.py",
            root / "analysis" / "hard_timeout.py",
            root / "analysis" / "safe_framing.py",
            root / "analysis" / "safe_fields.py",
            root / "analysis" / "safe_compare.py",
            root / "analysis" / "audit_evidence.py",
            root / "analysis" / "make_manifest.py",
            root / "analysis" / "build_clean_evidence.py",
            root / "analysis" / "verify_clean_evidence.py",
            root / "raw" / "runs" / "m4-20260817-boundaries-a" / "inputs" / "iotrace.c",
        }
    )
    files = []
    for path in sorted(selected):
        if not path.is_file():
            raise SystemExit(f"missing selected evidence: {path}")
        relative = path.relative_to(root)
        if any("quarantine" in part.lower() for part in relative.parts):
            raise SystemExit(f"quarantined path selected: {relative}")
        files.append(
            {
                "path": str(relative),
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
        )
    output = root / "clean-evidence.json"
    output.write_text(
        json.dumps(
            {
                "policy": "explicit pre-classified command/state/descriptor BO inputs only",
                "apple_binary_introspection": "NONE",
                "files": files,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(f"wrote {output} with {len(files)} explicitly allowed evidence files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
