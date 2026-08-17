#!/usr/bin/env python3
"""Build and run the pre-registered EXP-0048 matrix with hard timeouts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
HARNESS = HERE / "harness"
EXPECTED_PREREG = "872ea37e256cc196d4e62e41a48d77f14eb9303c4fa7cc9509e63298941ffa78"
CASES = [
    "rgba8-clear-store-draw",
    "rgba8-clear-store-empty",
    "rgba8-load-store-empty",
    "rgba8-dontcare-store-draw",
    "rgba8-clear-dontcare-draw",
    "bgra8-clear-store-draw",
    "rgba8srgb-clear-store-draw",
    "r32f-clear-store-draw",
    "r32u-clear-store-draw",
    "rgba8-load-store-blend",
    "rgba8-clear-store-atomic",
    "mixed-r32f-clear-store",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def invoke(cmd: list[object], log: Path, timeout: int, env: dict[str, str] | None = None) -> int:
    argv = [str(x) for x in cmd]
    started = time.time()
    record: dict[str, object] = {"command": argv, "timeout_seconds": timeout,
                                 "started_unix": started}
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
        record.update(exit=cp.returncode, elapsed_seconds=round(time.time()-started, 6),
                      stdout=cp.stdout, stderr=cp.stderr)
        rc = cp.returncode
    except subprocess.TimeoutExpired as exc:
        record.update(timeout=True, elapsed_seconds=round(time.time()-started, 6),
                      stdout=exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
                      stderr=exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or ""))
        rc = 124
    log.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        raise SystemExit("run-id may contain only alphanumerics, dash, underscore")
    prereg = HERE / "PRE_REGISTRATION.md"
    actual = sha256(prereg)
    if actual != EXPECTED_PREREG:
        raise SystemExit(f"frozen pre-registration hash changed: {actual}")

    out = RAW / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    work = HERE / "work" / args.run_id
    work.mkdir(parents=True, exist_ok=False)
    (out / "00_preregistration.json").write_text(json.dumps({
        "path": str(prereg.relative_to(HERE)), "sha256": actual,
        "verified_before_build_and_hardware": True,
    }, indent=2, sort_keys=True) + "\n")
    env_record = {
        "run_id": args.run_id,
        "started_unix": time.time(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "cwd": str(HERE),
        "clean_room": {
            "target": "local Apple M4 only",
            "apple_binary_inspection": False,
            "shader_binary_dump": False,
            "unknown_bo_dump": False,
            "pointer_following": False,
            "allowed_vas": ["0x18000", "0x58000", "0x68000", "0x10000018200"],
        },
    }
    (out / "01_environment.json").write_text(json.dumps(env_record, indent=2, sort_keys=True) + "\n")
    invoke(["sw_vers"], out / "02_sw_vers.json", 10)
    invoke(["uname", "-a"], out / "03_uname.json", 10)
    invoke(["clang", "--version"], out / "04_clang_version.json", 10)

    tracer = work / "allowtrace.dylib"
    probe = work / "probe"
    failures: list[dict[str, object]] = []
    rc = invoke(["clang", "-dynamiclib", "-o", tracer, HARNESS / "allowtrace.c",
                 "-framework", "IOKit", "-framework", "CoreFoundation"],
                out / "05_build_allowtrace.json", 30)
    if rc:
        failures.append({"phase": "build_allowtrace", "exit": rc})
    rc2 = invoke(["clang", "-fobjc-arc", "-o", probe, HARNESS / "probe.m",
                  "-framework", "Metal", "-framework", "Foundation"],
                 out / "06_build_probe.json", 30)
    if rc2:
        failures.append({"phase": "build_probe", "exit": rc2})
    if rc or rc2:
        (out / "failures.json").write_text(json.dumps(failures, indent=2) + "\n")
        return 1

    for case in CASES:
        case_dir = out / f"state_{case}"
        case_dir.mkdir()
        env = os.environ.copy()
        env.update({
            "DYLD_INSERT_LIBRARIES": str(tracer),
            "ALLOWTRACE_LOG": str(out / f"trace_{case}.log"),
            "ALLOWTRACE_DUMP_DIR": str(case_dir),
        })
        rc = invoke([probe, "--case", case, "--source-out", out / f"source_{case}.metal", "--dump"],
                    out / f"run_{case}.json", 45, env)
        required = {"va_18000.bin", "va_58000.bin", "va_68000.bin", "va_10000018200.bin"}
        present = {p.name for p in case_dir.glob("*.bin")}
        missing = sorted(required - present)
        extra = sorted(present - required)
        if rc or missing or extra:
            failures.append({"case": case, "exit": rc, "missing": missing, "extra": extra})

    (out / "failures.json").write_text(json.dumps(failures, indent=2, sort_keys=True) + "\n")
    hashes = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            hashes.append(f"{sha256(p)}  {p.relative_to(out)}")
    (out / "SHA256SUMS").write_text("\n".join(hashes) + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
