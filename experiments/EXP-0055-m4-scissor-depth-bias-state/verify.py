#!/usr/bin/env python3
"""Independent strict verifier for EXP-0055 clean M4 evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CAPTURE_HERE = Path(
    "/Users/user/asahi_re/public/agx-re/experiments/EXP-0055-m4-scissor-depth-bias-state"
)
sys.dont_write_bytecode = True
RUNS = ["m4_20260817_run01", "m4_20260817_run02"]
PRE_COMMIT = "cf1ea53c8cc8d95dd28b740e407ffd11b9a51144"
PRE_HASH = "b3c1df8b72da3c14cd93897451ad686c66b6b49f80478ba6841f796a175a0b04"
PRIOR_COMMIT = "5b701aa587b15b13680a9d83854d563bcb46228a"
PRIOR_PARENT = "22ab13a10e7e0a744c5f847d2c7286ba6b2c1cad"
PRIOR_MANIFEST_HASH = "58d518daea1fca9a45fdab16bdc681425c64eaedc97eaf7a07f773604a59dcfb"
RAW_INVENTORY_HASHES = {
    "m4_20260817_run01": "c22c56850c9c973b8a4555f73a49740c42dbdb79eee095ca06da8ba4bf06bf95",
    "m4_20260817_run02": "e8813425a21eaa2d20d808989c02900cdf818eed1826990692604845a79ed9a0",
}
SOURCE_HASHES = {
    "experiments/EXP-0055-m4-scissor-depth-bias-state/PRE_REGISTRATION.md": PRE_HASH,
    "experiments/EXP-0055-m4-scissor-depth-bias-state/harness/allowtrace.c": "47c9f65f97bb261a2632fb54042b4f363d1f4c0f77c6ceb602e9a76310450231",
    "experiments/EXP-0055-m4-scissor-depth-bias-state/harness/probe.m": "316055e347c834aba67422a8ec93c352e581e55ab4b3571095991536bc9a1bb5",
    "experiments/EXP-0055-m4-scissor-depth-bias-state/run.py": "328adea7e37b1925baa268674e773b58647eff5ad935cb4e5b6b4c3abe674558",
}
PUBLIC_HEADERS = {
    "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks/Metal.framework/Headers/MTLDepthStencil.h": "805b0de8de507148e609522f920bfc3a5ad526fe8ffe3eaeaef93f240326e665",
    "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks/Metal.framework/Headers/MTLRenderCommandEncoder.h": "8fbac9b5ab95dcb000a189d165176ac027284c6686633e711098ee45b8d930db",
    "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks/Metal.framework/Headers/MTLRenderPass.h": "9597f7e7e0cd11cf86997d8276803b0f866aebbfc4bb673deb9234e49b3470dc",
}
ANALYSIS_HASHES = {
    "analysis/summary.json": "2dd05938b73fcd121f71d916c7af2f65fdb6add1f7185a3748efa891c58875c8",
    "analysis/report.txt": "b9948fcff31c99c56537fa108bf5b11c5f8ac82be0ca902e24ceb7f565608e05",
}
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
    "va_58000": (0x58000, 0x8000, "fixed-function-render-state"),
    "va_68000": (0x68000, 0x88E0, "tiling-state"),
}
STATE_NAMES = {f"{stem}.{suffix}" for stem in ALLOWED for suffix in ("bin", "meta")}
META_KEYS = {"gpu_va", "allocation_size", "read_size", "role",
             "mapping_handle", "mapping_occurrence", "fixed_allowlist",
             "pointer_following", "command_mutation"}
HEADER = ("# EXP-0055 fixed_allowlist=2 unknown_bo_dump=0 pointer_following=0 "
          "shader_dump=0 command_mutation=0")
RESOURCE_RE = re.compile(
    r"RESOURCE_MAP class=(\S+) va=(0x[0-9a-f]+) size=(0x[0-9a-f]+) "
    r"handle=(\d+) cpu_present=(\d+) outcpu_present=(\d+) allowlisted=(\d+)")
DUMP_RE = re.compile(
    r"ALLOWLIST_DUMP va=(0x[0-9a-f]+) alloc=(0x[0-9a-f]+) "
    r"cap=(0x[0-9a-f]+) got=(0x[0-9a-f]+) role=(\S+) handle=(\d+) "
    r"occurrence=(\d+) expected_size=(0x[0-9a-f]+) kr=0x([0-9a-f]+) "
    r"bin_created=(\d+) meta_created=(\d+)")
SERVICE_RE = re.compile(r"SERVICE_OPEN class=(\S+) type=(\d+)")
CALL_RE = re.compile(
    r"CALL class=(\S+) sel=(\d+) ret=(0x[0-9a-f]+) "
    r"in_struct=(0x[0-9a-f]+) out_struct=(0x[0-9a-f]+)"
)
SHA_LINE = re.compile(r"([0-9a-f]{64})  ([^/].*)")
STATIC_ARTIFACTS = {
    "PRE_REGISTRATION.md", "README.md", "RESULTS.md",
    "harness/allowtrace.c", "harness/probe.m", "run.py",
    "analysis/analyze.py", "analysis/run_analysis.py",
    "analysis/failures.md", "analysis/invocation.json", "analysis/report.txt", "analysis/summary.json",
    "make_manifest.py", "verify.py",
}
RUN_TOP = {"00_inputs.json", "01_environment.json", "02_build_allowtrace.json",
           "03_build_probe.json", "04_boundary_preflight.json",
           "failures.jsonl", "SHA256SUMS", "trials"}
FORBIDDEN_SUFFIXES = {".dylib", ".metallib", ".air", ".o", ".a", ".so"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> object:
    def reject(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key {path}: {key}")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=reject)


def parse_meta(path: Path) -> dict[str, str]:
    lines = path.read_text().splitlines()
    require(len(lines) == len(META_KEYS) and
            all(line.count("=") == 1 for line in lines), f"meta grammar {path}")
    pairs = [line.split("=", 1) for line in lines]
    require(len({pair[0] for pair in pairs}) == len(pairs), f"meta duplicate {path}")
    fields = dict(pairs)
    require(set(fields) == META_KEYS, f"meta keys {path}")
    return fields


def captured_runner_bytes() -> bytes:
    """Reconstruct the exact live-runner bytes before post-capture hardening."""
    lines = (HERE / "run.py").read_text().splitlines(keepends=True)
    result: list[str] = []
    inside = False
    blocks = 0
    for line in lines:
        if line.rstrip("\n") == "# POST_CAPTURE_STRICT_TRACE_BEGIN":
            require(not inside, "nested runner hardening marker")
            inside = True
            blocks += 1
            continue
        if line.rstrip("\n") == "# POST_CAPTURE_STRICT_TRACE_END":
            require(inside, "unmatched runner hardening marker")
            inside = False
            continue
        if not inside:
            result.append(line)
    require(not inside and blocks == 4, "runner hardening marker count")
    return "".join(result).encode()


def metadata_preflight() -> set[str]:
    """Validate the global exact payload matrix before any payload read/hash."""
    raw = HERE / "raw"
    roots = list(raw.iterdir())
    require({path.name for path in roots} == set(RUNS) and
            all(path.is_dir() and not path.is_symlink() for path in roots),
            "preflight raw run set")
    allowed_paths: set[str] = set()
    trace_totals = {"header": 0, "service": 0, "call": 0,
                    "resource": 0, "dump": 0}
    for run in RUNS:
        root = raw / run
        require({path.name for path in root.iterdir()} == RUN_TOP,
                f"preflight run entries {run}")
        trials = root / "trials"
        require(trials.is_dir() and not trials.is_symlink(), f"preflight trials {run}")
        actual_trials = list(trials.iterdir())
        require({path.name for path in actual_trials} == {name for _, _, _, name in TRIALS} and
                all(path.is_dir() and not path.is_symlink() for path in actual_trials),
                f"preflight trial matrix {run}")
        for _, _, _, name in TRIALS:
            trial = trials / name
            require({path.name for path in trial.iterdir()} == {"run.json", "trace.log", "state"},
                    f"preflight trial entries {run}/{name}")
            state = trial / "state"
            entries = list(state.iterdir())
            require(state.is_dir() and not state.is_symlink() and
                    {path.name for path in entries} == STATE_NAMES and
                    all(path.is_file() and not path.is_symlink() for path in entries),
                    f"preflight state set {run}/{name}")
            metadata: dict[str, dict[str, str]] = {}
            for stem, (va, size, role) in ALLOWED.items():
                binary = state / f"{stem}.bin"
                meta = state / f"{stem}.meta"
                fields = parse_meta(meta)
                require(int(fields["gpu_va"], 0) == va and fields["role"] == role,
                        f"preflight VA/role {meta}")
                require((fields["fixed_allowlist"], fields["pointer_following"],
                         fields["command_mutation"]) == ("1", "0", "0") and
                        fields["mapping_handle"].isdigit() and
                        fields["mapping_occurrence"] == "1",
                        f"preflight boundary {meta}")
                require(binary.stat().st_size == int(fields["read_size"], 0) ==
                        int(fields["allocation_size"], 0) == size <= 0x10000,
                        f"preflight size {binary}")
                metadata[stem] = fields
                allowed_paths |= {str(binary.relative_to(HERE)), str(meta.relative_to(HERE))}

            lines = (trial / "trace.log").read_text().splitlines()
            require(lines.count(HEADER) == 1, f"preflight trace header {run}/{name}")
            trace_totals["header"] += 1
            resources = []
            dumps = []
            for line in lines:
                if line == HEADER:
                    continue
                if line.startswith("SERVICE_OPEN "):
                    require(bool(SERVICE_RE.fullmatch(line)),
                            f"preflight service grammar {run}/{name}")
                    trace_totals["service"] += 1
                elif line.startswith("CALL "):
                    require(bool(CALL_RE.fullmatch(line)),
                            f"preflight call grammar {run}/{name}")
                    trace_totals["call"] += 1
                elif line.startswith("RESOURCE_MAP "):
                    match = RESOURCE_RE.fullmatch(line)
                    require(bool(match), f"preflight resource grammar {run}/{name}")
                    trace_totals["resource"] += 1
                    if match[7] == "1": resources.append(match)
                elif line.startswith("ALLOWLIST_DUMP "):
                    match = DUMP_RE.fullmatch(line)
                    require(bool(match), f"preflight dump grammar {run}/{name}")
                    trace_totals["dump"] += 1
                    dumps.append(match)
                elif line.startswith("SNAPSHOT_ERROR "):
                    raise AssertionError(f"preflight snapshot error {run}/{name}")
                else:
                    raise AssertionError(
                        f"preflight unknown trace record {run}/{name}: {line!r}")
            require(len(resources) == len(dumps) == 2,
                    f"preflight trace counts {run}/{name}")
            resource_vas: set[int] = set()
            for match in resources:
                va = int(match[2], 0)
                stems = [stem for stem, spec in ALLOWED.items() if spec[0] == va]
                require(len(stems) == 1 and va not in resource_vas,
                        f"preflight resource VA {run}/{name}")
                stem = stems[0]
                _, size, _ = ALLOWED[stem]
                require(int(match[3], 0) == size and
                        match[4] == metadata[stem]["mapping_handle"] and
                        (match[5], match[6]) in {("1", "0"), ("0", "1"), ("1", "1")},
                        f"preflight resource linkage {run}/{name}/{stem}")
                resource_vas.add(va)
            dump_vas: set[int] = set()
            for match in dumps:
                va = int(match[1], 0)
                stems = [stem for stem, spec in ALLOWED.items() if spec[0] == va]
                require(len(stems) == 1 and va not in dump_vas,
                        f"preflight dump VA {run}/{name}")
                stem = stems[0]
                _, size, role = ALLOWED[stem]
                require(int(match[2], 0) == int(match[3], 0) ==
                        int(match[4], 0) == int(match[8], 0) == size and
                        match[5] == role and match[6] == metadata[stem]["mapping_handle"] and
                        match[7] == "1" and int(match[9], 16) == 0 and
                        (match[10], match[11]) == ("1", "1"),
                        f"preflight dump linkage {run}/{name}/{stem}")
                dump_vas.add(va)
            require(resource_vas == dump_vas == {0x58000, 0x68000},
                    f"preflight trace VA set {run}/{name}")
    require(trace_totals == {"header": 76, "service": 152, "call": 3799,
                             "resource": 3038, "dump": 152},
            f"global trace grammar/counts {trace_totals}")
    return allowed_paths


def expected_artifacts() -> set[str]:
    result = set(STATIC_ARTIFACTS)
    for run in RUNS:
        base = f"raw/{run}"
        result |= {f"{base}/{name}" for name in RUN_TOP if name != "trials"}
        for _, _, _, name in TRIALS:
            trial = f"{base}/trials/{name}"
            result |= {f"{trial}/run.json", f"{trial}/trace.log"}
            result |= {f"{trial}/state/{state}" for state in STATE_NAMES}
    return result


def verify_inventory(root: Path) -> None:
    listed: dict[str, str] = {}
    for line in (root / "SHA256SUMS").read_text().splitlines():
        match = SHA_LINE.fullmatch(line)
        require(bool(match), f"inventory grammar {root}: {line!r}")
        want, rel = match.groups()
        posix = PurePosixPath(rel)
        require(rel not in listed and not posix.is_absolute() and ".." not in posix.parts,
                f"inventory path {root}/{rel}")
        path = root / Path(*posix.parts)
        require(path.is_file() and not path.is_symlink() and digest(path) == want,
                f"inventory file/hash {path}")
        listed[rel] = want
    expected = {str(Path(rel).relative_to(root.relative_to(HERE)))
                for rel in expected_artifacts() if rel.startswith(str(root.relative_to(HERE)) + "/")}
    expected.remove("SHA256SUMS")
    require(set(listed) == expected, f"inventory exact coverage {root}")


def main() -> int:
    # No payload byte or payload hash occurs before this exact metadata/path gate.
    allowed_payload_paths = metadata_preflight()
    require(len(allowed_payload_paths) == 304, "global allowed payload path count")

    require(digest(HERE / "PRE_REGISTRATION.md") == PRE_HASH, "prereg hash")
    prereg_path = "experiments/EXP-0055-m4-scissor-depth-bias-state/PRE_REGISTRATION.md"
    blob = subprocess.run(["git", "-C", REPO, "show", f"{PRE_COMMIT}:{prereg_path}"],
                          capture_output=True, timeout=15)
    require(blob.returncode == 0 and hashlib.sha256(blob.stdout).hexdigest() == PRE_HASH,
            "committed prereg blob")
    changed = subprocess.run(["git", "-C", REPO, "diff-tree", "--no-commit-id",
                              "--name-only", "-r", PRE_COMMIT], capture_output=True,
                             text=True, timeout=15)
    require(changed.returncode == 0 and changed.stdout.splitlines() == [prereg_path],
            "prereg-only commit")
    ancestry = subprocess.run(["git", "-C", REPO, "merge-base", "--is-ancestor",
                               PRE_COMMIT, "HEAD"], timeout=15)
    require(ancestry.returncode == 0, "prereg ancestor")

    prior_parent = subprocess.run(["git", "-C", REPO, "rev-parse", f"{PRIOR_COMMIT}^"],
                                  check=True, capture_output=True, text=True,
                                  timeout=15).stdout.strip()
    require(prior_parent == PRIOR_PARENT, "prior commit parent")
    prior_manifest_path = REPO / "experiments/EXP-0048-bg-eot-pbe/manifest.json"
    require(digest(prior_manifest_path) == PRIOR_MANIFEST_HASH, "prior manifest worktree")
    prior_blob = subprocess.run(["git", "-C", REPO, "show",
        f"{PRIOR_COMMIT}:experiments/EXP-0048-bg-eot-pbe/manifest.json"],
        capture_output=True, timeout=15)
    require(prior_blob.returncode == 0 and
            hashlib.sha256(prior_blob.stdout).hexdigest() == PRIOR_MANIFEST_HASH,
            "prior committed manifest")
    prior_meta = {
        "va_58000.meta": "f582146de68fa08599d3b6a7678b279f813a425c7ab3125f3c57e845d9211a64",
        "va_68000.meta": "b4f99584fd9fe87211bdff651004bf6c2e6b7860280592aec4160ccfe9552f7c",
    }
    for run in ("m4_20260817_run01", "m4_20260817_run02"):
        for name, want in prior_meta.items():
            rel = f"experiments/EXP-0048-bg-eot-pbe/raw/{run}/state_rgba8-clear-store-draw/{name}"
            path = REPO / rel
            committed = subprocess.run(["git", "-C", REPO, "show",
                                        f"{PRIOR_COMMIT}:{rel}"],
                                       capture_output=True, timeout=15)
            require(digest(path) == want and committed.returncode == 0 and
                    hashlib.sha256(committed.stdout).hexdigest() == want,
                    f"prior metadata anchor {run}/{name}")

    for rel, want in SOURCE_HASHES.items():
        if rel.endswith("/run.py"):
            actual = hashlib.sha256(captured_runner_bytes()).hexdigest()
        else:
            actual = digest(REPO / rel)
        require(actual == want, f"captured authored source hash {rel}")
    for rel, want in PUBLIC_HEADERS.items():
        require(digest(Path(rel)) == want, f"public header hash {rel}")

    product_hashes = {
        "m4_20260817_run01": {
            "allowtrace.dylib": "acb02c642a75ce7033a1db44075c8024c51e4f878dbe358b7c75625926a28417",
            "probe": "06ee3bf165f6974bf81c18e985c6657e3e5ae45178f7cfd84542269f36e059b2"},
        "m4_20260817_run02": {
            "allowtrace.dylib": "9d827fa802157fbf93f51b53c2ca55fd408eab8d7392de62da94758326565931",
            "probe": "06ee3bf165f6974bf81c18e985c6657e3e5ae45178f7cfd84542269f36e059b2"},
    }
    stdout_hashes: dict[str, dict[str, str]] = {}
    for run in RUNS:
        root = HERE / "raw" / run
        require(digest(root / "SHA256SUMS") == RAW_INVENTORY_HASHES[run],
                f"self-binding raw inventory {run}")
        verify_inventory(root)
        require((root / "failures.jsonl").read_bytes() == b"", f"failures {run}")
        inputs = load_json(root / "00_inputs.json")
        require(inputs == {
            "schema": 1,
            "pre_registration": {"commit": PRE_COMMIT, "sha256": PRE_HASH},
            "prior_evidence": {"experiment": "EXP-0048-bg-eot-pbe",
                "artifact_commit": PRIOR_COMMIT,
                "manifest_generation_revision": PRIOR_PARENT,
                "manifest_sha256": PRIOR_MANIFEST_HASH},
            "authored_sources": SOURCE_HASHES,
            "public_headers": PUBLIC_HEADERS,
            "schedules": SCHEDULES, "cases": CASES,
            "trials": [name for _, _, _, name in TRIALS],
        }, f"exact inputs {run}")
        environment = load_json(root / "01_environment.json")
        require(set(environment) == {"schema", "run_id", "started_utc",
                "repository_revision", "target", "tools", "clean_room"} and
                environment["schema"] == 1 and environment["run_id"] == run and
                environment["repository_revision"] == PRE_COMMIT and
                environment["target"] == {"cpu_brand": "Apple M4", "machine": "arm64",
                    "model": "Mac16,10", "sw_vers": "ProductName:\t\tmacOS\nProductVersion:\t\t26.6.2\nBuildVersion:\t\t25G82"} and
                environment["tools"] == {"clang": "Apple clang version 21.0.0 (clang-2100.1.1.101)",
                    "python": "3.14.6",
                    "xcrun_path": "/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang"} and
                environment["clean_room"] == {"allowed_state_vas": ["0x58000", "0x68000"],
                    "apple_auxiliary_code_inspection": "NONE", "apple_binary_introspection": "NONE",
                    "categories": ["HW-PROBE", "DATA-TRACE", "OWN-SHADER"],
                    "command_bo_contents_inspected": "NONE", "compiled_shader_bytes_inspected": "NONE",
                    "generic_bo_scan": "NONE", "mutation_splice_replay": "NONE",
                    "pointer_following": "NONE", "target_qualification": "local M4 only; no A18 Pro validation",
                    "unknown_bo_contents_inspected": "NONE"},
                f"exact environment {run}")
        builds = {
            "allowtrace.dylib": load_json(root / "02_build_allowtrace.json"),
            "probe": load_json(root / "03_build_probe.json"),
        }
        for name, build in builds.items():
            require(set(build) == {"argv", "exit", "product", "started_utc", "stderr", "stdout", "timeout_seconds"} and
                    build["exit"] == 0 and build["timeout_seconds"] == 60 and
                    build["stdout"] == build["stderr"] == "" and
                    build["product"] == {"bytes": 68512 if name == "allowtrace.dylib" else 72136,
                        "retained": False, "semantic_inspection": "NONE",
                        "sha256": product_hashes[run][name]},
                    f"exact build {run}/{name}")
        tracer_path = builds["allowtrace.dylib"]["argv"][6]
        probe_path = builds["probe"]["argv"][6]
        require(builds["allowtrace.dylib"]["argv"] == ["xcrun", "clang", "-arch", "arm64e",
                "-dynamiclib", "-o", tracer_path, str(CAPTURE_HERE / "harness/allowtrace.c"),
                "-framework", "IOKit", "-framework", "CoreFoundation"], f"tracer argv {run}")
        require(builds["probe"]["argv"] == ["xcrun", "clang", "-arch", "arm64e",
                "-fobjc-arc", "-o", probe_path, str(CAPTURE_HERE / "harness/probe.m"),
                "-framework", "Metal", "-framework", "Foundation"], f"probe argv {run}")
        stdout_hashes[run] = {}
        for _, schedule, case, name in TRIALS:
            trial = root / "trials" / name
            captured_trial = CAPTURE_HERE / "raw" / run / "trials" / name
            record = load_json(trial / "run.json")
            require(set(record) == {"argv", "environment_overrides", "exit",
                    "started_utc", "stderr", "stdout", "timeout_seconds"} and
                    record["argv"] == [probe_path, "--case", case, "--schedule", schedule, "--dump"] and
                    record["environment_overrides"] == {"DYLD_INSERT_LIBRARIES": tracer_path,
                        "ALLOWTRACE_LOG": str(captured_trial / "trace.log"),
                        "ALLOWTRACE_DUMP_DIR": str(captured_trial / "state")} and
                    record["exit"] == 0 and record["timeout_seconds"] == 45 and
                    record["stderr"] == "" and len(record["stdout"].splitlines()) == 6,
                    f"exact trial record {run}/{name}")
            stdout_hashes[run][name] = hashlib.sha256(record["stdout"].encode()).hexdigest()
        boundary = load_json(root / "04_boundary_preflight.json")
        require(boundary["schema"] == 1 and boundary["preflight_before_payload_access"] is True and
                boundary["trial_count"] == 38 and boundary["payload_pairs"] == 76 and
                boundary["fixed_state_role_anchors"] == [
                    {"trial": "001_plain_scissor-base", "offset_0x14": 25,
                     "offset_0x53": 0, "expected": {"offset_0x14": 25, "offset_0x53": 0}},
                    {"trial": "020_pad64k_scissor-base", "offset_0x14": 25,
                     "offset_0x53": 0, "expected": {"offset_0x14": 25, "offset_0x53": 0}},
                ] and boundary["trials"] == [
                    {"trial": name, "case": case, "schedule": schedule, "payload_pairs": 2}
                    for _, schedule, case, name in TRIALS], f"boundary record {run}")
    require(stdout_hashes[RUNS[0]] == stdout_hashes[RUNS[1]], "stdout exact repetition")

    for rel, want in ANALYSIS_HASHES.items():
        require(digest(HERE / rel) == want, f"self-binding analysis {rel}")
    invocation = load_json(HERE / "analysis/invocation.json")
    captured_analysis_argv = [str(CAPTURE_HERE / "analysis/analyze.py"), "--json",
        str(CAPTURE_HERE / "analysis/summary.json"), "--report",
        str(CAPTURE_HERE / "analysis/report.txt")]
    current_analysis_argv = [str(HERE / "analysis/analyze.py"), "--json",
        str(HERE / "analysis/summary.json"), "--report",
        str(HERE / "analysis/report.txt")]
    require(set(invocation) == {"argv", "exit", "started_utc", "stderr", "stdout", "timeout_seconds"} and
            invocation["exit"] == 0 and invocation["timeout_seconds"] == 60 and
            invocation["stderr"] == "" and
            invocation["stdout"] == "PASS runs=2 processes=76 payload_pairs=152 comparisons=16\n" and
            invocation["argv"][1:] in (captured_analysis_argv, current_analysis_argv),
            "analysis invocation")
    with tempfile.TemporaryDirectory(prefix="exp0055-verify-") as temporary:
        temp = Path(temporary)
        generated_json = temp / "summary.json"
        generated_report = temp / "report.txt"
        cp = subprocess.run([sys.executable, HERE / "analysis/analyze.py", "--json", generated_json,
                             "--report", generated_report], capture_output=True, text=True,
                            timeout=60, env={"PYTHONDONTWRITEBYTECODE": "1"})
        require(cp.returncode == 0 and cp.stderr == "" and
                generated_json.read_bytes() == (HERE / "analysis/summary.json").read_bytes() and
                generated_report.read_bytes() == (HERE / "analysis/report.txt").read_bytes(),
                f"analysis regeneration: {cp.stderr}")
        generated_manifest = temp / "manifest.json"
        mp = subprocess.run([sys.executable, HERE / "make_manifest.py", "--output", generated_manifest],
                            capture_output=True, text=True, timeout=60,
                            env={"PYTHONDONTWRITEBYTECODE": "1"})
        require(mp.returncode == 0 and mp.stderr == "" and
                generated_manifest.read_bytes() == (HERE / "manifest.json").read_bytes(),
                f"manifest regeneration: {mp.stderr}")

    expected = expected_artifacts()
    top_expected = {"PRE_REGISTRATION.md", "README.md", "RESULTS.md", "harness", "run.py",
                    "analysis", "make_manifest.py", "verify.py", "raw", "manifest.json"}
    require({path.name for path in HERE.iterdir()} == top_expected, "exact experiment top-level entries")
    require({path.name for path in (HERE / "harness").iterdir()} == {"allowtrace.c", "probe.m"},
            "exact harness entries")
    require({path.name for path in (HERE / "analysis").iterdir()} == {"analyze.py", "run_analysis.py",
            "failures.md", "invocation.json", "report.txt", "summary.json"}, "exact analysis entries")
    actual = {str(path.relative_to(HERE)): path for path in HERE.rglob("*")
              if path.is_file() and path.name != "manifest.json"}
    require(set(actual) == expected,
            f"exact committable allowlist missing={sorted(expected-set(actual))} extra={sorted(set(actual)-expected)}")
    for path in HERE.rglob("*"):
        require(not path.is_symlink() and (path.is_file() or path.is_dir()),
                f"symlink/special forbidden {path}")
        require(path.suffix not in FORBIDDEN_SUFFIXES, f"forbidden binary artifact {path}")

    manifest = load_json(HERE / "manifest.json")
    listed = {item["path"]: item for item in manifest["artifacts"]}
    require(len(listed) == len(manifest["artifacts"]) and set(listed) == expected,
            "manifest exact unique coverage")
    for rel, path in actual.items():
        item = listed[rel]
        require(set(item) == {"path", "bytes", "sha256"} and
                item["bytes"] == path.stat().st_size and item["sha256"] == digest(path),
                f"manifest artifact {rel}")
    repository = manifest.get("repository", {})
    declared_base = repository.get("base_revision_at_manifest")
    require(isinstance(declared_base, str) and
            re.fullmatch(r"[0-9a-f]{40}", declared_base) is not None,
            "manifest base syntax")
    require(manifest["schema"] == 1 and
            manifest["experiment"] == "EXP-0055-m4-scissor-depth-bias-state" and
            manifest["target"] == {"model": "Mac16,10", "soc": "Apple M4",
                "gpu": "Apple M4 / G16G-class",
                "qualification": "local M4 DATA-TRACE only; A18 Pro untested"} and
            repository == {"base_revision_at_manifest": declared_base,
                "base_must_be_ancestor_of_head": True,
                "authoritative_process": "CODEX.md", "gap": "AGX_RE_INFORMATION_GAPS.md P0.3"} and
            manifest["pre_registration"] == {"path": "PRE_REGISTRATION.md",
                "commit": PRE_COMMIT, "sha256": PRE_HASH,
                "committed_alone_before_build": True},
            "manifest identity/history")
    base_check = subprocess.run(["git", "-C", REPO, "merge-base", "--is-ancestor",
                                 declared_base, "HEAD"],
                                timeout=15)
    require(base_check.returncode == 0, "manifest base ancestor")
    require(manifest["prior_evidence"] == {"experiment": "EXP-0048-bg-eot-pbe",
            "artifact_commit": PRIOR_COMMIT, "manifest_generation_revision": PRIOR_PARENT,
            "manifest": {"path": "experiments/EXP-0048-bg-eot-pbe/manifest.json",
                         "sha256": PRIOR_MANIFEST_HASH},
            "allowlist": [
                {"gpu_va": "0x58000", "role": "fixed-function-render-state",
                 "allocation_size": "0x8000", "cap": "0x10000"},
                {"gpu_va": "0x68000", "role": "tiling-state",
                 "allocation_size": "0x88e0", "cap": "0x10000"}]},
            "manifest prior evidence")
    require(manifest["provenance"] == {"categories": ["HW-PROBE", "DATA-TRACE", "OWN-SHADER"],
            "apple_binary_introspection": "NONE",
            "apple_auxiliary_or_helper_program_bytes_inspected": "NONE",
            "compiled_shader_bytes_inspected": "NONE", "command_bo_contents_inspected": "NONE",
            "unknown_bo_contents_inspected": "NONE", "pointer_following": "NONE",
            "generic_bo_or_memory_scan": "NONE", "command_memory_mutation_splice_replay": "NONE",
            "state_bo_allowlist": [
                {"gpu_va": "0x58000", "role": "fixed-function-render-state",
                 "expected_read": "0x8000", "cap": "0x10000"},
                {"gpu_va": "0x68000", "role": "tiling-state",
                 "expected_read": "0x88e0", "cap": "0x10000"}]},
            "manifest provenance")
    require(manifest["runs"] == {"canonical": [f"raw/{run}" for run in RUNS],
            "top_level_runs": 2, "fresh_gpu_processes": 76,
            "successful_gpu_processes": 76, "gpu_errors": 0, "timeouts": 0,
            "guard_errors": 0, "allowed_payload_pairs": 152,
            "metadata_preflight_before_payload_access": True} and
            manifest["build_products"] == {"retention": "temporary rebuildable authored products; not committed",
                "identity": "exact size/SHA-256 recorded before execution in each build record",
                "semantic_inspection": "NONE"} and
            manifest["interpretation"] == {"evidence_level": "DATA-TRACE-VALIDATED for qualified bounded correlations",
                "p0_3": "OPEN", "hardware_consumption": "NOT ESTABLISHED",
                "linux_uapi_mapping": "UNKNOWN", "a18_pro": "UNTESTED"},
            "manifest conclusions")

    readme = (HERE / "README.md").read_text()
    results = (HERE / "RESULTS.md").read_text()
    for text, name in ((readme, "README"), (results, "RESULTS")):
        for phrase in ("Apple binary introspection: NONE",
                       "Compiled shader bytes inspected: NONE",
                       "Unknown BO contents inspected: NONE",
                       "Pointer following: NONE", "Mutation/splice/replay: NONE"):
            require(phrase in text, f"clean-room wording {name}/{phrase}")
        require("P0.3 remains OPEN" in text and "A18 Pro" in text,
                f"scope wording {name}")
    require("nonzero-depth-bias enable candidate" in results and
            "not a complete field encoding" in results and
            "not evidence that the private arrays or values do not exist elsewhere" in results,
            "bounded result wording")

    summary = load_json(HERE / "analysis/summary.json")
    require(summary["processes"] == 76 and summary["payload_pairs"] == 152 and
            summary["exact_stdout_repetition"] is True and
            summary["exact_payload_repetition"] is True and
            summary["depth_bias_nonzero_enable_candidate"] == {
                "qualified": True, "gpu_va": "0x58000", "offset": "0x36",
                "before": "0x00", "after": "0x02",
                "factors": ["dbias-constant-negative", "dbias-constant-positive",
                    "dbias-slope-negative", "dbias-slope-positive",
                    "dbias-large-negative", "dbias-large-positive"],
                "qualification": "nonzero public constant/slope correlation only; no value, mode, or hardware-consumption claim"} and
            summary["bounded_identical_state_despite_changed_behavior"] == [
                "scissor-x", "scissor-y", "scissor-width", "scissor-height",
                "scissor-empty-width", "scissor-empty-height", "multi-slot0-x",
                "multi-slot1-x", "dbias-clamp-negative", "dbias-clamp-positive"] and
            summary["interpretation"]["p0_3"] == "OPEN" and
            summary["scope"]["a18_claim"] == "NONE",
            "derived claims")

    print(f"PASS prereg=1 runs=2 processes=76 payload_pairs=152 artifacts={len(expected)} analysis=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
