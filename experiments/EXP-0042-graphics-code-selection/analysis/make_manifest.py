#!/usr/bin/env python3
"""Hash EXP-0042 sources and all retained raw evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "raw"
RAW_LIST = ROOT / "raw_manifest.sha256"
MANIFEST = ROOT / "manifest.json"


def file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def tree_record(directory: Path, records: dict[str, dict[str, object]]) -> dict[str, object]:
    digest = hashlib.sha256()
    count = 0
    size = 0
    for relative in sorted(key for key in records if key.startswith(str(directory.relative_to(ROOT)) + "/")):
        item = records[relative]
        digest.update(relative.encode() + b"\0")
        digest.update(str(item["size"]).encode() + b"\0")
        digest.update(str(item["sha256"]).encode() + b"\n")
        count += 1
        size += int(item["size"])
    return {"files": count, "bytes": size, "aggregate_sha256": digest.hexdigest()}


def main() -> None:
    records: dict[str, dict[str, object]] = {}
    for path in sorted(p for p in RAW.rglob("*") if p.is_file()):
        relative = str(path.relative_to(ROOT))
        records[relative] = {"size": path.stat().st_size, "sha256": file_sha(path)}

    with RAW_LIST.open("w") as output:
        for relative, item in records.items():
            output.write(f"{item['sha256']}  {item['size']:12d}  {relative}\n")

    source_paths = [
        ROOT / ".gitignore",
        ROOT / "README.md",
        ROOT / "RESULTS.md",
        *sorted((ROOT / "analysis").glob("*.py")),
        *sorted((ROOT / "harness").glob("*")),
        *sorted((ROOT / "kernels").glob("*")),
    ]
    source_hashes = {
        str(path.relative_to(ROOT)): {"size": path.stat().st_size, "sha256": file_sha(path)}
        for path in source_paths if path.is_file()
    }
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              text=True, capture_output=True, check=True).stdout.strip()
    collections = {}
    for directory in sorted(path for path in RAW.iterdir() if path.is_dir()):
        collections[directory.name] = tree_record(directory, records)

    manifest = {
        "experiment": "EXP-0042-graphics-code-selection",
        "capture_date": "2026-08-17",
        "repository_revision_before_experiment": revision,
        "target": {
            "device": "Apple M4 / G16G (Metal public device name: Apple M4)",
            "os": "macOS 26.6.2 (25G82)",
            "architecture": "arm64",
        },
        "clean_room_categories": ["HW-PROBE", "DATA-TRACE", "OWN-SHADER"],
        "apple_binary_introspection": "NONE",
        "authoritative_capture_sets": [
            "run_ab_p0", "run_ba_p0", "run_ab_p17", "run_stage_equal"
        ],
        "preserved_non_authoritative_pilots": [
            "run_stage_matrix", "run_stage_matrix_repeat"
        ],
        "raw_retention": {
            "location": "raw/ (full maps retained in workspace; raw/run_*/maps is gitignored due size)",
            "per_file_hash_index": "raw_manifest.sha256",
            "collections": collections,
        },
        "source_hashes": source_hashes,
        "reused_clean_room_tools": {
            "tools/iotrace/iotrace.c": file_sha(ROOT.parents[1] / "tools/iotrace/iotrace.c"),
            "tools/shdump/shdump.m": file_sha(ROOT.parents[1] / "tools/shdump/shdump.m"),
            "tools/shdump/agxparse.py": file_sha(ROOT.parents[1] / "tools/shdump/agxparse.py"),
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
