#!/usr/bin/env python3
"""Verify frozen EXP-0052 evidence without executing the GPU."""

import datetime
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path, PurePosixPath


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PRE_HASH = "92ffe845be42a8dee30f4116cb239156eb3111295bf4dcd9d8b71048887625fa"
BASE_REVISION = "2fd358311e36a8b60fc56eaf3947880cc3ea0f1c"
RUNS = {
    "m4_20260817_run01": -10,
    "m4_20260817_run02": -10,
    "m4_20260817_run03": 0,
    "m4_20260817_run04": 0,
}
RUN_FILES = {"SHA256SUMS", "build.json", "environment.json", "failures.json", "run.json"}
AUTHORED_PATHS = {
    "experiments/EXP-0052-m4-timestamp-semantics/PRE_REGISTRATION.md",
    "experiments/EXP-0052-m4-timestamp-semantics/harness/probe.m",
    "experiments/EXP-0052-m4-timestamp-semantics/run.py",
}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256(path):
    return sha256_bytes(path.read_bytes())


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def parse_inventory(path):
    entries = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        parts = line.split("  ")
        require(len(parts) == 2 and len(parts[0]) == 64,
                f"malformed {path}:{number}")
        digest, relative = parts
        try:
            int(digest, 16)
        except ValueError:
            require(False, f"nonhex digest {path}:{number}")
        pure = PurePosixPath(relative)
        require(not pure.is_absolute() and ".." not in pure.parts,
                f"unsafe inventory path {relative}")
        require(relative not in entries, f"duplicate inventory path {relative}")
        entries[relative] = digest
    return entries


def historical_sources():
    current = (HERE / "harness/probe.m").read_text()
    original_readback = current.replace(
        "bytesPerRow:4 fromRegion:MTLRegionMake2D(0,0,1,1)",
        "bytesPerRow:256 fromRegion:MTLRegionMake2D(0,0,64,64)",
    )
    require(original_readback != current, "cannot reconstruct original readback")
    run01 = original_readback.replace("    setvbuf(stdout, NULL, _IONBF, 0);\n", "")
    require(run01 != original_readback, "cannot reconstruct buffered run")
    return {
        "m4_20260817_run01": sha256_bytes(run01.encode()),
        "m4_20260817_run02": sha256_bytes(original_readback.encode()),
        "m4_20260817_run03": sha256(HERE / "harness/probe.m"),
        "m4_20260817_run04": sha256(HERE / "harness/probe.m"),
    }


def verify_runs():
    raw = HERE / "raw"
    dirs = {path.name for path in raw.iterdir() if path.is_dir()}
    require(dirs == set(RUNS), "raw run-directory set")
    expected_harness = historical_sources()

    for run_id, expected_exit in RUNS.items():
        run_dir = raw / run_id
        actual_files = {path.name for path in run_dir.iterdir() if path.is_file()}
        require(actual_files == RUN_FILES, f"{run_id}: file set")
        require(not any(path.is_symlink() for path in run_dir.iterdir()),
                f"{run_id}: symlink")
        inventory = parse_inventory(run_dir / "SHA256SUMS")
        require(set(inventory) == RUN_FILES - {"SHA256SUMS"},
                f"{run_id}: inventory coverage")
        for relative, digest in inventory.items():
            require(sha256(run_dir / relative) == digest,
                    f"{run_id}: hash {relative}")

        environment = json.loads((run_dir / "environment.json").read_text())
        build = json.loads((run_dir / "build.json").read_text())
        result = json.loads((run_dir / "run.json").read_text())
        failures = json.loads((run_dir / "failures.json").read_text())
        require(environment["pre_registration_sha256"] == PRE_HASH,
                f"{run_id}: preregistration")
        require(environment["repo_revision"] == BASE_REVISION,
                f"{run_id}: base revision")
        require(environment["target"] == {
            "cpu_brand": "Apple M4",
            "machine": "arm64",
            "model": "Mac16,10",
            "sw_vers": "ProductName:\t\tmacOS\nProductVersion:\t\t26.6.2\nBuildVersion:\t\t25G82",
        }, f"{run_id}: target")
        require(environment["apple_binary_introspection"] == "NONE",
                f"{run_id}: Apple binary marker")
        require(environment["apple_auxiliary_code_inspection"] == "NONE",
                f"{run_id}: auxiliary marker")
        require(environment["compiled_shader_bytes_inspected"] == "NONE",
                f"{run_id}: compiled shader marker")
        require(environment["iokit_payload_tracing"] == "NONE",
                f"{run_id}: IOKit marker")
        require(set(environment["authored_sources"]) == AUTHORED_PATHS,
                f"{run_id}: authored path set")
        require(environment["authored_sources"][next(
            path for path in AUTHORED_PATHS if path.endswith("PRE_REGISTRATION.md")
        )] == PRE_HASH, f"{run_id}: pre hash")
        require(environment["authored_sources"][next(
            path for path in AUTHORED_PATHS if path.endswith("run.py")
        )] == sha256(HERE / "run.py"), f"{run_id}: runner hash")
        require(environment["authored_sources"][next(
            path for path in AUTHORED_PATHS if path.endswith("probe.m")
        )] == expected_harness[run_id], f"{run_id}: harness reconstruction")

        require(build["exit"] == 0 and build["timeout_seconds"] == 60,
                f"{run_id}: build")
        require(result["exit"] == expected_exit and result["timeout_seconds"] == 90,
                f"{run_id}: execution")
        require(not result.get("timed_out", False), f"{run_id}: timeout")
        if expected_exit == 0:
            require(failures == [], f"{run_id}: unexpected failure record")
            require(result["stdout"].endswith("PIXEL 5340bfff\nRESULT OK\n"),
                    f"{run_id}: result tail")
        else:
            require(failures == [{"phase": "run", "record": "run.json"}],
                    f"{run_id}: missing preserved failure")


def verify_analysis():
    with tempfile.TemporaryDirectory(prefix="exp0052-verify-") as temp:
        subprocess.run(
            ["python3", str(HERE / "analysis/analyze.py"), "--output-dir", temp],
            check=True, capture_output=True, text=True, timeout=15,
        )
        for name in ("summary.json", "report.txt"):
            require((Path(temp) / name).read_bytes() == (HERE / "analysis" / name).read_bytes(),
                    f"stale analysis/{name}")


def verify_manifest():
    manifest = json.loads((HERE / "manifest.json").read_text())
    require(manifest["schema"] == 1, "manifest schema")
    require(manifest["experiment"] == "EXP-0052-m4-timestamp-semantics",
            "manifest experiment")
    require(manifest["pre_registration_sha256"] == PRE_HASH, "manifest preregistration")
    require(manifest["canonical_runs"] == ["m4_20260817_run03", "m4_20260817_run04"],
            "manifest canonical runs")
    require(manifest["preserved_failed_runs"] ==
            ["m4_20260817_run01", "m4_20260817_run02"],
            "manifest failed runs")
    require(manifest["apple_binary_introspection"] == "NONE", "manifest marker")
    datetime.datetime.fromisoformat(manifest["generated_at_utc"])

    listed = {}
    for artifact in manifest["artifacts"]:
        relative = artifact["path"]
        pure = PurePosixPath(relative)
        require(not pure.is_absolute() and ".." not in pure.parts,
                f"unsafe manifest path {relative}")
        require(relative not in listed, f"duplicate manifest path {relative}")
        listed[relative] = artifact
    actual = {
        path.relative_to(HERE).as_posix(): path
        for path in HERE.rglob("*")
        if path.is_file() and path.name != "manifest.json" and
        "__pycache__" not in path.relative_to(HERE).parts
    }
    require(set(listed) == set(actual), "manifest coverage")
    for relative, path in actual.items():
        require(not path.is_symlink(), f"symlink {relative}")
        require(path.suffix not in {".air", ".metallib", ".dylib", ".a", ".bin"},
                f"forbidden compiled/binary artifact {relative}")
        artifact = listed[relative]
        require(path.stat().st_size == artifact["bytes"], f"size {relative}")
        require(sha256(path) == artifact["sha256"], f"hash {relative}")


def main():
    require(sha256(HERE / "PRE_REGISTRATION.md") == PRE_HASH,
            "pre-registration hash")
    verify_runs()
    verify_analysis()
    verify_manifest()
    manifest = json.loads((HERE / "manifest.json").read_text())
    print(
        "PASS prereg=1 raw_runs=4 canonical=2 preserved_failures=2 "
        f"analysis=PASS manifest_artifacts={len(manifest['artifacts'])}"
    )


if __name__ == "__main__":
    main()
