#!/usr/bin/env python3
"""Append-only runner for EXP-0055's exact two-VA live M4 trace."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RAW = HERE / "raw"
PRE = HERE / "PRE_REGISTRATION.md"
PROBE_SOURCE = HERE / "harness" / "probe.m"
TRACE_SOURCE = HERE / "harness" / "allowtrace.c"
PRE_HASH = "b3c1df8b72da3c14cd93897451ad686c66b6b49f80478ba6841f796a175a0b04"
PRE_COMMIT = "cf1ea53c8cc8d95dd28b740e407ffd11b9a51144"
PRIOR_COMMIT = "5b701aa587b15b13680a9d83854d563bcb46228a"
PRIOR_PARENT = "22ab13a10e7e0a744c5f847d2c7286ba6b2c1cad"
PRIOR_MANIFEST_HASH = "58d518daea1fca9a45fdab16bdc681425c64eaedc97eaf7a07f773604a59dcfb"
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
CASES = [
    "scissor-base", "scissor-x", "scissor-y", "scissor-width",
    "scissor-height", "scissor-empty-width", "scissor-empty-height",
    "multi-base", "multi-slot0-x", "multi-slot1-x", "dbias-zero",
    "dbias-constant-negative", "dbias-constant-positive",
    "dbias-slope-negative", "dbias-slope-positive",
    "dbias-large-negative", "dbias-clamp-negative",
    "dbias-large-positive", "dbias-clamp-positive",
]
SCHEDULES = ["plain", "pad64k"]
TRIALS = [
    (index, schedule, case, f"{index:03d}_{schedule}_{case}")
    for index, (schedule, case) in enumerate(
        ((schedule, case) for schedule in SCHEDULES for case in CASES), 1
    )
]
ALLOWED = {
    "va_58000": {"va": 0x58000, "size": 0x8000,
                  "role": "fixed-function-render-state"},
    "va_68000": {"va": 0x68000, "size": 0x88E0,
                  "role": "tiling-state"},
}
STATE_NAMES = {
    f"{stem}.{suffix}" for stem in ALLOWED for suffix in ("bin", "meta")
}
META_KEYS = {
    "gpu_va", "allocation_size", "read_size", "role", "mapping_handle",
    "mapping_occurrence", "fixed_allowlist", "pointer_following",
    "command_mutation",
}
HEADER = (
    "# EXP-0055 fixed_allowlist=2 unknown_bo_dump=0 pointer_following=0 "
    "shader_dump=0 command_mutation=0"
)
RESOURCE_RE = re.compile(
    r"RESOURCE_MAP class=(\S+) va=(0x[0-9a-f]+) size=(0x[0-9a-f]+) "
    r"handle=(\d+) cpu_present=(\d+) outcpu_present=(\d+) allowlisted=(\d+)"
)
DUMP_RE = re.compile(
    r"ALLOWLIST_DUMP va=(0x[0-9a-f]+) alloc=(0x[0-9a-f]+) "
    r"cap=(0x[0-9a-f]+) got=(0x[0-9a-f]+) role=(\S+) handle=(\d+) "
    r"occurrence=(\d+) expected_size=(0x[0-9a-f]+) kr=0x([0-9a-f]+) "
    r"bin_created=(\d+) meta_created=(\d+)"
)
# POST_CAPTURE_STRICT_TRACE_BEGIN
SERVICE_RE = re.compile(r"SERVICE_OPEN class=(\S+) type=(\d+)")
CALL_RE = re.compile(
    r"CALL class=(\S+) sel=(\d+) ret=(0x[0-9a-f]+) "
    r"in_struct=(0x[0-9a-f]+) out_struct=(0x[0-9a-f]+)"
)
# POST_CAPTURE_STRICT_TRACE_END
PUBLIC_HEADERS = [
    Path("/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks/Metal.framework/Headers/MTLRenderCommandEncoder.h"),
    Path("/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks/Metal.framework/Headers/MTLDepthStencil.h"),
    Path("/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks/Metal.framework/Headers/MTLRenderPass.h"),
]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def command(argv: list[object]) -> str:
    return subprocess.run(
        [str(value) for value in argv], check=True, capture_output=True,
        text=True, timeout=15,
    ).stdout.strip()


def invoke(argv: list[object], timeout: int,
           env: dict[str, str] | None = None,
           env_overrides: dict[str, str] | None = None) -> dict[str, object]:
    args = [str(value) for value in argv]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record: dict[str, object] = {
        "argv": args,
        "timeout_seconds": timeout,
        "started_utc": started,
    }
    if env_overrides is not None:
        record["environment_overrides"] = env_overrides
    try:
        cp = subprocess.run(args, capture_output=True, text=True,
                            timeout=timeout, env=env)
        record.update(exit=cp.returncode, stdout=cp.stdout, stderr=cp.stderr)
    except subprocess.TimeoutExpired as exc:
        def to_text(value: object) -> str:
            if isinstance(value, bytes):
                return value.decode(errors="replace")
            return str(value or "")
        record.update(exit=None, timed_out=True, stdout=to_text(exc.stdout),
                      stderr=to_text(exc.stderr))
    return record


def parse_meta(path: Path) -> dict[str, str]:
    lines = path.read_text().splitlines()
    if len(lines) != len(META_KEYS) or any(line.count("=") != 1 for line in lines):
        raise AssertionError(f"metadata grammar: {path}")
    pairs = [line.split("=", 1) for line in lines]
    keys = [pair[0] for pair in pairs]
    if len(keys) != len(set(keys)):
        raise AssertionError(f"metadata duplicate key: {path}")
    fields = dict(pairs)
    if set(fields) != META_KEYS:
        raise AssertionError(f"metadata keys: {path}")
    return fields


def preflight_all_payloads(out: Path) -> dict[str, object]:
    """Validate the complete matrix and metadata before any payload byte/hash."""
    trials_root = out / "trials"
    actual_trials = list(trials_root.iterdir())
    expected_names = {name for _, _, _, name in TRIALS}
    if ({path.name for path in actual_trials} != expected_names or
            any(not path.is_dir() or path.is_symlink() for path in actual_trials)):
        raise AssertionError("exact trial directory matrix")
    validated: list[dict[str, object]] = []
    for _, schedule, case, name in TRIALS:
        trial = trials_root / name
        if {path.name for path in trial.iterdir()} != {"run.json", "trace.log", "state"}:
            raise AssertionError(f"trial entry set: {name}")
        state = trial / "state"
        if not state.is_dir() or state.is_symlink():
            raise AssertionError(f"state directory: {name}")
        entries = list(state.iterdir())
        if ({path.name for path in entries} != STATE_NAMES or
                any(not path.is_file() or path.is_symlink() for path in entries)):
            raise AssertionError(f"exact state file set: {name}")
        metadata: dict[str, dict[str, str]] = {}
        for stem, spec in ALLOWED.items():
            binary = state / f"{stem}.bin"
            meta = state / f"{stem}.meta"
            fields = parse_meta(meta)
            if (int(fields["gpu_va"], 0) != spec["va"] or
                    fields["role"] != spec["role"]):
                raise AssertionError(f"VA/role: {meta}")
            if (fields["fixed_allowlist"], fields["pointer_following"],
                    fields["command_mutation"]) != ("1", "0", "0"):
                raise AssertionError(f"boundary flags: {meta}")
            if int(fields["mapping_occurrence"], 10) != 1:
                raise AssertionError(f"mapping occurrence: {meta}")
            size = binary.stat().st_size
            if not (size == int(fields["read_size"], 0) ==
                    int(fields["allocation_size"], 0) == spec["size"] <= 0x10000):
                raise AssertionError(f"bounded size: {binary}")
            if not fields["mapping_handle"].isdigit():
                raise AssertionError(f"mapping handle: {meta}")
            metadata[stem] = fields

        lines = (trial / "trace.log").read_text().splitlines()
        if lines.count(HEADER) != 1:
            raise AssertionError(f"trace header: {name}")
        resources = []
        dumps = []
# POST_CAPTURE_STRICT_TRACE_BEGIN
        services = 0
        calls = 0
# POST_CAPTURE_STRICT_TRACE_END
        for line in lines:
# POST_CAPTURE_STRICT_TRACE_BEGIN
            if line == HEADER:
                continue
            if line.startswith("SERVICE_OPEN "):
                if not SERVICE_RE.fullmatch(line):
                    raise AssertionError(f"service trace grammar: {name}")
                services += 1
                continue
            if line.startswith("CALL "):
                if not CALL_RE.fullmatch(line):
                    raise AssertionError(f"call trace grammar: {name}")
                calls += 1
                continue
            if not line.startswith(("RESOURCE_MAP ", "ALLOWLIST_DUMP ",
                                    "SNAPSHOT_ERROR ")):
                raise AssertionError(f"unknown trace record: {name}: {line!r}")
# POST_CAPTURE_STRICT_TRACE_END
            if line.startswith("RESOURCE_MAP "):
                match = RESOURCE_RE.fullmatch(line)
                if not match:
                    raise AssertionError(f"resource trace grammar: {name}")
                if match[7] == "1":
                    resources.append(match)
            elif line.startswith("ALLOWLIST_DUMP "):
                match = DUMP_RE.fullmatch(line)
                if not match:
                    raise AssertionError(f"dump trace grammar: {name}")
                dumps.append(match)
            elif line.startswith("SNAPSHOT_ERROR "):
                raise AssertionError(f"snapshot error: {name}")
# POST_CAPTURE_STRICT_TRACE_BEGIN
        if services != 2 or calls <= 0:
            raise AssertionError(f"service/call trace counts: {name}")
# POST_CAPTURE_STRICT_TRACE_END
        if len(resources) != 2 or len(dumps) != 2:
            raise AssertionError(f"exact trace counts: {name}")
        seen_resources: set[int] = set()
        for match in resources:
            va = int(match[2], 0)
            stems = [stem for stem, spec in ALLOWED.items() if spec["va"] == va]
            if len(stems) != 1 or va in seen_resources:
                raise AssertionError(f"resource VA/duplicate: {name}")
            stem = stems[0]
            fields = metadata[stem]
            spec = ALLOWED[stem]
            if (int(match[3], 0) != spec["size"] or
                    match[4] != fields["mapping_handle"] or
                    (match[5], match[6]) not in
                    {("1", "0"), ("0", "1"), ("1", "1")}):
                raise AssertionError(f"resource linkage: {name}/{stem}")
            seen_resources.add(va)
        seen_dumps: set[int] = set()
        for match in dumps:
            va = int(match[1], 0)
            stems = [stem for stem, spec in ALLOWED.items() if spec["va"] == va]
            if len(stems) != 1 or va in seen_dumps:
                raise AssertionError(f"dump VA/duplicate: {name}")
            stem = stems[0]
            fields = metadata[stem]
            spec = ALLOWED[stem]
            if not (int(match[2], 0) == int(match[3], 0) ==
                    int(match[4], 0) == int(match[8], 0) == spec["size"] and
                    match[5] == spec["role"] and
                    match[6] == fields["mapping_handle"] and
                    match[7] == "1" and int(match[9], 16) == 0 and
                    match[10] == "1" and match[11] == "1"):
                raise AssertionError(f"dump linkage: {name}/{stem}")
            seen_dumps.add(va)
        if seen_resources != {spec["va"] for spec in ALLOWED.values()} or seen_dumps != seen_resources:
            raise AssertionError(f"trace VA set: {name}")
        validated.append({"trial": name, "case": case,
                          "schedule": schedule, "payload_pairs": 2})
    return {"schema": 1, "preflight_before_payload_access": True,
            "trial_count": len(validated), "payload_pairs": len(validated) * 2,
            "trials": validated}


def append_failure(path: Path, value: dict[str, object]) -> None:
    with path.open("a") as stream:
        stream.write(json.dumps(value, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not RUN_ID.fullmatch(args.run_id):
        raise SystemExit("run-id must contain only alphanumerics, dash, underscore")
    if digest(PRE) != PRE_HASH:
        raise SystemExit("frozen preregistration hash mismatch")

    out = RAW / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    (out / "trials").mkdir()
    failures_path = out / "failures.jsonl"
    failures_path.write_text("")
    source_paths = [PRE, PROBE_SOURCE, TRACE_SOURCE, Path(__file__)]
    inputs = {
        "schema": 1,
        "pre_registration": {"commit": PRE_COMMIT, "sha256": PRE_HASH},
        "prior_evidence": {
            "experiment": "EXP-0048-bg-eot-pbe", "artifact_commit": PRIOR_COMMIT,
            "manifest_generation_revision": PRIOR_PARENT,
            "manifest_sha256": PRIOR_MANIFEST_HASH,
        },
        "authored_sources": {
            str(path.relative_to(REPO)): digest(path) for path in source_paths
        },
        "public_headers": {str(path): digest(path) for path in PUBLIC_HEADERS},
        "schedules": SCHEDULES,
        "cases": CASES,
        "trials": [name for _, _, _, name in TRIALS],
    }
    write_json(out / "00_inputs.json", inputs)
    environment = {
        "schema": 1,
        "run_id": args.run_id,
        "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "repository_revision": command(["git", "-C", REPO, "rev-parse", "HEAD"]),
        "target": {
            "model": command(["sysctl", "-n", "hw.model"]),
            "cpu_brand": command(["sysctl", "-n", "machdep.cpu.brand_string"]),
            "machine": platform.machine(),
            "sw_vers": command(["sw_vers"]),
        },
        "tools": {
            "clang": command(["xcrun", "clang", "--version"]).splitlines()[0],
            "python": platform.python_version(),
            "xcrun_path": command(["xcrun", "--find", "clang"]),
        },
        "clean_room": {
            "categories": ["HW-PROBE", "DATA-TRACE", "OWN-SHADER"],
            "target_qualification": "local M4 only; no A18 Pro validation",
            "allowed_state_vas": ["0x58000", "0x68000"],
            "apple_binary_introspection": "NONE",
            "apple_auxiliary_code_inspection": "NONE",
            "compiled_shader_bytes_inspected": "NONE",
            "command_bo_contents_inspected": "NONE",
            "unknown_bo_contents_inspected": "NONE",
            "pointer_following": "NONE",
            "generic_bo_scan": "NONE",
            "mutation_splice_replay": "NONE",
        },
    }
    write_json(out / "01_environment.json", environment)

    failure_count = 0
    with tempfile.TemporaryDirectory(prefix="exp0055-") as temporary:
        work = Path(temporary)
        tracer = work / "allowtrace.dylib"
        probe = work / "probe"
        build_trace = invoke([
            "xcrun", "clang", "-arch", "arm64e", "-dynamiclib", "-o", tracer,
            TRACE_SOURCE, "-framework", "IOKit", "-framework", "CoreFoundation",
        ], 60)
        if build_trace.get("exit") == 0:
            build_trace["product"] = {"bytes": tracer.stat().st_size,
                                      "sha256": digest(tracer),
                                      "retained": False, "semantic_inspection": "NONE"}
        write_json(out / "02_build_allowtrace.json", build_trace)
        if build_trace.get("exit") != 0:
            append_failure(failures_path, {"phase": "build_allowtrace",
                                           "record": "02_build_allowtrace.json"})
            failure_count += 1

        build_probe = invoke([
            "xcrun", "clang", "-arch", "arm64e", "-fobjc-arc", "-o", probe,
            PROBE_SOURCE, "-framework", "Metal", "-framework", "Foundation",
        ], 60)
        if build_probe.get("exit") == 0:
            build_probe["product"] = {"bytes": probe.stat().st_size,
                                      "sha256": digest(probe),
                                      "retained": False, "semantic_inspection": "NONE"}
        write_json(out / "03_build_probe.json", build_probe)
        if build_probe.get("exit") != 0:
            append_failure(failures_path, {"phase": "build_probe",
                                           "record": "03_build_probe.json"})
            failure_count += 1

        if build_trace.get("exit") == 0 and build_probe.get("exit") == 0:
            for _, schedule, case, name in TRIALS:
                trial = out / "trials" / name
                trial.mkdir()
                overrides = {
                    "DYLD_INSERT_LIBRARIES": str(tracer),
                    "ALLOWTRACE_LOG": str(trial / "trace.log"),
                    "ALLOWTRACE_DUMP_DIR": str(trial / "state"),
                }
                env = os.environ.copy()
                env.update(overrides)
                record = invoke([
                    probe, "--case", case, "--schedule", schedule, "--dump",
                ], 45, env, overrides)
                write_json(trial / "run.json", record)
                if record.get("exit") != 0:
                    append_failure(failures_path, {
                        "phase": "gpu_process", "trial": name,
                        "exit": record.get("exit"),
                        "timed_out": record.get("timed_out", False),
                    })
                    failure_count += 1

            try:
                boundary = preflight_all_payloads(out)
                # Payload access starts only after the full matrix preflight.
                anchors = []
                for schedule in SCHEDULES:
                    name = next(name for _, sched, case, name in TRIALS
                                if sched == schedule and case == "scissor-base")
                    state = out / "trials" / name / "state" / "va_58000.bin"
                    data = state.read_bytes()
                    anchor = {"trial": name, "offset_0x14": data[0x14],
                              "offset_0x53": data[0x53],
                              "expected": {"offset_0x14": 0x19,
                                           "offset_0x53": 0x00}}
                    anchors.append(anchor)
                    if data[0x14] != 0x19 or data[0x53] != 0x00:
                        raise AssertionError(f"fixed-state role anchor: {name}")
                boundary["fixed_state_role_anchors"] = anchors
                write_json(out / "04_boundary_preflight.json", boundary)
            except Exception as exc:
                append_failure(failures_path, {"phase": "boundary_preflight",
                                               "error": str(exc)})
                failure_count += 1

    # Hash payloads only if the mandatory full preflight/anchor record exists.
    if (out / "04_boundary_preflight.json").exists():
        inventory = []
        for path in sorted(value for value in out.rglob("*")
                           if value.is_file() and value.name != "SHA256SUMS"):
            inventory.append(f"{digest(path)}  {path.relative_to(out)}")
        (out / "SHA256SUMS").write_text("\n".join(inventory) + "\n")

    print(json.dumps({"run": args.run_id, "trials": len(TRIALS),
                      "failures": failure_count,
                      "preflight": (out / "04_boundary_preflight.json").exists()},
                     sort_keys=True))
    return 1 if failure_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
