#!/usr/bin/env python3
"""Verify frozen EXP-0053 evidence without executing Metal."""

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path, PurePosixPath


HERE = Path(__file__).resolve().parent
PRE_HASH = "4773ea2764b1fd3479ec2f52881ff7dcb2b1cfe0fa2e1f592db37b57db8bd34f"
BASE_REVISION = "3dea789d6001444b9d78e7f7bcc7602d690bc169"
RUNS = {"m4_20260817_run01":"build-failure","m4_20260817_run02":"gpu-failure",
        "m4_20260817_run03":"hash-only-success","m4_20260817_run04":"hash-only-success",
        "m4_20260817_run05":"success","m4_20260817_run06":"success"}
BASE_FILES = {"SHA256SUMS","environment.json","build.json","failures.json"}
SOURCE_PATH = "experiments/EXP-0053-m4-indirect-api-semantics/harness/probe.m"
RUNNER_PATH = "experiments/EXP-0053-m4-indirect-api-semantics/run.py"
PRE_PATH = "experiments/EXP-0053-m4-indirect-api-semantics/PRE_REGISTRATION.md"
STATIC_ARTIFACTS = {"PRE_REGISTRATION.md","README.md","RESULTS.md","harness/probe.m",
                    "run.py","make_manifest.py","verify.py","analysis/analyze.py",
                    "analysis/summary.json","analysis/report.txt"}
MANIFEST_BASE = "e704f8dc945c5f1318d8df5f514ab6169e4bf04a"
RUN02_STDOUT_LINES = [
    "DEVICE Apple M4",
    "SUPPORT icb_api=attempted",
    "COMMAND label=indirect-zero status=4 error=none",
    "COMPUTE case=indirect-zero expected_threads=0 counter=0 mismatches=0 guards=0 args=0,1,1 output_fnv=577e53ec5812a283",
    "COMMAND label=cpu-mutate-before-commit status=4 error=none",
    "COMPUTE case=cpu-mutate-before-commit expected_threads=24 counter=24 mismatches=0 guards=0 args=3,1,1 output_fnv=08b5d47700595c6b",
    "COMMAND label=gpu-producer-prior-encoder status=4 error=none",
    "COMPUTE case=gpu-producer-prior-encoder expected_threads=32 counter=32 mismatches=0 guards=0 args=4,1,1 output_fnv=45481b45a99fef63",
    "COMMAND label=indirect-draw-zero status=4 error=none",
    "DRAW case=indirect-draw-zero vertices=0 guards=0 rgba=01020304010203040102030401020304",
    "COMMAND label=indirect-draw-three status=4 error=none",
    "DRAW case=indirect-draw-three vertices=3 guards=0 rgba=11223344112233441122334411223344",
    "COMMAND label=full status=5 error=Caused GPU Address Fault Error (0000000b:kIOGPUCommandBufferCallbackErrorPageFault)",
    "COMMAND label=prefix status=5 error=Caused GPU Address Fault Error (0000000b:kIOGPUCommandBufferCallbackErrorPageFault)",
    "COMMAND label=suffix status=5 error=Ignored (for causing prior/excessive GPU errors) (00000004:kIOGPUCommandBufferCallbackErrorSubmissionsIgnored)",
    "COMMAND label=middle status=5 error=Ignored (for causing prior/excessive GPU errors) (00000004:kIOGPUCommandBufferCallbackErrorSubmissionsIgnored)",
    "COMMAND label=empty status=5 error=Ignored (for causing prior/excessive GPU errors) (00000004:kIOGPUCommandBufferCallbackErrorSubmissionsIgnored)",
    "COMMAND label=reset-middle status=5 error=Ignored (for causing prior/excessive GPU errors) (00000004:kIOGPUCommandBufferCallbackErrorSubmissionsIgnored)",
    "COMMAND label=restore-one status=5 error=Ignored (for causing prior/excessive GPU errors) (00000004:kIOGPUCommandBufferCallbackErrorSubmissionsIgnored)",
    "COMMAND label=optimized-full status=5 error=Ignored (for causing prior/excessive GPU errors) (00000004:kIOGPUCommandBufferCallbackErrorSubmissionsIgnored)",
    "RESULT FAIL",
]


def digest_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    return digest_bytes(path.read_bytes())


def require(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def inventory(path):
    result = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        parts = line.split("  ")
        require(len(parts) == 2 and len(parts[0]) == 64, f"malformed inventory {path}:{number}")
        want, relative = parts; pure = PurePosixPath(relative)
        require(not pure.is_absolute() and ".." not in pure.parts and relative not in result,
                f"unsafe/duplicate inventory path {relative}")
        try: int(want, 16)
        except ValueError: require(False, f"nonhex inventory {path}:{number}")
        result[relative] = want
    return result


def source_hashes():
    current = (HERE / "harness/probe.m").read_text()
    hex_helper = '''static void print_hex_field(const char *name, const void *bytes, size_t length) {
    const uint8_t *p = bytes;
    printf(" %s=", name);
    for (size_t i = 0; i < length; ++i) printf("%02x", p[i]);
}

'''
    run03 = current.replace(hex_helper, "").replace(
'''    printf("COMPUTE case=%s expected_threads=%u counter=%u mismatches=%u guards=%u "
           "args=%u,%u,%u output_fnv=%016llx", name, expected_threads, c[1],
           mismatches, guard_errors, a[4], a[5], a[6],
           (unsigned long long)fnv1a(o, output.length));
    print_hex_field("arg_hex", a, args.length);
    print_hex_field("counter_hex", c, counter.length);
    print_hex_field("output_hex", o, output.length);
    printf("\\n");
''', '''    printf("COMPUTE case=%s expected_threads=%u counter=%u mismatches=%u guards=%u "
           "args=%u,%u,%u output_fnv=%016llx\\n", name, expected_threads, c[1],
           mismatches, guard_errors, a[4], a[5], a[6],
           (unsigned long long)fnv1a(o, output.length));
''').replace(
'''    printf("DRAW case=%s vertices=%u guards=%u rgba=%s", name, vertex_count, guards, hex);
    print_hex_field("arg_hex", words, args.length);
    printf("\\n");
''', '''    printf("DRAW case=%s vertices=%u guards=%u rgba=%s\\n", name, vertex_count, guards, hex);
''')
    require(run03 != current, "run03 source reconstruction")
    run02 = run03.replace("        pd.supportIndirectCommandBuffers = YES;\n", "")
    require(run02 != run03, "run02 source reconstruction")
    run01 = run02.replace(
        '        printf("SUPPORT icb_api=attempted\\n");\n',
        '        printf("SUPPORT icb=%d\\n", (int)dev.supportsIndirectCommandBuffers);\n'
        '        if (!dev.supportsIndirectCommandBuffers) { printf("RESULT UNSUPPORTED\\n"); return 2; }\n'
    ).replace(
        '        if (!icb) { printf("RESULT UNSUPPORTED icb_allocation=nil\\n"); return 2; }\n', ""
    )
    require(run01 != run02, "run01 source reconstruction")
    return {"m4_20260817_run01":digest_bytes(run01.encode()),
            "m4_20260817_run02":digest_bytes(run02.encode()),
            "m4_20260817_run03":digest_bytes(run03.encode()),
            "m4_20260817_run04":digest_bytes(run03.encode()),
            "m4_20260817_run05":digest_bytes(current.encode()),
            "m4_20260817_run06":digest_bytes(current.encode())}


def verify_runs():
    raw = HERE / "raw"
    require({path.name for path in raw.iterdir() if path.is_dir()} == set(RUNS), "raw run set")
    harness_hashes = source_hashes()
    for run_id, outcome in RUNS.items():
        directory = raw / run_id
        require(directory.is_dir() and not directory.is_symlink(), f"run directory {run_id}")
        entries = list(directory.rglob("*"))
        require(all(path.is_file() and not path.is_symlink() and path.parent == directory for path in entries),
                f"nested/special raw entry {run_id}")
        expected = set(BASE_FILES) | ({"run.json"} if outcome != "build-failure" else set())
        require({path.name for path in entries} == expected, f"raw file set {run_id}")
        sums = inventory(directory / "SHA256SUMS")
        require(set(sums) == expected - {"SHA256SUMS"}, f"inventory coverage {run_id}")
        for relative, want in sums.items():
            require(digest(directory / relative) == want, f"raw hash {run_id}/{relative}")

        env = json.loads((directory / "environment.json").read_text())
        require(env["pre_registration_sha256"] == PRE_HASH and env["repo_revision"] == BASE_REVISION,
                f"prereg/revision {run_id}")
        require(env["target"] == {"cpu_brand":"Apple M4","machine":"arm64","model":"Mac16,10",
          "sw_vers":"ProductName:\t\tmacOS\nProductVersion:\t\t26.6.2\nBuildVersion:\t\t25G82"},
          f"target {run_id}")
        require(env["authored_sources"] == {PRE_PATH:PRE_HASH,RUNNER_PATH:digest(HERE / "run.py"),
                                             SOURCE_PATH:harness_hashes[run_id]},
                f"source binding {run_id}")
        require({key:env[key] for key in ("apple_binary_introspection","apple_auxiliary_code_inspection",
          "compiled_shader_bytes_inspected","iokit_or_bo_payload_tracing","pointer_following",
          "mutation_or_splice")} == {
          "apple_binary_introspection":"NONE","apple_auxiliary_code_inspection":"NONE",
          "compiled_shader_bytes_inspected":"NONE","iokit_or_bo_payload_tracing":"NONE",
          "pointer_following":"NONE","mutation_or_splice":"NONE"}, f"clean-room {run_id}")
        build = json.loads((directory / "build.json").read_text())
        require(build["timeout_seconds"] == 60 and not build.get("timed_out",False), f"build timeout {run_id}")
        require(len(build["argv"]) == 9 and build["argv"][:7] ==
                ["clang","-fobjc-arc","-framework","Metal","-framework","Foundation","-o"] and
                build["argv"][8] == str(HERE / "harness/probe.m"), f"build argv {run_id}")
        failures = json.loads((directory / "failures.json").read_text())
        if outcome == "build-failure":
            require(build["exit"] == 1 and failures == [{"phase":"build","record":"build.json"}],
                    "preserved build failure")
            require("supportsIndirectCommandBuffers" in build["stderr"], "build diagnostic")
        else:
            require(build["exit"] == 0, f"build status {run_id}")
            require(build["stdout"] == "" and build["stderr"] == "", f"build output {run_id}")
            run = json.loads((directory / "run.json").read_text())
            require(run["timeout_seconds"] == 90 and not run.get("timed_out",False), f"run timeout {run_id}")
            require(run["argv"] == [build["argv"][7]] and run["stderr"] == "", f"run argv/stderr {run_id}")
            if outcome == "gpu-failure":
                require(run["exit"] == 10 and failures == [{"phase":"run","record":"run.json"}],
                        "preserved GPU failure")
                lines = run["stdout"].splitlines()
                require(lines == RUN02_STDOUT_LINES and run["stdout"].endswith("\n"),
                        "closed exact GPU failure transcript")
            else:
                require(run["exit"] == 0 and failures == [] and run["stdout"].endswith("RESULT OK\n"),
                        f"canonical result {run_id}")
                if outcome == "hash-only-success":
                    require("arg_hex=" not in run["stdout"], f"historical retention class {run_id}")
                else:
                    require(run["stdout"].count("arg_hex=") == 5 and
                            run["stdout"].count("counter_hex=") == 3 and
                            run["stdout"].count("output_hex=") == 3,
                            f"canonical full-byte retention {run_id}")
    require(json.loads((raw/"m4_20260817_run03/run.json").read_text())["stdout"] ==
            json.loads((raw/"m4_20260817_run04/run.json").read_text())["stdout"],
            "historical successful stdout mismatch")
    require(json.loads((raw/"m4_20260817_run05/run.json").read_text())["stdout"] ==
            json.loads((raw/"m4_20260817_run06/run.json").read_text())["stdout"],
            "canonical stdout mismatch")


def verify_analysis():
    with tempfile.TemporaryDirectory(prefix="exp0053-verify-") as temp:
        subprocess.run(["python3", str(HERE / "analysis/analyze.py"), "--output-dir", temp],
                       check=True, capture_output=True, text=True, timeout=15)
        for name in ("summary.json","report.txt"):
            require((Path(temp)/name).read_bytes() == (HERE/"analysis"/name).read_bytes(),
                    f"stale analysis/{name}")


def verify_manifest():
    manifest = json.loads((HERE / "manifest.json").read_text())
    require(manifest["schema"] == 1 and manifest["experiment"] == "EXP-0053-m4-indirect-api-semantics",
            "manifest identity")
    require(manifest["base_revision_at_manifest"] == MANIFEST_BASE,
            "manifest generation base")
    ancestry = subprocess.run(["git","-C",str(HERE.parents[1]),"merge-base","--is-ancestor",
                               MANIFEST_BASE,"HEAD"],capture_output=True,text=True,timeout=15)
    require(ancestry.returncode == 0, "manifest base is not an ancestor of HEAD")
    require(manifest["run_base_revision"] == BASE_REVISION, "manifest run base")
    require(manifest["pre_registration"] == {"commit":"3dea789d","sha256":PRE_HASH},
            "manifest preregistration")
    require(manifest["canonical_runs"] == ["m4_20260817_run05","m4_20260817_run06"] and
            manifest["preserved_failed_runs"] == ["m4_20260817_run01","m4_20260817_run02"],
            "manifest runs")
    require(manifest["preserved_noncanonical_successes"] ==
            ["m4_20260817_run03","m4_20260817_run04"], "manifest historical successes")
    require(manifest["provenance"] == {"categories":["HW-PROBE","OWN-SHADER source"],
      "apple_binary_introspection":"NONE","apple_auxiliary_code_inspection":"NONE",
      "compiled_shader_bytes_inspected":"NONE","command_bo_payload_tracing":"NONE",
      "pointer_following":"NONE","mutation_or_splice":"NONE"}, "manifest provenance")
    listed = {item["path"]:item for item in manifest["artifacts"]}
    require(len(listed) == len(manifest["artifacts"]), "duplicate manifest path")
    expected = set(STATIC_ARTIFACTS)
    for run_id, outcome in RUNS.items():
        files = set(BASE_FILES) | ({"run.json"} if outcome != "build-failure" else set())
        expected |= {f"raw/{run_id}/{name}" for name in files}
    actual = {path.relative_to(HERE).as_posix():path for path in HERE.rglob("*")
              if path.is_file() and path.name != "manifest.json" and "__pycache__" not in path.parts}
    require(set(actual) == expected and set(listed) == expected, "exact artifact coverage")
    for relative, path in actual.items():
        require(not path.is_symlink(), f"symlink {relative}")
        require(path.suffix in {".md",".m",".py",".json",".txt"} or path.name == "SHA256SUMS",
                f"unexpected artifact type {relative}")
        require(listed[relative]["bytes"] == path.stat().st_size and
                listed[relative]["sha256"] == digest(path), f"manifest hash {relative}")


def main():
    require(digest(HERE / "PRE_REGISTRATION.md") == PRE_HASH, "pre-registration hash")
    verify_runs(); verify_analysis(); verify_manifest()
    manifest = json.loads((HERE / "manifest.json").read_text())
    print(f"PASS prereg=1 raw_runs=6 canonical=2 noncanonical_successes=2 failures=2 "
          f"analysis=PASS artifacts={len(manifest['artifacts'])}")


if __name__ == "__main__":
    main()
