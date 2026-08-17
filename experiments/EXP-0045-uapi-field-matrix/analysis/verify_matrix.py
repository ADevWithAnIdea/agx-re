#!/usr/bin/env python3
"""Verify exhaustive leaf coverage for the pinned Asahi queue/render/compute UAPI."""

import csv
import hashlib
import json
import re
import sys
from pathlib import Path


SCALAR = r"__u(?:8|16|32|64)"
STRUCT = r"struct\s+drm_asahi_\w+"


def parse_structs(header: str):
    source = re.sub(r"/\*.*?\*/", "", header, flags=re.S)
    structs = {}
    for name, body in re.findall(
        r"struct\s+(drm_asahi_\w+)\s*\{(.*?)\};", source, flags=re.S
    ):
        fields = []
        for field_type, field_name in re.findall(
            rf"\b((?:{SCALAR})|(?:{STRUCT}))\s+(\w+)\s*(?:\[[^]]+\])?\s*;", body
        ):
            fields.append((field_type.removeprefix("struct "), field_name))
        structs[name] = fields
    return structs


def expand(structs, struct_name, prefix):
    for field_type, field_name in structs[struct_name]:
        path = f"{prefix}.{field_name}"
        if field_type in structs:
            yield from expand(structs, field_type, path)
        else:
            yield path


def fail(message):
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def main():
    if len(sys.argv) != 5:
        fail("usage: verify_matrix.py HEADER EXPECTED_FIELDS FIELD_MATRIX MANIFEST")

    header_path, expected_path, matrix_path, manifest_path = map(Path, sys.argv[1:])
    structs = parse_structs(header_path.read_text())
    required_structs = {
        "drm_asahi_queue_create",
        "drm_asahi_cmd_render",
        "drm_asahi_cmd_compute",
    }
    missing_structs = required_structs - structs.keys()
    if missing_structs:
        fail(f"missing structs: {sorted(missing_structs)}")

    actual = ["queue.usc_exec_base"]
    actual += list(expand(structs, "drm_asahi_cmd_render", "render"))
    actual += list(expand(structs, "drm_asahi_cmd_compute", "compute"))
    expected = [line for line in expected_path.read_text().splitlines() if line]
    if actual != expected:
        fail("pinned header expansion differs from raw/expected-fields.txt")

    with matrix_path.open(newline="") as matrix_file:
        rows = list(csv.DictReader(matrix_file, delimiter="\t"))
    paths = [row["path"] for row in rows]
    duplicates = sorted({path for path in paths if paths.count(path) > 1})
    if duplicates:
        fail(f"duplicate matrix paths: {duplicates}")
    if set(paths) != set(expected):
        fail(
            f"matrix mismatch; missing={sorted(set(expected) - set(paths))}, "
            f"extra={sorted(set(paths) - set(expected))}"
        )
    valid_status = {"OPEN", "A18-PARTIAL", "PUBLIC-ONLY"}
    bad_status = sorted({row["status"] for row in rows} - valid_status)
    if bad_status:
        fail(f"invalid statuses: {bad_status}")
    for row in rows:
        if not row["contract"] or not row["closure_obligation"]:
            fail(f"empty contract or closure obligation for {row['path']}")

    manifest = json.loads(manifest_path.read_text())
    experiment_dir = manifest_path.parent
    for relative_path, expected_hash in manifest["artifacts"].items():
        artifact = experiment_dir / relative_path
        if not artifact.is_file():
            fail(f"manifest artifact does not exist: {relative_path}")
        actual_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            fail(f"manifest hash mismatch: {relative_path}")

    print(f"PASS: {len(paths)}/{len(expected)} required UAPI leaves have exactly one matrix row")


if __name__ == "__main__":
    main()
