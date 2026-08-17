#!/usr/bin/env python3
"""Prove quarantined/generic analysis does not feed the result evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re

BANNED_RESULT_REFERENCES = (
    "analysis/analyze.py",
    "analysis/framing_summary.py",
    "-scan.txt",
    "-diff.txt",
    "-relocations.txt",
    "analysis-quarantined",
)

# Independently correlated before clean analysis. Any other captured BO is raw
# retention only and must never enter the evidence allowlist.
ALLOWED_BO_VAS = {
    0x18000,        # VDM command/state stream
    0x88000,        # VDM continuation segment
    0x10000088000,  # repeated-compute argument/uniform data
    0x100000B8000,  # primary CDM stream
    0x100000E8000,  # compute resource table
    0x10000100000,  # graphics resource table
    0x10000158000,  # CDM continuation segment
    0x10000360000,  # mixed-order CDM stream
}
BO_VA = re.compile(r"_va([0-9a-fA-F]+)_")


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
    evidence = json.loads((root / "clean-evidence.json").read_text())
    manifest = json.loads((root / "manifest.json").read_text())
    manifest_files = {item["path"]: item for item in manifest["files"]}
    errors = []
    for item in evidence["files"]:
        relative = pathlib.Path(item["path"])
        if any("quarantine" in part.lower() for part in relative.parts):
            errors.append(f"quarantined evidence path: {relative}")
            continue
        if "dumps" in relative.parts and relative.suffix == ".hex":
            match = BO_VA.search(relative.name)
            if not match or int(match.group(1), 16) not in ALLOWED_BO_VAS:
                errors.append(f"unclassified BO evidence path: {relative}")
                continue
        path = root / relative
        if not path.is_file():
            errors.append(f"missing evidence path: {relative}")
            continue
        actual = digest(path)
        if actual != item["sha256"] or path.stat().st_size != item["bytes"]:
            errors.append(f"evidence hash/size mismatch: {relative}")
        recorded = manifest_files.get(str(relative))
        if not recorded or recorded["sha256"] != actual:
            errors.append(f"evidence absent/mismatched in manifest: {relative}")
    for item in manifest["files"]:
        if any("quarantine" in part.lower() for part in pathlib.Path(item["path"]).parts):
            errors.append(f"quarantined manifest path: {item['path']}")
    results = (root / "RESULTS.md").read_text()
    for token in BANNED_RESULT_REFERENCES:
        if token in results:
            errors.append(f"RESULTS references banned generic artifact: {token}")
    for error in errors:
        print(f"ERROR {error}")
    print(
        f"SUMMARY clean_evidence_files={len(evidence['files'])} "
        f"manifest_files={len(manifest['files'])} errors={len(errors)}"
    )
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
