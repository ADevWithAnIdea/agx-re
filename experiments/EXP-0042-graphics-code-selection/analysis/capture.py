#!/usr/bin/env python3
"""Build and capture EXP-0042 with hard subprocess timeouts.

Only our Objective-C/MSL source and boundary data are handled here. The dylib is
built from the repository's clean-room iotrace source; no Apple binary is read.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
BUILD = ROOT / "build"
RAW = ROOT / "raw"


def run(command: list[str], *, timeout: int, env: dict[str, str] | None = None,
        stdout=None, stderr=None) -> None:
    print("+", " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr,
                   timeout=timeout, check=True)


def build() -> None:
    BUILD.mkdir(exist_ok=True)
    run([
        "xcrun", "clang", "-arch", "arm64", "-dynamiclib", "-o",
        str(BUILD / "iotrace.dylib"), str(REPO / "tools/iotrace/iotrace.c"),
        "-framework", "IOKit", "-framework", "CoreFoundation",
    ], timeout=60)
    run([
        "xcrun", "clang", "-arch", "arm64", "-fobjc-arc", "-o",
        str(BUILD / "multipipe"), str(ROOT / "harness/multipipe.m"),
        "-framework", "Metal", "-framework", "Foundation",
    ], timeout=60)
    run([
        "xcrun", "clang", "-arch", "arm64", "-fobjc-arc", "-o",
        str(BUILD / "stage_matrix"), str(ROOT / "harness/stage_matrix.m"),
        "-framework", "Metal", "-framework", "Foundation",
    ], timeout=60)


def capture(label: str, order: str, prealloc: int) -> None:
    outdir = RAW / label
    if outdir.exists():
        raise SystemExit(f"refusing to overwrite append-only raw capture: {outdir}")
    outdir.mkdir(parents=True)
    dumpdir = outdir / "maps"
    dumpdir.mkdir()
    env = os.environ.copy()
    env.update({
        "DYLD_INSERT_LIBRARIES": str(BUILD / "iotrace.dylib"),
        "IOTRACE_LOG": str(outdir / "iotrace.log"),
        "IOTRACE_DUMP_DIR": str(dumpdir),
        "IOTRACE_DUMP_PERSIG": "1",
        "IOTRACE_DUMP_ON_USR1": "1",
        "IOTRACE_MAX_MAP": "4194304",
    })
    with (outdir / "stdout.txt").open("wb") as stdout, \
         (outdir / "stderr.txt").open("wb") as stderr:
        run([
            str(BUILD / "multipipe"), "--source-a", "kernels/pipeline_a.metal",
            "--source-b", "kernels/pipeline_b.metal", "--compile-order", order,
            "--prealloc", str(prealloc), "--dump",
        ], timeout=180, env=env, stdout=stdout, stderr=stderr)


def capture_matrix(label: str) -> None:
    outdir = RAW / label
    if outdir.exists():
        raise SystemExit(f"refusing to overwrite append-only raw capture: {outdir}")
    outdir.mkdir(parents=True)
    dumpdir = outdir / "maps"
    dumpdir.mkdir()
    env = os.environ.copy()
    env.update({
        "DYLD_INSERT_LIBRARIES": str(BUILD / "iotrace.dylib"),
        "IOTRACE_LOG": str(outdir / "iotrace.log"),
        "IOTRACE_DUMP_DIR": str(dumpdir),
        "IOTRACE_DUMP_PERSIG": "1",
        "IOTRACE_DUMP_ON_USR1": "1",
        "IOTRACE_MAX_MAP": "4194304",
    })
    with (outdir / "stdout.txt").open("wb") as stdout, \
         (outdir / "stderr.txt").open("wb") as stderr:
        run([str(BUILD / "stage_matrix"), "--source",
             "kernels/stage_matrix.metal", "--dump"], timeout=180, env=env,
            stdout=stdout, stderr=stderr)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-only", action="store_true")
    parser.add_argument("--label")
    parser.add_argument("--order", choices=("AB", "BA"), default="AB")
    parser.add_argument("--prealloc", type=int, default=0)
    parser.add_argument("--matrix", action="store_true")
    args = parser.parse_args()
    build()
    if args.build_only:
        return 0
    if not args.label:
        parser.error("--label is required unless --build-only is used")
    if args.matrix:
        capture_matrix(args.label)
    else:
        capture(args.label, args.order, args.prealloc)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.TimeoutExpired as error:
        print(f"TIMEOUT after {error.timeout}s: {error.cmd}", file=sys.stderr)
        raise SystemExit(124)
