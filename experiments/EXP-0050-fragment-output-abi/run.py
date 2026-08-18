#!/usr/bin/env python3
"""Run the frozen EXP-0050 authored fragment-output matrix once."""
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
RAW = HERE / "raw"
WORK = HERE / "work"
HARNESS = HERE / "harness" / "render_probe.m"
SOURCE = HERE / "kernels" / "output_matrix.metal"
PARSER = REPO / "tools" / "shdump" / "agxparse.py"
PREREG_HASH = "99cd47d7c75687c1ce816826c57507b73a9d827f0deed56243a1122d2959748f"

CASES = [
    "c0", "c1-only", "c2-only", "c0-c2-decl02", "c0-c2-decl20",
    "mrt3-decl012", "mrt3-decl210", "mrt3-swap12", "color-depth",
    "depth-color-decl", "depth-only", "color-fixed-depth", "mask-f",
    "mask-5", "mask-a", "mask-0", "mask-5-declfirst", "discard-half",
    "atomic-all", "atomic-before-discard", "atomic-after-discard",
]

HEX_RE = re.compile(r"^[0-9a-f]+$")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def invoke(command: list[object], log: Path, timeout: int,
           env: dict[str, str] | None = None) -> tuple[int, dict[str, object]]:
    argv = [str(x) for x in command]
    started = time.time()
    record: dict[str, object] = {
        "command": argv,
        "started_unix": started,
        "timeout_seconds": timeout,
    }
    try:
        cp = subprocess.run(argv, capture_output=True, text=True,
                            timeout=timeout, env=env)
        record.update(exit=cp.returncode,
                      elapsed_seconds=round(time.time() - started, 6),
                      stdout=cp.stdout, stderr=cp.stderr)
        rc = cp.returncode
    except subprocess.TimeoutExpired as exc:
        def text(value: object) -> str:
            if isinstance(value, bytes):
                return value.decode(errors="replace")
            return str(value or "")
        record.update(timeout=True,
                      elapsed_seconds=round(time.time() - started, 6),
                      stdout=text(exc.stdout), stderr=text(exc.stderr))
        rc = 124
    log.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return rc, record


def parse_render(stdout: str) -> dict[str, object]:
    def one(pattern: str, required: bool = True) -> str | None:
        match = re.search(pattern, stdout, re.M)
        if required and not match:
            raise ValueError(f"missing output pattern {pattern!r}")
        return match.group(1) if match else None

    colors: list[str | None] = []
    for index in range(3):
        value = one(rf"^COLOR{index}_HEX (\S+)$")
        colors.append(None if value == "absent" else value)
    depth = one(r"^DEPTH_HEX (\S+)$")
    return {
        "device": one(r"^DEVICE (.+)$"),
        "pipeline_source": one(r"^PIPELINE_SOURCE (\S+)$"),
        "colors": colors,
        "depth_hex": None if depth == "absent" else depth,
        "depth_values": one(r"^DEPTH_VALUES (.+)$", required=False),
        "counter": int(one(r"^COUNTER (\d+)$")),
        "status": one(r"^STATUS (\S+)$"),
    }


def extract_main(archive: Path, out: Path, tag: str,
                 failures: list[dict[str, object]]) -> tuple[str, dict[str, object]] | None:
    rc, rec = invoke(
        [sys.executable, PARSER, archive, "--stage", "fragment", "--extract-hex"],
        out / f"extract_{tag}.json", 30)
    if rc:
        failures.append({"case": tag, "phase": "extract_main", "exit": rc})
        return None
    main_hex = str(rec["stdout"]).strip()
    if not main_hex or len(main_hex) % 2 or not HEX_RE.fullmatch(main_hex):
        failures.append({"case": tag, "phase": "extract_main_format"})
        return None
    main_bytes = bytes.fromhex(main_hex)
    (out / f"own_{tag}.fragment.main.hex").write_text(main_hex + "\n")
    meta = {
        "main_hex": main_hex,
        "main_length": len(main_bytes),
        "main_sha256": hashlib.sha256(main_bytes).hexdigest(),
    }
    return main_hex, meta


def write_case(out: Path, tag: str, archive: Path, source_hash: str,
               run_record: dict[str, object], main_meta: dict[str, object],
               extra: dict[str, object] | None = None) -> None:
    parsed = parse_render(str(run_record["stdout"]))
    record: dict[str, object] = {
        "case": tag,
        "source_path": "source.metal",
        "source_sha256": source_hash,
        "archive_retained": False,
        "archive_local_work_path": str(archive.relative_to(HERE)),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": sha256(archive),
        "render": parsed,
        **main_meta,
    }
    if extra:
        record.update(extra)
    (out / f"case_{tag}.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n")


def make_splice(out: Path, work: Path, archive: Path,
                source_hash: str, probe: Path,
                failures: list[dict[str, object]]) -> None:
    tag = "splice-rt1-to-rt2"
    rc, locate = invoke(
        [sys.executable, PARSER, archive, "--stage", "fragment",
         "--locate", "_agc.main"], out / f"locate_{tag}.json", 30)
    if rc:
        failures.append({"case": tag, "phase": "locate", "exit": rc})
        return
    try:
        absolute, length = map(int, str(locate["stdout"]).split())
    except Exception:
        failures.append({"case": tag, "phase": "locate_parse"})
        return
    data = bytearray(archive.read_bytes())
    main = bytes(data[absolute:absolute + length])
    stores = [i for i in range(len(main) - 11)
              if main[i:i + 3] == b"\xe7\x06\x54"]
    candidates = [i for i in stores if main[i + 5] == 0x02]
    if len(candidates) != 1:
        failure = {"case": tag, "phase": "splice_signature",
                   "store_offsets": stores, "rt1_candidates": candidates}
        failures.append(failure)
        (out / f"mutation_{tag}.json").write_text(
            json.dumps({**failure, "status": "SKIPPED"}, indent=2, sort_keys=True) + "\n")
        return
    rel = candidates[0]
    mutated = bytearray(main)
    mutated[rel + 5] = 0x04
    changes = [(i, a, b) for i, (a, b) in enumerate(zip(main, mutated)) if a != b]
    if changes != [(rel + 5, 0x02, 0x04)]:
        failures.append({"case": tag, "phase": "splice_change_guard"})
        return
    spliced = work / f"{tag}.archive"
    shutil.copyfile(archive, spliced)
    spliced_data = bytearray(spliced.read_bytes())
    spliced_data[absolute:absolute + length] = mutated
    spliced.write_bytes(spliced_data)
    mutated_hex = bytes(mutated).hex()
    (out / f"own_{tag}.fragment.main.hex").write_text(mutated_hex + "\n")
    mutation = {
        "status": "APPLIED",
        "source_case": "mrt3-decl012",
        "source_archive_sha256": sha256(archive),
        "spliced_archive_sha256": sha256(spliced),
        "main_file_offset": absolute,
        "main_length": length,
        "store_offsets": stores,
        "selected_store_offset": rel,
        "changed_main_offset": rel + 5,
        "before": "0x02",
        "after": "0x04",
        "change_count": 1,
        "purpose": "reroute authored RT1 store to already-valid RT2",
    }
    (out / f"mutation_{tag}.json").write_text(
        json.dumps(mutation, indent=2, sort_keys=True) + "\n")
    rc, run_record = invoke(
        [probe, "--case", "mrt3-decl012", "--source", out / "source.metal",
         "--archive-in", spliced], out / f"run_{tag}.json", 60)
    if rc:
        failures.append({"case": tag, "phase": "render", "exit": rc})
        return
    try:
        main_meta = {
            "main_hex": mutated_hex,
            "main_length": len(mutated),
            "main_sha256": hashlib.sha256(mutated).hexdigest(),
        }
        write_case(out, tag, spliced, source_hash, run_record, main_meta,
                   {"mutation": mutation})
    except Exception as exc:
        failures.append({"case": tag, "phase": "normalize", "error": str(exc)})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        raise SystemExit("run-id may contain alphanumerics, dash, underscore")
    prereg = HERE / "PRE_REGISTRATION.md"
    if sha256(prereg) != PREREG_HASH:
        raise SystemExit(f"frozen preregistration hash mismatch: {sha256(prereg)}")

    out = RAW / args.run_id
    work = WORK / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    work.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(SOURCE, out / "source.metal")
    source_hash = sha256(out / "source.metal")
    (out / "00_preregistration.json").write_text(json.dumps({
        "path": "PRE_REGISTRATION.md",
        "sha256": PREREG_HASH,
        "verified_before_build_and_hardware": True,
        "started_unix": time.time(),
    }, indent=2, sort_keys=True) + "\n")
    (out / "01_environment.json").write_text(json.dumps({
        "run_id": args.run_id,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "repository_head": subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], check=True,
            capture_output=True, text=True, timeout=10).stdout.strip(),
        "inputs": {
            "source.metal": source_hash,
            "harness/render_probe.m": sha256(HARNESS),
            "run.py": sha256(Path(__file__)),
            "tools/shdump/agxparse.py": sha256(PARSER),
        },
        "clean_room": {
            "target": "local M4 only; no A18 claim",
            "apple_binary_introspection": "NONE",
            "apple_auxiliary_program_inspection": "NONE",
            "unknown_bo_inspection": "NONE",
            "compiled_bytes": "exact fragment _agc.main from source.metal only",
        },
    }, indent=2, sort_keys=True) + "\n")

    for index, command in enumerate((["sw_vers"], ["uname", "-a"],
                                     ["sysctl", "-n", "hw.model"],
                                     ["sysctl", "-n", "machdep.cpu.brand_string"],
                                     ["clang", "--version"]), start=2):
        invoke(command, out / f"{index:02d}_environment_command.json", 15)

    probe = work / "render_probe"
    failures: list[dict[str, object]] = []
    rc, _ = invoke(
        ["clang", "-fobjc-arc", "-o", probe, HARNESS,
         "-framework", "Metal", "-framework", "Foundation"],
        out / "07_build_probe.json", 60)
    if rc:
        failures.append({"phase": "build_probe", "exit": rc})
    else:
        for case in CASES:
            archive = work / f"{case}.archive"
            rc, run_record = invoke(
                [probe, "--case", case, "--source", out / "source.metal",
                 "--archive-out", archive], out / f"run_{case}.json", 60)
            if rc:
                failures.append({"case": case, "phase": "render", "exit": rc})
                continue
            extracted = extract_main(archive, out, case, failures)
            if not extracted:
                continue
            _, main_meta = extracted
            try:
                write_case(out, case, archive, source_hash, run_record, main_meta)
            except Exception as exc:
                failures.append({"case": case, "phase": "normalize", "error": str(exc)})
        intact = work / "mrt3-decl012.archive"
        if intact.exists():
            make_splice(out, work, intact, source_hash, probe, failures)
        else:
            failures.append({"case": "splice-rt1-to-rt2", "phase": "missing_baseline_archive"})

    (out / "failures.json").write_text(
        json.dumps(failures, indent=2, sort_keys=True) + "\n")
    sums = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            sums.append(f"{sha256(path)}  {path.relative_to(out)}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
