#!/usr/bin/env python3
"""Append-only runner for EXP-0053; public API output only."""

import argparse
import datetime
import hashlib
import json
import platform
import subprocess
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PRE_HASH = "4773ea2764b1fd3479ec2f52881ff7dcb2b1cfe0fa2e1f592db37b57db8bd34f"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(argv):
    return subprocess.run(argv, check=True, capture_output=True, text=True, timeout=15).stdout.strip()


def invoke(argv, timeout):
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        cp = subprocess.run([str(item) for item in argv], capture_output=True, text=True, timeout=timeout)
        return {"argv": [str(item) for item in argv], "timeout_seconds": timeout,
                "started_utc": started, "exit": cp.returncode,
                "stdout": cp.stdout, "stderr": cp.stderr}
    except subprocess.TimeoutExpired as exc:
        def text(value):
            return value.decode(errors="replace") if isinstance(value, bytes) else (value or "")
        return {"argv": [str(item) for item in argv], "timeout_seconds": timeout,
                "started_utc": started, "exit": None, "timed_out": True,
                "stdout": text(exc.stdout), "stderr": text(exc.stderr)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if digest(HERE / "PRE_REGISTRATION.md") != PRE_HASH:
        raise SystemExit("pre-registration hash mismatch")
    out = HERE / "raw" / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    environment = {
        "captured_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "pre_registration_sha256": PRE_HASH,
        "repo_revision": command(["git", "-C", str(REPO), "rev-parse", "HEAD"]),
        "target": {"model": command(["sysctl", "-n", "hw.model"]),
                   "cpu_brand": command(["sysctl", "-n", "machdep.cpu.brand_string"]),
                   "machine": platform.machine(), "sw_vers": command(["sw_vers"])},
        "clang": command(["clang", "--version"]).splitlines()[0],
        "authored_sources": {str(path.relative_to(REPO)): digest(path) for path in
                             (HERE / "PRE_REGISTRATION.md", HERE / "harness/probe.m", HERE / "run.py")},
        "apple_binary_introspection": "NONE",
        "apple_auxiliary_code_inspection": "NONE",
        "compiled_shader_bytes_inspected": "NONE",
        "iokit_or_bo_payload_tracing": "NONE",
        "pointer_following": "NONE",
        "mutation_or_splice": "NONE",
    }
    (out / "environment.json").write_text(json.dumps(environment, indent=2, sort_keys=True) + "\n")
    failures = []
    with tempfile.TemporaryDirectory(prefix="exp0053-") as temp:
        executable = Path(temp) / "probe"
        build = invoke(["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
                        "-o", executable, HERE / "harness/probe.m"], 60)
        (out / "build.json").write_text(json.dumps(build, indent=2, sort_keys=True) + "\n")
        if build.get("exit") != 0:
            failures.append({"phase": "build", "record": "build.json"})
        else:
            run = invoke([executable], 90)
            (out / "run.json").write_text(json.dumps(run, indent=2, sort_keys=True) + "\n")
            if run.get("exit") != 0:
                failures.append({"phase": "run", "record": "run.json"})
    (out / "failures.json").write_text(json.dumps(failures, indent=2, sort_keys=True) + "\n")
    sums = []
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            sums.append(f"{digest(path)}  {path.relative_to(out)}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    print(json.dumps({"run": args.run_id, "failures": failures, "artifacts": len(sums)}, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
