#!/usr/bin/env python3
"""BLOCKED, NON-RUNNABLE draft for a possible EXP-0050 clean-v2 repetition.

DO NOT EXECUTE. The draft locator cannot prove an exact symbol extent or clean
container-format provenance. `main()` exits before parsing arguments, creating
state, compiling source, or opening an archive.

Do not use this runner until PRE_REGISTRATION_CLEAN_V2.md, CLEAN_V2_LOCK.json,
and every locked authored input have been committed together. The required
``--anchor-commit`` is verified before a run directory or Metal object exists.

The only archive accessor is harness/exact_fragment_region.py. This runner never
opens, reads, mmaps, scans, or hashes an archive itself. It treats an archive as
an opaque public-API transport and retains only the exact allowlisted fragment
main returned by the exact-region tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REL = Path("experiments/EXP-0050-fragment-output-abi")
RAW = HERE / "raw_v2"
WORK = HERE / "work_v2"
HARNESS = HERE / "harness" / "render_probe.m"
SOURCE = HERE / "kernels" / "output_matrix.metal"
EXACT = HERE / "harness" / "exact_fragment_region.py"
LOCK = HERE / "CLEAN_V2_LOCK.json"
PREREG = HERE / "PRE_REGISTRATION_CLEAN_V2.md"

CASES = [
    "c0", "c1-only", "c2-only", "c0-c2-decl02", "c0-c2-decl20",
    "mrt3-decl012", "mrt3-decl210", "mrt3-swap12", "color-depth",
    "depth-color-decl", "depth-only", "color-fixed-depth", "mask-f",
    "mask-5", "mask-a", "mask-0", "mask-5-declfirst", "discard-half",
    "atomic-all", "atomic-before-discard", "atomic-after-discard",
]
SPLICE = "splice-rt1-to-rt2"
HEX_RE = re.compile(r"^[0-9a-f]+$")


def digest(path: Path) -> str:
    """Hash authored text or retained lawful raw only; never call on an archive."""
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def invoke(command: list[object], log: Path, timeout: int,
           env: dict[str, str] | None = None) -> tuple[int, dict[str, object]]:
    argv = [str(item) for item in command]
    started = time.time()
    record: dict[str, object] = {
        "command": argv,
        "started_unix": started,
        "timeout_seconds": timeout,
    }
    try:
        completed = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout, env=env
        )
        record.update(
            exit=completed.returncode,
            elapsed_seconds=round(time.time() - started, 6),
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
        result = completed.returncode
    except subprocess.TimeoutExpired as error:
        def as_text(value: object) -> str:
            if isinstance(value, bytes):
                return value.decode(errors="replace")
            return str(value or "")
        record.update(
            timed_out=True,
            elapsed_seconds=round(time.time() - started, 6),
            stdout=as_text(error.stdout),
            stderr=as_text(error.stderr),
        )
        result = 124
    log.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return result, record


def git_output(arguments: list[str], binary: bool = False) -> bytes | str:
    completed = subprocess.run(
        ["git", "-C", str(REPO), *arguments], check=True,
        capture_output=True, text=not binary, timeout=15,
    )
    return completed.stdout


def verify_anchor(requested: str) -> dict[str, object]:
    lock = json.loads(LOCK.read_text())
    if lock.get("schema") != 1 or lock.get("experiment") != "EXP-0050-clean-v2":
        raise SystemExit("invalid CLEAN_V2_LOCK.json")
    commit = str(git_output(["rev-parse", "--verify", f"{requested}^{{commit}}"])).strip()
    head = str(git_output(["rev-parse", "HEAD"])).strip()
    ancestor = subprocess.run(
        ["git", "-C", str(REPO), "merge-base", "--is-ancestor", commit, head],
        timeout=15,
    )
    if ancestor.returncode != 0:
        raise SystemExit("anchor commit is not an ancestor of current HEAD")

    required = {
        str(REL / "PRE_REGISTRATION_CLEAN_V2.md"): digest(PREREG),
        str(REL / "CLEAN_V2_LOCK.json"): digest(LOCK),
        **lock["authored_inputs"],
    }
    for relative, expected_hash in required.items():
        path = REPO / relative
        if not path.is_file() or path.is_symlink():
            raise SystemExit(f"missing/unsafe anchored input: {relative}")
        current_hash = digest(path)
        if current_hash != expected_hash:
            raise SystemExit(
                f"current input hash mismatch {relative}: {current_hash} != {expected_hash}"
            )
        try:
            anchored = git_output(["show", f"{commit}:{relative}"], binary=True)
        except subprocess.CalledProcessError as error:
            raise SystemExit(f"input absent from anchor commit: {relative}") from error
        anchored_hash = hashlib.sha256(anchored).hexdigest()
        if anchored_hash != expected_hash:
            raise SystemExit(
                f"anchor input hash mismatch {relative}: {anchored_hash} != {expected_hash}"
            )
    return {
        "requested": requested,
        "commit": commit,
        "head_at_run": head,
        "pre_registration_sha256": digest(PREREG),
        "lock_sha256": digest(LOCK),
        "verified_inputs": required,
    }


def parse_render(stdout: str) -> dict[str, object]:
    def exactly_one(pattern: str, required: bool = True) -> str | None:
        matches = re.findall(pattern, stdout, re.M)
        if required and len(matches) != 1:
            raise ValueError(f"expected one output match {pattern!r}, got {len(matches)}")
        if not required and len(matches) > 1:
            raise ValueError(f"duplicate optional output match {pattern!r}")
        return matches[0] if matches else None

    colors: list[str | None] = []
    for index in range(3):
        value = exactly_one(rf"^COLOR{index}_HEX (\S+)$")
        colors.append(None if value == "absent" else value)
    depth = exactly_one(r"^DEPTH_HEX (\S+)$")
    parsed = {
        "device": exactly_one(r"^DEVICE (.+)$"),
        "pipeline_source": exactly_one(r"^PIPELINE_SOURCE (\S+)$"),
        "colors": colors,
        "depth_hex": None if depth == "absent" else depth,
        "depth_values": exactly_one(r"^DEPTH_VALUES (.+)$", required=False),
        "counter": int(str(exactly_one(r"^COUNTER (\d+)$"))),
        "status": exactly_one(r"^STATUS (\S+)$"),
    }
    if parsed["device"] != "Apple M4":
        raise ValueError(f"unexpected device: {parsed['device']}")
    if parsed["pipeline_source"] != "archive" or parsed["status"] != "OK":
        raise ValueError("render did not complete from forced archive")
    return parsed


def parse_exact(record: dict[str, object], expected_status: str) -> dict[str, object]:
    if record.get("exit") != 0 or record.get("timed_out"):
        raise ValueError("exact-region subprocess failed")
    result = json.loads(str(record["stdout"]))
    if result.get("status") != expected_status:
        raise ValueError(f"exact-region status {result.get('status')} != {expected_status}")
    region = result.get("region", {})
    if region.get("stage") != "fragment" or region.get("symbol") != "_agc.main":
        raise ValueError("exact-region attribution mismatch")
    if "whole" in str(result.get("access_contract", "")).lower():
        raise ValueError("exact-region access contract unexpectedly broad")
    start = int(region.get("absolute_offset", -1))
    length = int(region.get("length", -1))
    ranges = result.get("metadata_ranges")
    if start < 0 or length <= 0 or not isinstance(ranges, list):
        raise ValueError("exact-region/transcript shape mismatch")
    total = 0
    for item in ranges:
        offset = int(item["offset"])
        size = int(item["bytes"])
        if offset < start + length and start < offset + size:
            raise ValueError("metadata access overlaps selected executable region")
        total += size
    if total != result.get("metadata_bytes_read"):
        raise ValueError("metadata access transcript byte-count mismatch")
    return result


def exact_extract(archive: Path, log: Path) -> dict[str, object]:
    result, record = invoke(
        [sys.executable, EXACT, "extract", archive], log, 30
    )
    if result:
        raise ValueError(f"exact fragment extraction failed with exit {result}")
    parsed = parse_exact(record, "EXTRACTED")
    main_hex = parsed["main_hex"]
    if not isinstance(main_hex, str) or len(main_hex) % 2 or not HEX_RE.fullmatch(main_hex):
        raise ValueError("malformed exact selected-main hex")
    main = bytes.fromhex(main_hex)
    if parsed["main_length"] != len(main):
        raise ValueError("selected-main length mismatch")
    if parsed["main_sha256"] != hashlib.sha256(main).hexdigest():
        raise ValueError("selected-main hash mismatch")
    return parsed


def archive_metadata(archive: Path, extraction: dict[str, object]) -> dict[str, object]:
    # stat() observes filesystem metadata only; the archive is never opened here.
    status = archive.stat()
    return {
        "archive_retained": False,
        "archive_local_work_path": str(archive.relative_to(HERE)),
        "archive_bytes": status.st_size,
        "archive_content_hash": None,
        "archive_hash_omission": (
            "intentional: container-wide hashing would read non-allowlisted bytes"
        ),
        "exact_region": extraction["region"],
        "metadata_bytes_read": extraction["metadata_bytes_read"],
        "metadata_read_sha256": extraction["metadata_read_sha256"],
        "metadata_ranges": extraction["metadata_ranges"],
    }


def normalized_case(
    out: Path,
    tag: str,
    archive: Path,
    source_hash: str,
    run_record: dict[str, object],
    extraction: dict[str, object],
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    main_hex = str(extraction["main_hex"])
    record: dict[str, object] = {
        "case": tag,
        "source_path": "source.metal",
        "source_sha256": source_hash,
        "main_hex": main_hex,
        "main_length": extraction["main_length"],
        "main_sha256": extraction["main_sha256"],
        "render": parse_render(str(run_record["stdout"])),
        **archive_metadata(archive, extraction),
    }
    if extra:
        record.update(extra)
    (out / f"case_{tag}.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n"
    )
    (out / f"own_{tag}.fragment.main.hex").write_text(main_hex + "\n")
    return record


def run_splice(
    out: Path,
    work: Path,
    probe: Path,
    source_hash: str,
    intact_baseline: dict[str, object],
    failures: list[dict[str, object]],
) -> None:
    archive = work / f"{SPLICE}.archive"
    rc, baseline_run = invoke(
        [probe, "--case", "mrt3-decl012", "--source", out / "source.metal",
         "--archive-out", archive],
        out / f"run_{SPLICE}_intact.json", 60,
    )
    if rc:
        failures.append({"case": SPLICE, "phase": "fresh_intact_render", "exit": rc})
        return
    try:
        before = exact_extract(archive, out / f"extract_{SPLICE}_before.json")
        parse_render(str(baseline_run["stdout"]))
        if (
            before["main_length"] != intact_baseline["main_length"] or
            before["main_sha256"] != intact_baseline["main_sha256"] or
            before["main_hex"] != intact_baseline["main_hex"]
        ):
            raise ValueError("fresh splice archive main differs from intact case baseline")
        (out / f"own_{SPLICE}.before.fragment.main.hex").write_text(
            str(before["main_hex"]) + "\n"
        )
    except Exception as error:
        failures.append({"case": SPLICE, "phase": "fresh_intact_extract", "error": str(error)})
        return

    rc, patch_record = invoke(
        [
            sys.executable, EXACT, "patch", archive,
            "--expected-main-length", before["main_length"],
            "--expected-main-sha256", before["main_sha256"],
            "--signature-hex", "e70654",
            "--selector-offset", "5",
            "--before-byte", "02",
            "--after-byte", "04",
            "--expected-candidates", "1",
        ],
        out / f"mutation_{SPLICE}.json", 30,
    )
    if rc:
        failures.append({"case": SPLICE, "phase": "exact_region_patch", "exit": rc})
        return
    try:
        mutation = parse_exact(patch_record, "PATCHED")
        if (
            mutation["before_main_hex"] != before["main_hex"] or
            mutation["before_main_sha256"] != before["main_sha256"] or
            mutation["change_count"] != 1 or
            mutation["before_byte"] != 0x02 or mutation["after_byte"] != 0x04
        ):
            raise ValueError("mutation record failed exact one-byte guard")
        after_hex = str(mutation["after_main_hex"])
        after_bytes = bytes.fromhex(after_hex)
        if (
            len(after_bytes) != mutation["after_main_length"] or
            hashlib.sha256(after_bytes).hexdigest() != mutation["after_main_sha256"] or
            mutation["region"] != before["region"] or
            mutation["metadata_read_sha256"] != before["metadata_read_sha256"]
        ):
            raise ValueError("mutation exact-region hash/metadata mismatch")
        before_bytes = bytes.fromhex(str(before["main_hex"]))
        differences = [
            index for index, (old, new) in enumerate(zip(before_bytes, after_bytes))
            if old != new
        ]
        if differences != [mutation["changed_main_offset"]]:
            raise ValueError(f"unexpected selected-main differences: {differences}")
        after = {
            "status": "EXTRACTED",
            "access_contract": mutation["access_contract"],
            "region": mutation["region"],
            "main_hex": after_hex,
            "main_length": mutation["after_main_length"],
            "main_sha256": mutation["after_main_sha256"],
            "metadata_bytes_read": mutation["metadata_bytes_read"],
            "metadata_read_sha256": mutation["metadata_read_sha256"],
            "metadata_ranges": mutation["metadata_ranges"],
        }
    except Exception as error:
        failures.append({"case": SPLICE, "phase": "mutation_normalize", "error": str(error)})
        return

    rc, mutated_run = invoke(
        [probe, "--case", "mrt3-decl012", "--source", out / "source.metal",
         "--archive-in", archive],
        out / f"run_{SPLICE}.json", 60,
    )
    if rc:
        failures.append({"case": SPLICE, "phase": "mutated_render", "exit": rc})
        return
    try:
        normalized_case(
            out, SPLICE, archive, source_hash, mutated_run, after,
            {
                "fresh_intact_render": parse_render(str(baseline_run["stdout"])),
                "before_main_length": before["main_length"],
                "before_main_sha256": before["main_sha256"],
                "mutation": mutation,
            },
        )
    except Exception as error:
        failures.append({"case": SPLICE, "phase": "mutated_normalize", "error": str(error)})


def write_sums(out: Path) -> None:
    lines = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            lines.append(f"{digest(path)}  {path.relative_to(out)}")
    (out / "SHA256SUMS").write_text("\n".join(lines) + "\n")


def main() -> int:
    raise SystemExit(
        "BLOCKED DRAFT: exact fragment-main extent/container provenance is not established"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--anchor-commit", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"m4_clean_[0-9]{8}_run[0-9]{2}", args.run_id):
        raise SystemExit("run-id must match m4_clean_YYYYMMDD_runNN")

    # This is deliberately the first stateful gate. It uses authored text and Git
    # objects only; no compiler, Metal API, archive, or selected-main byte exists.
    anchor = verify_anchor(args.anchor_commit)
    out = RAW / args.run_id
    work = WORK / args.run_id
    RAW.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    out.mkdir(exist_ok=False)
    work.mkdir(exist_ok=False)
    shutil.copyfile(SOURCE, out / "source.metal")
    source_hash = digest(out / "source.metal")
    (out / "00_anchor.json").write_text(
        json.dumps(anchor, indent=2, sort_keys=True) + "\n"
    )
    (out / "01_environment.json").write_text(json.dumps({
        "run_id": args.run_id,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "anchor": anchor,
        "authored_inputs": json.loads(LOCK.read_text())["authored_inputs"],
        "clean_room": {
            "target": "local M4 only; no A18 claim",
            "v1_raw_and_claims": "QUARANTINED; not read or used",
            "apple_binary_introspection": "NONE",
            "apple_auxiliary_program_inspection": "NONE",
            "constant_program_bytes_read": "NONE",
            "other_stage_bytes_read": "NONE",
            "unknown_bo_inspection": "NONE",
            "compiled_bytes": "exact selected authored fragment _agc.main only",
            "archive_access": "declared metadata plus exact selected region; no whole-file hash",
        },
    }, indent=2, sort_keys=True) + "\n")

    for index, command in enumerate((
        ["sw_vers"], ["uname", "-a"], ["sysctl", "-n", "hw.model"],
        ["sysctl", "-n", "machdep.cpu.brand_string"], ["clang", "--version"],
    ), start=2):
        invoke(command, out / f"{index:02d}_environment_command.json", 15)

    probe = work / "render_probe"
    failures: list[dict[str, object]] = []
    rc, _build = invoke(
        ["clang", "-fobjc-arc", "-o", probe, HARNESS,
         "-framework", "Metal", "-framework", "Foundation"],
        out / "07_build_probe.json", 60,
    )
    intact: dict[str, dict[str, object]] = {}
    if rc:
        failures.append({"phase": "build_probe", "exit": rc})
    else:
        for case in CASES:
            archive = work / f"{case}.archive"
            rc, run_record = invoke(
                [probe, "--case", case, "--source", out / "source.metal",
                 "--archive-out", archive],
                out / f"run_{case}.json", 60,
            )
            if rc:
                failures.append({"case": case, "phase": "render", "exit": rc})
                continue
            try:
                extraction = exact_extract(archive, out / f"extract_{case}.json")
                intact[case] = normalized_case(
                    out, case, archive, source_hash, run_record, extraction
                )
            except Exception as error:
                failures.append({"case": case, "phase": "extract_or_normalize",
                                 "error": str(error)})
        if "mrt3-decl012" in intact:
            run_splice(out, work, probe, source_hash, intact["mrt3-decl012"], failures)
        else:
            failures.append({"case": SPLICE, "phase": "missing_intact_baseline"})

    (out / "failures.json").write_text(
        json.dumps(failures, indent=2, sort_keys=True) + "\n"
    )
    write_sums(out)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
