#!/usr/bin/env python3
"""Re-extract only the machine code produced from EXP-0042's authored MSL."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
BUILD = ROOT / "build"


def run(command: list[str], *, timeout: int, output=None) -> None:
    subprocess.run(command, cwd=ROOT, timeout=timeout, check=True,
                   stdout=output, stderr=subprocess.STDOUT if output else None)


def extract(output: Path, name: str, source: Path, vertex: str, fragment: str) -> None:
    archive = BUILD / f"extract_{name}.bin"
    with (output / f"{name}.compile.txt").open("wb") as log:
        run([str(BUILD / "shdump"), "-o", str(archive), "--render",
             "--vertex", vertex, "--fragment", fragment, str(source)],
            timeout=120, output=log)
    with (output / f"{name}.structure.txt").open("wb") as report:
        run(["python3", str(REPO / "tools/shdump/agxparse.py"), str(archive)],
            timeout=30, output=report)
    for stage in ("vertex", "fragment"):
        for symbol, suffix in (("_agc.main", "main"),
                               ("_agc.main.constant_program", "constant_program")):
            with (output / f"{name}.{stage}.{suffix}.hex").open("wb") as result:
                run(["python3", str(REPO / "tools/shdump/agxparse.py"), str(archive),
                     "--stage", stage, "--symbol", symbol, "--extract-hex"],
                    timeout=30, output=result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    BUILD.mkdir(exist_ok=True)
    run(["xcrun", "clang", "-arch", "arm64", "-fobjc-arc", "-o",
         str(BUILD / "shdump"), str(REPO / "tools/shdump/shdump.m"),
         "-framework", "Metal", "-framework", "Foundation"], timeout=60)

    extract(output, "pipeline_a", ROOT / "kernels/pipeline_a.metal", "vs_main", "fs_main")
    extract(output, "pipeline_b", ROOT / "kernels/pipeline_b.metal", "vs_main", "fs_main")
    matrix = ROOT / "kernels/stage_matrix.metal"
    for name, vertex, fragment in (
        ("ss", "vs_small", "fs_small"), ("sf", "vs_small", "fs_large"),
        ("ls", "vs_large", "fs_small"), ("lf", "vs_large", "fs_large"),
        ("ea", "vs_small", "fs_equal_a"), ("eb", "vs_small", "fs_equal_b"),
    ):
        extract(output, name, matrix, vertex, fragment)


if __name__ == "__main__":
    main()
