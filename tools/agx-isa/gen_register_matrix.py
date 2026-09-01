#!/usr/bin/env python3
"""Generate the human-auditable 96-column register-access matrix."""

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/isa/register-effects.json"
OUTPUT = ROOT / "docs/isa/register-access-matrix.csv"
CODE = {
    "direct": "D",
    "transfer": "T",
    "unaddressable": "I",
    "unknown": "?",
}


def expand(role, count):
    cells = [role.get("default_status", "unknown")] * count
    for span in role.get("cells", []):
        for reg in range(span["first"], span["last"] + 1):
            cells[reg] = span["status"]
    for override in role.get("overrides", []):
        for reg in override["registers"]:
            cells[reg] = override["status"]
    return cells


def main():
    data = json.loads(SOURCE.read_text())
    count = data["physical_gprs"]
    header = ["role_id", "instruction", "form", "role", "width", "evidence"]
    header += [f"r{reg}" for reg in range(count)]
    header += ["outside_behavior"]
    with OUTPUT.open("w", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(header)
        for role in data["roles"]:
            cells = expand(role, count)
            assert len(cells) == count
            assert all(status in CODE for status in cells)
            row = [
                role["id"], role["instruction"], role["form"], role["role"],
                role["width"], ";".join(role["evidence"]),
            ]
            row += [CODE[status] for status in cells]
            row += [role["outside_behavior"]]
            writer.writerow(row)


if __name__ == "__main__":
    main()
