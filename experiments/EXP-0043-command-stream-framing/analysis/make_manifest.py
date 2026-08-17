#!/usr/bin/env python3
"""Create an auditable SHA-256 manifest for EXP-0043 artifacts."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import subprocess


def digest(path: pathlib.Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def command(*argv: str) -> str:
    try:
        return subprocess.check_output(argv, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=pathlib.Path)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    paths = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        relative = path.relative_to(root)
        lowered = tuple(part.lower() for part in relative.parts)
        if "build" in relative.parts or "__pycache__" in relative.parts:
            continue
        # Quarantined generic directory-wide scans are retained for process
        # audit but are never part of the evidence manifest.
        if any("quarantine" in part for part in lowered):
            continue
        paths.append(
            {
                "path": str(relative),
                "bytes": path.stat().st_size,
                "sha256": digest(path),
            }
        )
    manifest = {
        "experiment": "EXP-0043-command-stream-framing",
        "run_id": args.run_id,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "repository_revision": command("git", "-C", str(root), "rev-parse", "HEAD"),
        "target_scope": "Apple M4 local only; A18 Pro transfer not tested",
        "clean_room_categories": ["DATA-TRACE", "OWN-SHADER", "HW-PROBE"],
        "apple_binary_introspection": "NONE",
        "excluded_from_evidence": [
            "all path components containing 'quarantine'",
            "build outputs",
            "Python bytecode caches",
        ],
        "files": paths,
    }
    output = root / "manifest.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote {output} with {len(paths)} hashed files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
