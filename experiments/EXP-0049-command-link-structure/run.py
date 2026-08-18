#!/usr/bin/env python3
"""Run append-only EXP-0049 rollover searches with per-process timeouts."""
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
WORK = HERE / "work"
PREREG_HASH = "217063a4dad9831ece3d4fe974876d9d50b4216451c3cd281ae284382f3bc808"
VARIANTS = {
    "cdm-direct": ("cdm", 2048),
    "cdm-indirect": ("cdm", 2048),
    "cdm-encoder1": ("cdm", 2048),
    "cdm-pad7": ("cdm", 2048),
    "vdm-state1": ("vdm", 4096),
    "vdm-stable": ("vdm", 4096),
    "vdm-pass1": ("vdm", 4096),
    "vdm-pad7": ("vdm", 4096),
}
ALLOWED = {
    "va_100000b8000.bin", "va_100000b8000.meta",
    "va_10000158000.bin", "va_10000158000.meta",
    "va_18000.bin", "va_18000.meta",
    "va_88000.bin", "va_88000.meta",
}

def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def invoke(command: list[object], record: Path, timeout: int,
           env: dict[str, str] | None = None) -> int:
    argv = [str(x) for x in command]
    started = time.time()
    data: dict[str, object] = {"command": argv, "timeout_seconds": timeout,
                              "started_unix": started}
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
        data.update(exit=cp.returncode, elapsed_seconds=round(time.time()-started, 6),
                    stdout=cp.stdout, stderr=cp.stderr)
        rc = cp.returncode
    except subprocess.TimeoutExpired as exc:
        def text(value: object) -> str:
            if isinstance(value, bytes): return value.decode(errors="replace")
            return str(value or "")
        data.update(exit=124, timeout=True, elapsed_seconds=round(time.time()-started, 6),
                    stdout=text(exc.stdout), stderr=text(exc.stderr))
        rc = 124
    record.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return rc

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").isalnum():
        raise SystemExit("run-id may contain only alphanumerics, dash, underscore")
    prereg = HERE / "PRE_REGISTRATION.md"
    if digest(prereg) != PREREG_HASH:
        raise SystemExit("frozen pre-registration hash mismatch")
    out = RAW / args.run_id
    work = WORK / args.run_id
    out.mkdir(parents=True, exist_ok=False)
    work.mkdir(parents=True, exist_ok=False)
    inputs = [prereg, HERE/"run.py", HERE/"harness/probe.m",
              HERE/"harness/allowtrace.c", HERE/"analysis/analyze_trial.py"]
    (out/"00_inputs.json").write_text(json.dumps({
        "pre_registration_verified_before_build_and_hardware": True,
        "pre_registration_sha256": PREREG_HASH,
        "authored_inputs": {str(p.relative_to(HERE)): digest(p) for p in inputs},
    }, indent=2, sort_keys=True) + "\n")
    (out/"01_environment.json").write_text(json.dumps({
        "run_id": args.run_id, "started_unix": time.time(),
        "platform": platform.platform(), "machine": platform.machine(),
        "python": sys.version, "target": "local Apple M4/G16G only",
        "apple_binary_introspection": "NONE", "unknown_bo_contents": "NONE",
        "pointer_following": "NONE", "command_mutation": "NONE",
        "allowlist": ["0x100000b8000", "0x10000158000", "0x18000", "0x88000"],
    }, indent=2, sort_keys=True) + "\n")
    tracer = work / "allowtrace.dylib"
    probe = work / "probe"
    failures: list[dict[str, object]] = []
    rc1 = invoke(["xcrun", "clang", "-arch", "arm64e", "-dynamiclib", "-o", tracer,
                  HERE/"harness/allowtrace.c", "-framework", "IOKit", "-framework", "CoreFoundation"],
                 out/"02_build_allowtrace.json", 60)
    rc2 = invoke(["xcrun", "clang", "-arch", "arm64e", "-fobjc-arc", "-o", probe,
                  HERE/"harness/probe.m", "-framework", "Metal", "-framework", "Foundation"],
                 out/"03_build_probe.json", 60)
    if rc1 or rc2:
        failures.append({"phase": "build", "allowtrace_exit": rc1, "probe_exit": rc2})
    sequence = 0

    def trial(variant: str, count: int, phase: str) -> dict[str, object] | None:
        nonlocal sequence
        sequence += 1
        name = f"{sequence:03d}_{variant}_{phase}_n{count:04d}"
        directory = out / "trials" / name
        state = directory / "state"
        state.mkdir(parents=True)
        env = os.environ.copy()
        env.update({"DYLD_INSERT_LIBRARIES": str(tracer),
                    "ALLOWTRACE_LOG": str(directory/"trace.log"),
                    "ALLOWTRACE_DUMP_DIR": str(state)})
        rc = invoke([probe, "--variant", variant, "--count", count, "--dump"],
                    directory/"run.json", 45, env)
        actual = {p.name for p in state.iterdir() if p.is_file()}
        if not actual <= ALLOWED:
            failures.append({"variant": variant, "phase": phase, "count": count,
                             "error": "allowlist_violation", "extra": sorted(actual-ALLOWED)})
            return None
        engine = VARIANTS[variant][0]
        source = "va_100000b8000.bin" if engine == "cdm" else "va_18000.bin"
        if rc or source not in actual:
            failures.append({"variant": variant, "phase": phase, "count": count,
                             "error": "probe_or_capture", "exit": rc,
                             "captured": sorted(actual)})
            return None
        analysis_record = directory / "analysis-run.json"
        arc = invoke([sys.executable, HERE/"analysis/analyze_trial.py", "--trial", directory,
                      "--engine", engine, "--output", directory/"analysis.json"],
                     analysis_record, 15)
        if arc:
            failures.append({"variant": variant, "phase": phase, "count": count,
                             "error": "analysis", "exit": arc})
            return None
        return json.loads((directory/"analysis.json").read_text())

    summaries: dict[str, object] = {}
    if not failures:
        for variant, (engine, upper) in VARIANTS.items():
            observations: list[dict[str, object]] = []
            low_result = trial(variant, 1, "discover")
            high_result = trial(variant, upper, "discover")
            if low_result: observations.append(low_result)
            if high_result: observations.append(high_result)
            if low_result is None or high_result is None:
                summaries[variant] = {"status": "STOPPED", "reason": "trial failure"}
                continue
            if low_result["known_link"] or not high_result["known_link"]:
                reason = "count1 linked" if low_result["known_link"] else "upper bound has no known link"
                failures.append({"variant": variant, "phase": "bracket", "error": reason,
                                 "upper": upper})
                summaries[variant] = {"status": "STOPPED", "reason": reason,
                                      "observations": observations}
                continue
            low, high = 1, upper
            while high - low > 1:
                middle = (low + high) // 2
                result = trial(variant, middle, "discover")
                if result is None:
                    break
                observations.append(result)
                if result["known_link"]: high = middle
                else: low = middle
            if high - low != 1:
                summaries[variant] = {"status": "STOPPED", "reason": "search trial failure",
                                      "observations": observations}
                continue
            repeat_low = trial(variant, low, "repeat")
            repeat_high = trial(variant, high, "repeat")
            if repeat_low: observations.append(repeat_low)
            if repeat_high: observations.append(repeat_high)
            ordered = sorted((int(x["count"]), bool(x["known_link"])) for x in observations)
            monotonic = not any(link and any(not later_link for later_count,later_link in ordered if later_count>count)
                                for count,link in ordered)
            if repeat_low is None or repeat_high is None or repeat_low["known_link"] or not repeat_high["known_link"] or not monotonic:
                failures.append({"variant": variant, "phase": "repeat", "error": "boundary mismatch",
                                 "lower": low, "threshold": high, "monotonic": monotonic})
                summaries[variant] = {"status": "STOPPED", "reason": "boundary repeat mismatch",
                                      "observations": observations}
                continue
            boundary_highs = [x for x in observations if int(x["count"]) == high and x["known_link"]]
            summaries[variant] = {
                "status": "PASS", "engine": engine, "lower_no_link": low,
                "first_known_link": high,
                "link_offsets": [x["link_offsets"] for x in boundary_highs],
                "known_link_words": high_result["known_link_words"],
                "observations": observations,
            }
    (out/"summary.json").write_text(json.dumps({"schema": 1, "run_id": args.run_id,
        "scope": "local M4 only; structural correlations; no mutation; no A18 claim",
        "variants": summaries}, indent=2, sort_keys=True) + "\n")
    (out/"failures.json").write_text(json.dumps(failures, indent=2, sort_keys=True) + "\n")
    sums=[]
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS":
            sums.append(f"{digest(path)}  {path.relative_to(out)}")
    (out/"SHA256SUMS").write_text("\n".join(sums) + "\n")
    print(json.dumps({"run_id": args.run_id, "variants": summaries,
                      "failures": failures}, indent=2, sort_keys=True))
    return 1 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
