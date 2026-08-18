#!/usr/bin/env python3
"""Append-only runner for the EXP-0054 public-Metal HW probe."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import platform
import re
import subprocess
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
HARNESS = HERE / "harness" / "probe.m"
PRE = HERE / "PRE_REGISTRATION.md"
AMEND = HERE / "PRE_REGISTRATION_AMENDMENT.md"
FOLLOWUP = HERE / "PRE_REGISTRATION_FOLLOWUP.md"
PRE_HASH = "7bff360264354961cd0d22f043e65a0d800f4d23efd1b8c516e9ee564cad8953"
AMEND_HASH = "c8ccd2144a0423a9a48fd3f7754228e4665f931996cbeb1a5406114782379517"
FOLLOWUP_HASH = "11b52fec26751be0752340786b98573ba16e50fcfef9741531f176ec7e7c640d"
PRE_COMMIT = "13d200c5aeae67182b4555c51eb728a413a954aa"
AMEND_COMMIT = "7a7fde9c"
FOLLOWUP_COMMIT = "4c43187a"
RUN_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
PUBLIC_HEADERS = [
    Path("/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks/Metal.framework/Headers/MTLRenderCommandEncoder.h"),
    Path("/Library/Developer/CommandLineTools/SDKs/MacOSX.sdk/System/Library/Frameworks/Metal.framework/Headers/MTL4RenderCommandEncoder.h"),
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(argv: list[object]) -> str:
    return subprocess.run([str(x) for x in argv], check=True, capture_output=True,
                          text=True, timeout=15).stdout.strip()


def invoke(argv: list[object], timeout: int) -> dict[str, object]:
    args = [str(x) for x in argv]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        cp = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return {"argv": args, "timeout_seconds": timeout, "started_utc": started,
                "exit": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr}
    except subprocess.TimeoutExpired as exc:
        def text(value: object) -> str:
            if isinstance(value, bytes):
                return value.decode(errors="replace")
            return str(value or "")
        return {"argv": args, "timeout_seconds": timeout, "started_utc": started,
                "exit": None, "timed_out": True,
                "stdout": text(exc.stdout), "stderr": text(exc.stderr)}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not RUN_ID.fullmatch(args.run_id):
        raise SystemExit("run-id must contain only alphanumerics, dash, underscore")
    if (digest(PRE) != PRE_HASH or digest(AMEND) != AMEND_HASH or
            digest(FOLLOWUP) != FOLLOWUP_HASH):
        raise SystemExit("frozen preregistration hash mismatch")

    out = HERE / "raw" / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    revision = command(["git", "-C", REPO, "rev-parse", "HEAD"])
    environment = {
        "captured_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "run_id": args.run_id,
        "repo_revision": revision,
        "pre_registration": {"commit": PRE_COMMIT, "sha256": PRE_HASH},
        "pre_run_amendment": {"commit": AMEND_COMMIT, "sha256": AMEND_HASH},
        "pre_run_followup": {"commit": FOLLOWUP_COMMIT, "sha256": FOLLOWUP_HASH},
        "target": {
            "model": command(["sysctl", "-n", "hw.model"]),
            "cpu_brand": command(["sysctl", "-n", "machdep.cpu.brand_string"]),
            "machine": platform.machine(),
            "sw_vers": command(["sw_vers"]),
        },
        "tools": {
            "clang": command(["clang", "--version"]).splitlines()[0],
            "python": platform.python_version(),
        },
        "authored_sources": {
            str(PRE.relative_to(REPO)): digest(PRE),
            str(AMEND.relative_to(REPO)): digest(AMEND),
            str(FOLLOWUP.relative_to(REPO)): digest(FOLLOWUP),
            str(HARNESS.relative_to(REPO)): digest(HARNESS),
            str(Path(__file__).relative_to(REPO)): digest(Path(__file__)),
        },
        "public_headers": {str(path): digest(path) for path in PUBLIC_HEADERS},
        "apple_binary_introspection": "NONE",
        "apple_auxiliary_code_inspection": "NONE",
        "compiled_shader_bytes_inspected": "NONE",
        "command_or_state_bo_payload_tracing": "NONE",
        "pointer_following": "NONE",
        "generic_memory_scan": "NONE",
        "mutation_splice_replay": "NONE",
    }
    write_json(out / "environment.json", environment)

    failures: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="exp0054-") as temporary:
        executable = Path(temporary) / "probe"
        build = invoke(["clang", "-fobjc-arc", "-framework", "Metal",
                        "-framework", "Foundation", "-o", executable, HARNESS], 60)
        write_json(out / "build.json", build)
        if build.get("exit") != 0:
            failures.append({"phase": "build", "record": "build.json"})
        else:
            run = invoke([executable], 120)
            write_json(out / "run.json", run)
            if run.get("exit") != 0:
                failures.append({"phase": "run", "record": "run.json"})

    write_json(out / "failures.json", failures)
    inventory = []
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "SHA256SUMS":
            inventory.append(f"{digest(path)}  {path.name}")
    (out / "SHA256SUMS").write_text("\n".join(inventory) + "\n")
    print(json.dumps({"run": args.run_id, "failures": failures,
                      "artifacts": len(inventory)}, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
