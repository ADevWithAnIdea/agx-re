#!/usr/bin/env python3
"""Strict read-only verifier for frozen EXP-0054 evidence."""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path, PurePosixPath


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RUNS = {
    "m4_20260817_run01": "initial",
    "m4_20260817_run02": "initial",
    "m4_20260817_run03": "final",
    "m4_20260817_run04": "final",
}
PRE_HASH = "7bff360264354961cd0d22f043e65a0d800f4d23efd1b8c516e9ee564cad8953"
AMEND_HASH = "c8ccd2144a0423a9a48fd3f7754228e4665f931996cbeb1a5406114782379517"
FOLLOWUP_HASH = "11b52fec26751be0752340786b98573ba16e50fcfef9741531f176ec7e7c640d"
PRE_COMMIT = "13d200c5aeae67182b4555c51eb728a413a954aa"
AMEND_COMMIT = "7a7fde9c53a7765accb62c5896a3e8c404b4e0d8"
FOLLOWUP_COMMIT = "4c43187a807e8323fc6227471795f2d868d578de"
INITIAL_REVISION = AMEND_COMMIT
FINAL_REVISION = FOLLOWUP_COMMIT
INITIAL_STDOUT_SHA = "25c7f5e3448f0fcef7f41f74ede8c1135288a9f5d7b2448e06f06a6a57545b2e"
FINAL_STDOUT_SHA = "1ce116d62d370b68c8cdb9f1b9b7ca144d1240d90c07f1a1bddbfc77508cb918"
BUILD_STDERR_SHA = "0a6e786f7d530ccd2da734fedaebbc45c7cb58ed306df42a6c1d70b74da191e4"
INITIAL_HARNESS_SHA = "c8bbbf188009884b70e099a26453802b7104b2841edd6b7c641c453f125e8101"
FINAL_HARNESS_SHA = "898352c0b82b5bb5055e6907b890ba5047c1ec87751ca6a5e4fb935fb31a5b78"
INITIAL_RUNNER_SHA = "5757f632e6be65c0276a667093d69f8923e0bfd4a0149c3a3554e4b1b6e3acd2"
FINAL_RUNNER_SHA = "4717f025f284bc7ae5c41e03d18c51336e3b0c6875c66c424239163409e313c6"
HEADER_HASHES = {
    "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks/Metal.framework/Headers/MTL4RenderCommandEncoder.h":
        "0eed1f3675fd016f14fa628f3d4dfbbfaf317d59f028976a3526905001798d57",
    "/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks/Metal.framework/Headers/MTLRenderCommandEncoder.h":
        "8fbac9b5ab95dcb000a189d165176ac027284c6686633e711098ee45b8d930db",
}
CAPTURE_HARNESS = "/Users/user/asahi_re/public/agx-re/experiments/EXP-0054-m4-scissor-depth-bias/harness/probe.m"
EXECUTABLES = {
    "m4_20260817_run01":"/var/folders/yp/4sxsx2dn78nbdnfcq2_2cxzr0000gn/T/exp0054-mg5y0c5i/probe",
    "m4_20260817_run02":"/var/folders/yp/4sxsx2dn78nbdnfcq2_2cxzr0000gn/T/exp0054-_wxl5580/probe",
    "m4_20260817_run03":"/var/folders/yp/4sxsx2dn78nbdnfcq2_2cxzr0000gn/T/exp0054-m1d1rdyp/probe",
    "m4_20260817_run04":"/var/folders/yp/4sxsx2dn78nbdnfcq2_2cxzr0000gn/T/exp0054-da0q8ces/probe",
}
RAW_FILES = {"SHA256SUMS","environment.json","build.json","run.json","failures.json"}
STATIC_FILES = {"PRE_REGISTRATION.md","PRE_REGISTRATION_AMENDMENT.md",
    "PRE_REGISTRATION_FOLLOWUP.md","README.md","RESULTS.md","harness/probe.m",
    "run.py","make_manifest.py","verify.py","analysis/analyze.py",
    "analysis/summary.json","analysis/report.txt"}
EXPECTED_DIRS = {"analysis","harness","raw"} | {f"raw/{run_id}" for run_id in RUNS}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(path: Path) -> str:
    return digest_bytes(path.read_bytes())


def strict_json(path: Path) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key {path}:{key}")
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


def iso(value: object, label: str) -> datetime.datetime:
    require(isinstance(value, str), f"{label}: timestamp type")
    try: parsed = datetime.datetime.fromisoformat(value)
    except ValueError: require(False, f"{label}: timestamp syntax")
    require(parsed.tzinfo is not None, f"{label}: timezone")
    return parsed


def inventory(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        parts = line.split("  ")
        require(len(parts) == 2 and len(parts[0]) == 64, f"{path}:{number}: inventory syntax")
        want, relative = parts; pure = PurePosixPath(relative)
        require(not pure.is_absolute() and ".." not in pure.parts and relative not in result,
                f"{path}:{number}: unsafe/duplicate path")
        try: int(want, 16)
        except ValueError: require(False, f"{path}:{number}: nonhex hash")
        result[relative] = want
    return result


def verify_filesystem_shape() -> None:
    entries = list(HERE.rglob("*"))
    for path in entries:
        require(not path.is_symlink(), f"symlink forbidden {path.relative_to(HERE)}")
        require(path.is_file() or path.is_dir(), f"special entry forbidden {path.relative_to(HERE)}")
    directories = {path.relative_to(HERE).as_posix() for path in entries if path.is_dir()}
    require(directories == EXPECTED_DIRS,
            f"exact directory set missing={sorted(EXPECTED_DIRS-directories)} extra={sorted(directories-EXPECTED_DIRS)}")


def source_versions() -> dict[str, tuple[str, str]]:
    harness = (HERE / "harness/probe.m").read_text()
    require(harness.count("100000.0f") == 4 and harness.count("100.0f") == 0,
            "final harness follow-up edit shape")
    initial_harness = harness.replace("100000.0f", "100.0f")
    require(digest_bytes(initial_harness.encode()) == INITIAL_HARNESS_SHA and
            digest_bytes(harness.encode()) == FINAL_HARNESS_SHA, "harness version reconstruction")

    runner = (HERE / "run.py").read_text(); initial_runner = runner
    removable = [
        'FOLLOWUP = HERE / "PRE_REGISTRATION_FOLLOWUP.md"\n',
        'FOLLOWUP_HASH = "11b52fec26751be0752340786b98573ba16e50fcfef9741531f176ec7e7c640d"\n',
        'FOLLOWUP_COMMIT = "4c43187a"\n',
        '        "pre_run_followup": {"commit": FOLLOWUP_COMMIT, "sha256": FOLLOWUP_HASH},\n',
        '            str(FOLLOWUP.relative_to(REPO)): digest(FOLLOWUP),\n',
    ]
    for value in removable:
        require(initial_runner.count(value) == 1, "initial runner reconstruction token")
        initial_runner = initial_runner.replace(value, "")
    new_guard = '''    if (digest(PRE) != PRE_HASH or digest(AMEND) != AMEND_HASH or
            digest(FOLLOWUP) != FOLLOWUP_HASH):
'''
    old_guard = '''    if digest(PRE) != PRE_HASH or digest(AMEND) != AMEND_HASH:
'''
    require(initial_runner.count(new_guard) == 1, "initial runner guard reconstruction")
    initial_runner = initial_runner.replace(new_guard, old_guard)
    require(digest_bytes(initial_runner.encode()) == INITIAL_RUNNER_SHA and
            digest_bytes(runner.encode()) == FINAL_RUNNER_SHA, "runner version reconstruction")
    return {"initial":(INITIAL_HARNESS_SHA,INITIAL_RUNNER_SHA),
            "final":(FINAL_HARNESS_SHA,FINAL_RUNNER_SHA)}


def git_bytes(revision: str, relative: str) -> bytes:
    cp = subprocess.run(["git","-C",str(REPO),"show",f"{revision}:{relative}"],
                        capture_output=True,timeout=15)
    require(cp.returncode == 0, f"git object {revision}:{relative}")
    return cp.stdout


def ancestor(older: str, newer: str, label: str) -> None:
    cp = subprocess.run(["git","-C",str(REPO),"merge-base","--is-ancestor",older,newer],
                        capture_output=True,text=True,timeout=15)
    require(cp.returncode == 0, label)


def verify_git_anchors() -> None:
    paths = {
        PRE_COMMIT:("experiments/EXP-0054-m4-scissor-depth-bias/PRE_REGISTRATION.md",PRE_HASH),
        AMEND_COMMIT:("experiments/EXP-0054-m4-scissor-depth-bias/PRE_REGISTRATION_AMENDMENT.md",AMEND_HASH),
        FOLLOWUP_COMMIT:("experiments/EXP-0054-m4-scissor-depth-bias/PRE_REGISTRATION_FOLLOWUP.md",FOLLOWUP_HASH),
    }
    for revision, (relative, want) in paths.items():
        require(digest_bytes(git_bytes(revision, relative)) == want, f"committed prereg blob {relative}")
        ancestor(revision, "HEAD", f"{relative} commit is not ancestor of HEAD")
    ancestor(PRE_COMMIT, AMEND_COMMIT, "initial prereg/amend order")
    ancestor(AMEND_COMMIT, INITIAL_REVISION, "amend not before initial runs")
    ancestor(AMEND_COMMIT, FOLLOWUP_COMMIT, "follow-up history order")
    ancestor(FOLLOWUP_COMMIT, FINAL_REVISION, "follow-up not before final runs")
    not_before = subprocess.run(["git","-C",str(REPO),"merge-base","--is-ancestor",
                                 FOLLOWUP_COMMIT,INITIAL_REVISION],capture_output=True,timeout=15)
    require(not_before.returncode != 0, "follow-up unexpectedly predates initial run revision")


def verify_runs() -> None:
    raw = HERE / "raw"
    require({path.name for path in raw.iterdir() if path.is_dir()} == set(RUNS), "raw run set")
    versions = source_versions()
    for run_id, generation in RUNS.items():
        directory = raw / run_id
        entries = list(directory.rglob("*"))
        require(directory.is_dir() and not directory.is_symlink() and
                all(path.is_file() and not path.is_symlink() and path.parent == directory for path in entries),
                f"{run_id}: nested/special raw entry")
        require({path.name for path in entries} == RAW_FILES, f"{run_id}: exact raw files")
        sums = inventory(directory / "SHA256SUMS")
        require(set(sums) == RAW_FILES - {"SHA256SUMS"}, f"{run_id}: inventory coverage")
        for relative, want in sums.items():
            require(digest(directory / relative) == want, f"{run_id}/{relative}: inventory hash")

        env = strict_json(directory / "environment.json"); require(isinstance(env, dict), f"{run_id}: env type")
        base_keys = {"captured_at_utc","run_id","repo_revision","pre_registration","pre_run_amendment",
            "target","tools","authored_sources","public_headers","apple_binary_introspection",
            "apple_auxiliary_code_inspection","compiled_shader_bytes_inspected",
            "command_or_state_bo_payload_tracing","pointer_following","generic_memory_scan",
            "mutation_splice_replay"}
        if generation == "final": base_keys.add("pre_run_followup")
        require(set(env) == base_keys and env["run_id"] == run_id, f"{run_id}: environment keys/id")
        iso(env["captured_at_utc"], f"{run_id}: capture time")
        revision = INITIAL_REVISION if generation == "initial" else FINAL_REVISION
        require(env["repo_revision"] == revision, f"{run_id}: revision")
        require(env["pre_registration"] == {"commit":PRE_COMMIT,"sha256":PRE_HASH} and
                env["pre_run_amendment"] == {"commit":"7a7fde9c","sha256":AMEND_HASH},
                f"{run_id}: prereg records")
        if generation == "final":
            require(env["pre_run_followup"] == {"commit":"4c43187a","sha256":FOLLOWUP_HASH},
                    f"{run_id}: follow-up record")
        require(env["target"] == {"cpu_brand":"Apple M4","machine":"arm64","model":"Mac16,10",
            "sw_vers":"ProductName:\t\tmacOS\nProductVersion:\t\t26.6.2\nBuildVersion:\t\t25G82"},
            f"{run_id}: target")
        require(env["tools"] == {"clang":"Apple clang version 21.0.0 (clang-2100.1.1.101)",
                                  "python":"3.14.6"}, f"{run_id}: tools")
        require(env["public_headers"] == HEADER_HASHES, f"{run_id}: public header hashes")
        harness_sha, runner_sha = versions[generation]
        sources = {
            "experiments/EXP-0054-m4-scissor-depth-bias/PRE_REGISTRATION.md":PRE_HASH,
            "experiments/EXP-0054-m4-scissor-depth-bias/PRE_REGISTRATION_AMENDMENT.md":AMEND_HASH,
            "experiments/EXP-0054-m4-scissor-depth-bias/harness/probe.m":harness_sha,
            "experiments/EXP-0054-m4-scissor-depth-bias/run.py":runner_sha,
        }
        if generation == "final":
            sources["experiments/EXP-0054-m4-scissor-depth-bias/PRE_REGISTRATION_FOLLOWUP.md"] = FOLLOWUP_HASH
        require(env["authored_sources"] == sources, f"{run_id}: exact source binding")
        require({key:env[key] for key in ("apple_binary_introspection","apple_auxiliary_code_inspection",
            "compiled_shader_bytes_inspected","command_or_state_bo_payload_tracing","pointer_following",
            "generic_memory_scan","mutation_splice_replay")} == {
            "apple_binary_introspection":"NONE","apple_auxiliary_code_inspection":"NONE",
            "compiled_shader_bytes_inspected":"NONE","command_or_state_bo_payload_tracing":"NONE",
            "pointer_following":"NONE","generic_memory_scan":"NONE","mutation_splice_replay":"NONE"},
            f"{run_id}: clean-room fields")

        build = strict_json(directory / "build.json"); require(isinstance(build, dict), f"{run_id}: build type")
        require(set(build) == {"argv","timeout_seconds","started_utc","exit","stdout","stderr"},
                f"{run_id}: build keys")
        require(build["argv"] == ["clang","-fobjc-arc","-framework","Metal","-framework","Foundation",
            "-o",EXECUTABLES[run_id],CAPTURE_HARNESS], f"{run_id}: exact historical build argv")
        require(build["timeout_seconds"] == 60 and build["exit"] == 0 and build["stdout"] == "" and
                digest_bytes(build["stderr"].encode()) == BUILD_STDERR_SHA, f"{run_id}: build result")
        build_time = iso(build["started_utc"], f"{run_id}: build time")

        run = strict_json(directory / "run.json"); require(isinstance(run, dict), f"{run_id}: run type")
        require(set(run) == {"argv","timeout_seconds","started_utc","exit","stdout","stderr"},
                f"{run_id}: run keys")
        stdout_sha = INITIAL_STDOUT_SHA if generation == "initial" else FINAL_STDOUT_SHA
        require(run["argv"] == [EXECUTABLES[run_id]] and run["timeout_seconds"] == 120 and
                run["exit"] == 0 and run["stderr"] == "" and
                digest_bytes(run["stdout"].encode()) == stdout_sha, f"{run_id}: exact run transcript")
        require(iso(run["started_utc"], f"{run_id}: run time") >= build_time, f"{run_id}: phase order")
        require(strict_json(directory / "failures.json") == [], f"{run_id}: failures")


def verify_analysis() -> None:
    with tempfile.TemporaryDirectory(prefix="exp0054-verify-") as temporary:
        cp = subprocess.run(["python3",str(HERE / "analysis/analyze.py"),"--output-dir",temporary],
                            capture_output=True,text=True,timeout=20)
        require(cp.returncode == 0, f"analysis execution: {cp.stderr}")
        for name in ("summary.json","report.txt"):
            require((Path(temporary)/name).read_bytes() == (HERE/"analysis"/name).read_bytes(),
                    f"stale analysis/{name}")
    summary = strict_json(HERE / "analysis/summary.json"); require(isinstance(summary, dict), "summary type")
    require(summary["canonical_runs"] == ["m4_20260817_run03","m4_20260817_run04"] and
            summary["preserved_initial_successes"] == ["m4_20260817_run01","m4_20260817_run02"],
            "analysis run classification")
    require(summary["hypotheses"] == {
        "H1":"SUPPORTED for tested exact half-open/empty single scissors",
        "H2":"SUPPORTED for tested two public viewport-indexed scissors and slot-1 perturbation",
        "H3":"SUPPORTED for tested constant/slope signs and flat slope-only controls",
        "H4":"FALSIFIED as preregistered: magnitude 100 did not engage the 0.001 clamp",
        "H5":"PUBLIC API ABSENCE ONLY; private/integer mode remains UNKNOWN",
        "H6":"SUPPORTED for tested sign-matched magnitude-100000/0.001 clamp pairs"},
        "analysis hypotheses")
    require(summary["scope"] == {"target":"Apple M4/G16G-class only","a18_pro":"UNTESTED",
        "p0_3":"OPEN","isp_scissor_base":"UNKNOWN","isp_dbias_base":"UNKNOWN",
        "integer_depth_bias":"UNKNOWN","linux_uapi_mapping":"NOT ESTABLISHED",
        "bo_payload_tracing":"NONE","apple_binary_introspection":"NONE",
        "compiled_shader_bytes_inspected":"NONE"}, "analysis scope")


def verify_manifest() -> None:
    manifest = strict_json(HERE / "manifest.json"); require(isinstance(manifest, dict), "manifest type")
    require(set(manifest) == {"schema","experiment","generated_at_utc","base_revision_at_manifest",
        "pre_registrations","run_revisions","canonical_runs","preserved_initial_successes",
        "source_versions","target","provenance","artifacts"}, "manifest keys")
    require(manifest["schema"] == 1 and manifest["experiment"] == "EXP-0054-m4-scissor-depth-bias",
            "manifest identity")
    iso(manifest["generated_at_utc"], "manifest time")
    manifest_base = manifest["base_revision_at_manifest"]
    require(isinstance(manifest_base,str) and re.fullmatch(r"[0-9a-f]{40}",manifest_base) is not None,
            "manifest base syntax")
    ancestor(manifest_base,"HEAD","manifest base is not ancestor of HEAD")
    require(manifest["pre_registrations"] == [
        {"commit":PRE_COMMIT,"path":"PRE_REGISTRATION.md","sha256":PRE_HASH},
        {"commit":AMEND_COMMIT,"path":"PRE_REGISTRATION_AMENDMENT.md","sha256":AMEND_HASH},
        {"commit":FOLLOWUP_COMMIT,"path":"PRE_REGISTRATION_FOLLOWUP.md","sha256":FOLLOWUP_HASH}],
        "manifest preregistrations")
    require(manifest["run_revisions"] == {"initial":INITIAL_REVISION,"final":FINAL_REVISION} and
            manifest["canonical_runs"] == ["m4_20260817_run03","m4_20260817_run04"] and
            manifest["preserved_initial_successes"] == ["m4_20260817_run01","m4_20260817_run02"],
            "manifest run classification")
    require(manifest["source_versions"] == {"initial":{"harness":INITIAL_HARNESS_SHA,"runner":INITIAL_RUNNER_SHA},
            "final":{"harness":FINAL_HARNESS_SHA,"runner":FINAL_RUNNER_SHA}}, "manifest source versions")
    require(manifest["target"] == {"qualification":"local M4/G16G-class only; A18 Pro untested",
            "model":"Mac16,10","os":"macOS 26.6.2 (25G82)"}, "manifest target")
    require(manifest["provenance"] == {"categories":["HW-PROBE","OWN-SHADER source","PUBLIC"],
        "apple_binary_introspection":"NONE","apple_auxiliary_code_inspection":"NONE",
        "compiled_shader_bytes_inspected":"NONE","command_or_state_bo_payload_tracing":"NONE",
        "pointer_following":"NONE","generic_memory_scan":"NONE","mutation_splice_replay":"NONE"},
        "manifest provenance")
    listed = {item["path"]:item for item in manifest["artifacts"]}
    require(len(listed) == len(manifest["artifacts"]), "duplicate manifest path")
    expected = set(STATIC_FILES)
    for run_id in RUNS: expected |= {f"raw/{run_id}/{name}" for name in RAW_FILES}
    actual = {path.relative_to(HERE).as_posix():path for path in HERE.rglob("*")
              if path.is_file() and path.name != "manifest.json"}
    require(set(actual) == expected and set(listed) == expected, "exact committable artifact coverage")
    forbidden = {".bin",".dylib",".metallib",".air",".o",".a",".so",".exe",".pyc"}
    for relative, path in actual.items():
        require(not path.is_symlink() and path.suffix.lower() not in forbidden and
                "__pycache__" not in path.parts, f"forbidden artifact {relative}")
        require(set(listed[relative]) == {"path","bytes","sha256"} and
                listed[relative]["bytes"] == path.stat().st_size and
                listed[relative]["sha256"] == digest(path), f"manifest hash {relative}")


def main() -> None:
    verify_filesystem_shape()
    require(digest(HERE/"PRE_REGISTRATION.md") == PRE_HASH and
            digest(HERE/"PRE_REGISTRATION_AMENDMENT.md") == AMEND_HASH and
            digest(HERE/"PRE_REGISTRATION_FOLLOWUP.md") == FOLLOWUP_HASH,
            "preregistration hashes")
    verify_git_anchors(); verify_runs(); verify_analysis(); verify_manifest()
    manifest = strict_json(HERE / "manifest.json")
    print(f"PASS prereg=3 runs=4 canonical=2 preserved_initial=2 cases=76 "
          f"analysis=PASS artifacts={len(manifest['artifacts'])}")


if __name__ == "__main__":
    main()
