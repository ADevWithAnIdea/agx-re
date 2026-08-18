#!/usr/bin/env python3
"""Strict clean-room verifier for EXP-0050."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
RUNS = ["m4_20260817_run01", "m4_20260817_run02"]
PREREG = "99cd47d7c75687c1ce816826c57507b73a9d827f0deed56243a1122d2959748f"
CASES = [
    "c0", "c1-only", "c2-only", "c0-c2-decl02", "c0-c2-decl20",
    "mrt3-decl012", "mrt3-decl210", "mrt3-swap12", "color-depth",
    "depth-color-decl", "depth-only", "color-fixed-depth", "mask-f",
    "mask-5", "mask-a", "mask-0", "mask-5-declfirst", "discard-half",
    "atomic-all", "atomic-before-discard", "atomic-after-discard",
]
SPLICE = "splice-rt1-to-rt2"
SHA_LINE = re.compile(r"^([0-9a-f]{64})  ([^/].*)$")
HEX_RE = re.compile(r"^[0-9a-f]+$")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_run_files() -> set[str]:
    names = {
        "00_preregistration.json", "01_environment.json",
        "02_environment_command.json", "03_environment_command.json",
        "04_environment_command.json", "05_environment_command.json",
        "06_environment_command.json", "07_build_probe.json",
        "source.metal", "failures.json", "SHA256SUMS",
        f"locate_{SPLICE}.json", f"mutation_{SPLICE}.json",
        f"own_{SPLICE}.fragment.main.hex", f"run_{SPLICE}.json",
        f"case_{SPLICE}.json",
    }
    for case in CASES:
        names.update({
            f"run_{case}.json", f"extract_{case}.json",
            f"own_{case}.fragment.main.hex", f"case_{case}.json",
        })
    return names


def verify_run(run: str) -> None:
    directory = RAW / run
    if not directory.is_dir() or directory.is_symlink():
        raise AssertionError(f"missing/unsafe run directory {run}")
    actual_paths = {str(path.relative_to(directory)) for path in directory.rglob("*")
                    if path.is_file()}
    expected = expected_run_files()
    if actual_paths != expected:
        raise AssertionError(
            f"raw file allowlist violation {run}: "
            f"missing={sorted(expected-actual_paths)} extra={sorted(actual_paths-expected)}")
    if any(path.is_symlink() for path in directory.rglob("*")):
        raise AssertionError(f"raw symlink forbidden {run}")

    prereg = json.loads((directory / "00_preregistration.json").read_text())
    if prereg.get("sha256") != PREREG or not prereg.get("verified_before_build_and_hardware"):
        raise AssertionError(f"bad pre-registration record {run}")
    if json.loads((directory / "failures.json").read_text()):
        raise AssertionError(f"formal failure present {run}")

    lines = (directory / "SHA256SUMS").read_text().splitlines()
    inventory: dict[str, str] = {}
    for line in lines:
        match = SHA_LINE.fullmatch(line)
        if not match:
            raise AssertionError(f"malformed SHA line {run}: {line!r}")
        want, relative = match.groups()
        path = Path(relative)
        if relative in inventory or path.is_absolute() or ".." in path.parts:
            raise AssertionError(f"unsafe/duplicate SHA path {run}/{relative}")
        inventory[relative] = want
    actual_without_inventory = actual_paths - {"SHA256SUMS"}
    if set(inventory) != actual_without_inventory:
        raise AssertionError(f"incomplete SHA inventory {run}")
    for relative, want in inventory.items():
        if digest(directory / relative) != want:
            raise AssertionError(f"SHA mismatch {run}/{relative}")

    source_hash = digest(directory / "source.metal")
    for case in [*CASES, SPLICE]:
        record = json.loads((directory / f"case_{case}.json").read_text())
        if record["case"] != case or record["source_sha256"] != source_hash:
            raise AssertionError(f"bad normalized identity {run}/{case}")
        if record.get("archive_retained") is not False:
            raise AssertionError(f"archive policy mismatch {run}/{case}")
        main_hex = (directory / f"own_{case}.fragment.main.hex").read_text().strip()
        if not HEX_RE.fullmatch(main_hex) or len(main_hex) % 2:
            raise AssertionError(f"bad own-main hex {run}/{case}")
        if record["main_hex"] != main_hex:
            raise AssertionError(f"own-main copy mismatch {run}/{case}")
        main = bytes.fromhex(main_hex)
        if record["main_length"] != len(main) or record["main_sha256"] != hashlib.sha256(main).hexdigest():
            raise AssertionError(f"own-main metadata mismatch {run}/{case}")
        render = record["render"]
        if render["status"] != "OK" or render["pipeline_source"] != "archive":
            raise AssertionError(f"render status mismatch {run}/{case}")

    mutation = json.loads((directory / f"mutation_{SPLICE}.json").read_text())
    if (mutation.get("status") != "APPLIED" or mutation.get("change_count") != 1 or
            mutation.get("before") != "0x02" or mutation.get("after") != "0x04"):
        raise AssertionError(f"splice guard mismatch {run}")


def main() -> int:
    if digest(HERE / "PRE_REGISTRATION.md") != PREREG:
        raise AssertionError("frozen pre-registration changed")
    raw_dirs = {path.name for path in RAW.iterdir() if path.is_dir()}
    if raw_dirs != set(RUNS):
        raise AssertionError(f"unexpected raw run directories: {sorted(raw_dirs)}")
    for run in RUNS:
        verify_run(run)

    with tempfile.TemporaryDirectory(prefix="exp0050-verify-") as temporary:
        temp = Path(temporary)
        cp = subprocess.run(
            [sys.executable, HERE / "analysis" / "analyze.py",
             "--json", temp / "summary.json", "--report", temp / "report.txt"],
            capture_output=True, text=True, timeout=30)
        if cp.returncode:
            raise AssertionError(f"analysis failed: {cp.stderr}")
        for name in ("summary.json", "report.txt"):
            if (temp / name).read_bytes() != (HERE / "analysis" / name).read_bytes():
                raise AssertionError(f"stale analysis/{name}")

    manifest = json.loads((HERE / "manifest.json").read_text())
    if manifest["pre_registration"]["sha256"] != PREREG:
        raise AssertionError("manifest pre-registration mismatch")
    if manifest["target"]["qualification"] != "local M4 only; no A18 Pro validation":
        raise AssertionError("manifest target qualification mismatch")
    archive_records = manifest["temporary_own_archives"]["records"]
    if len(archive_records) != len(RUNS) * (len(CASES) + 1):
        raise AssertionError("manifest temporary archive record count")
    if any(record.get("committed") is not False for record in archive_records):
        raise AssertionError("manifest archive policy")

    listed = {item["path"]: item for item in manifest["artifacts"]}
    actual = {str(path.relative_to(HERE)): path for path in HERE.rglob("*")
              if path.is_file() and path.name != "manifest.json" and
              "work" not in path.parts and "__pycache__" not in path.parts}
    if set(listed) != set(actual):
        raise AssertionError(
            f"manifest coverage mismatch missing={sorted(set(actual)-set(listed))} "
            f"extra={sorted(set(listed)-set(actual))}")
    forbidden_suffixes = {".bin", ".dylib", ".metallib", ".air", ".o", ".a", ".so"}
    forbidden = [relative for relative, path in actual.items()
                 if path.suffix.lower() in forbidden_suffixes]
    if forbidden:
        raise AssertionError(f"forbidden committable binary payload: {forbidden}")
    for relative, path in actual.items():
        item = listed[relative]
        if item["bytes"] != path.stat().st_size or item["sha256"] != digest(path):
            raise AssertionError(f"manifest mismatch {relative}")

    print(f"PASS runs=2 executions=44 artifacts={len(listed)} prereg={PREREG[:12]} analysis=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
