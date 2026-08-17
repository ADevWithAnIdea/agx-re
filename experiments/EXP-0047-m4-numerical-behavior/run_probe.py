#!/usr/bin/env python3
"""Compile and execute authored numerical-boundary kernels twice on local M4."""

import argparse
import datetime
import hashlib
import json
import platform
import re
import subprocess
import sys
import tempfile
from pathlib import Path


CASES = {
    "fidentity": {
        "function": "k_fidentity",
        "a": [0x00000001, 0x007FFFFF, 0x80000001, 0x807FFFFF,
              0x00000000, 0x80000000, 0x7FC12345, 0x7F800000],
    },
    "fadd": {
        "function": "k_fadd",
        "a": [0x00000001, 0x007FFFFF, 0x80000001, 0x00000000, 0x80000000, 0x00800000],
        "b": [0x00000001, 0x00000001, 0x80000001, 0x80000000, 0x80000000, 0x807FFFFF],
    },
    "fmul": {
        "function": "k_fmul",
        "a": [0x00800000, 0x00000001, 0x80800000, 0x00800000, 0x7F7FFFFF, 0xFF7FFFFF],
        "b": [0x3F000000, 0x40000000, 0x3F000000, 0x00800000, 0x40000000, 0x40000000],
    },
    "fmin": {
        "function": "k_fmin",
        "a": [0x7FC12345, 0x40400000, 0x7FC12345, 0x00000000, 0x80000000,
              0x80000000, 0x00000000, 0x7F800000, 0xFF800000, 0x00000001,
              0x3F800000, 0x40000000, 0xBF800000, 0xC0000000, 0x7F800000],
        "b": [0x40400000, 0x7FC54321, 0x7FC54321, 0x80000000, 0x00000000,
              0x80000000, 0x00000000, 0x7F800000, 0xFF800000, 0x80000001,
              0x40000000, 0x3F800000, 0xC0000000, 0xBF800000, 0xFF800000],
    },
    "fmax": {
        "function": "k_fmax",
        "a": [0x7FC12345, 0x40400000, 0x7FC12345, 0x00000000, 0x80000000,
              0x80000000, 0x00000000, 0x7F800000, 0xFF800000, 0x00000001,
              0x3F800000, 0x40000000, 0xBF800000, 0xC0000000, 0x7F800000],
        "b": [0x40400000, 0x7FC54321, 0x7FC54321, 0x80000000, 0x00000000,
              0x80000000, 0x00000000, 0x7F800000, 0xFF800000, 0x80000001,
              0x40000000, 0x3F800000, 0xC0000000, 0xBF800000, 0xFF800000],
    },
    "rint": {
        "function": "k_rint",
        "a": [0x3FC00000, 0x40200000, 0xBFC00000, 0xC0200000,
              0x3F000000, 0xBF000000, 0x4059999A, 0xC059999A,
              0x3FBFFFFF, 0x3FC00001, 0x7F800000, 0xFF800000,
              0x7FC12345, 0x00000001, 0x80000001, 0x4B800000],
    },
    "round": {
        "function": "k_round",
        "a": [0x3FC00000, 0x40200000, 0xBFC00000, 0xC0200000,
              0x3F000000, 0xBF000000, 0x4059999A, 0xC059999A,
              0x3FBFFFFF, 0x3FC00001, 0x7F800000, 0xFF800000,
              0x7FC12345, 0x00000001, 0x80000001, 0x4B800000],
    },
    "hidentity": {
        "function": "k_hidentity",
        "a": [0x0001, 0x03FF, 0x8001, 0x83FF,
              0x0000, 0x8000, 0x7E55, 0x7C00],
    },
    "hadd": {
        "function": "k_hadd",
        "a": [0x0001, 0x03FF, 0x8001, 0x0000, 0x8000, 0x0400],
        "b": [0x0001, 0x0001, 0x8001, 0x8000, 0x8000, 0x83FF],
    },
    "hmul": {
        "function": "k_hmul",
        "a": [0x0400, 0x0001, 0x8400, 0x0400, 0x7BFF, 0xFBFF],
        "b": [0x3800, 0x4000, 0x3800, 0x0400, 0x4000, 0x4000],
    },
}


def checked(command, **kwargs):
    return subprocess.run(command, check=True, text=True, capture_output=True, **kwargs)


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def signed32(value):
    return value if value < (1 << 31) else value - (1 << 32)


def csv_bits(values):
    return ",".join(str(signed32(value)) for value in values)


def parse_case(stdout, case):
    main = re.search(r"^MAIN_ORIG ([0-9a-f]+)$", stdout, re.M)
    status = re.search(r"^STATUS (\S+)$", stdout, re.M)
    result = re.search(r"^RESULT 2 (.+)$", stdout, re.M)
    source_kind = re.search(r"^PIPELINE_SOURCE (\S+)$", stdout, re.M)
    if not all((main, status, result, source_kind)):
        raise RuntimeError(f"missing output fields for {case}:\n{stdout}")
    values = [(int(token) & 0xFFFFFFFF) for token in result.group(1).split()]
    main_bytes = bytes.fromhex(main.group(1))
    return {
        "function": CASES[case]["function"],
        "inputs": {key: [f"0x{value:08x}" for value in CASES[case][key]]
                   for key in ("a", "b") if key in CASES[case]},
        "outputs": [f"0x{value:08x}" for value in values],
        "status": status.group(1),
        "pipeline_source": source_kind.group(1),
        "main_hex": main.group(1),
        "main_length": len(main_bytes),
        "main_sha256": hashlib.sha256(main_bytes).hexdigest(),
    }


def target_identity():
    sw = checked(["sw_vers"], timeout=10).stdout
    product = dict(
        line.split(":", 1) for line in sw.splitlines() if ":" in line
    )
    brand = checked(["sysctl", "-n", "machdep.cpu.brand_string"], timeout=10).stdout.strip()
    display = checked(["system_profiler", "SPDisplaysDataType"], timeout=30).stdout
    cores = re.search(r"Total Number of Cores:\s*(\d+)", display)
    metal = re.search(r"Metal Support:\s*(.+)", display)
    return {
        "machine": platform.machine(),
        "cpu_brand": brand,
        "gpu_cores": int(cores.group(1)) if cores else None,
        "metal_support": metal.group(1).strip() if metal else None,
        "macos": product.get("ProductVersion", "").strip(),
        "build": product.get("BuildVersion", "").strip(),
    }


def one_pass(repo, experiment_dir, run_dir):
    tool_dir = repo / "tools"
    run_dir.mkdir(parents=True)
    shdump = run_dir / "shdump"
    agxrun = run_dir / "agxrun"
    for output, source in (
        (shdump, tool_dir / "shdump/shdump.m"),
        (agxrun, tool_dir / "agxtest/agxrun.m"),
    ):
        checked(
            ["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
             "-o", str(output), str(source)],
            timeout=60,
        )

    report = {}
    for name, case in CASES.items():
        case_dir = run_dir / name
        command = [
            sys.executable,
            str(tool_dir / "agxtest/agxtest.py"),
            "--source", str(experiment_dir / "kernels/numeric.metal"),
            "--function", case["function"],
            "--no-fast-math",
            "--grid", str(len(case["a"])),
            "--tg", str(len(case["a"])),
            "--buf", f"0={csv_bits(case['a'])}",
            "--out", f"2={len(case['a'])}",
            "--int",
            "--dump-main",
            "--run-timeout", "20",
            "--workdir", str(case_dir),
            "--shdump", str(shdump),
            "--agxrun", str(agxrun),
            "--agxparse", str(tool_dir / "shdump/agxparse.py"),
        ]
        if "b" in case:
            command += ["--buf", f"1={csv_bits(case['b'])}"]
        completed = checked(command, timeout=45)
        report[name] = parse_case(completed.stdout, name)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    repo = args.repo.resolve()
    experiment_dir = Path(__file__).resolve().parent
    captured_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="agx-exp0047-") as scratch:
        scratch_path = Path(scratch)
        passes = [
            one_pass(repo, experiment_dir, scratch_path / "run-a"),
            one_pass(repo, experiment_dir, scratch_path / "run-b"),
        ]
    result = {
        "schema": 1,
        "captured_at_utc": captured_at,
        "target": target_identity(),
        "compiler_mode": "runtime MSL, fast math disabled",
        "compiler_identity": {
            "clang": checked(["clang", "--version"], timeout=10).stdout.splitlines()[0],
            "macos_sdk": checked(
                ["xcrun", "--sdk", "macosx", "--show-sdk-version"], timeout=10
            ).stdout.strip(),
            "python": sys.version.splitlines()[0],
        },
        "repo_revision": checked(
            ["git", "rev-parse", "HEAD"], cwd=repo, timeout=10
        ).stdout.strip(),
        "invocation": "python3 experiments/EXP-0047-m4-numerical-behavior/run_probe.py",
        "authored_inputs": {
            str(path.relative_to(repo)): file_sha256(path)
            for path in (
                Path(__file__).resolve(),
                experiment_dir / "kernels/numeric.metal",
                repo / "tools/shdump/shdump.m",
                repo / "tools/agxtest/agxrun.m",
                repo / "tools/agxtest/agxtest.py",
                repo / "tools/shdump/agxparse.py",
            )
        },
        "passes": passes,
        "passes_equal": passes[0] == passes[1],
        "apple_binary_introspection": "NONE",
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
