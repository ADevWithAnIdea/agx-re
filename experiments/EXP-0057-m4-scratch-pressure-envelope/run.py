#!/usr/bin/env python3
"""Append-only fresh-process runner for the pre-registered EXP-0057 matrix."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KERNELS, HARNESS, RAW_ROOT, WORK_ROOT = HERE / "kernels", HERE / "harness", HERE / "raw", HERE / "work"
LEVELS = [("baseline", 0), ("p576", 576), ("p1024", 1024), ("p2048", 2048),
          ("p4096", 4096), ("p8192", 8192), ("p16384", 16384)]
SHAPES = [("tg32", 32), ("tg256", 256)]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_id(value):
    if not value.replace("-", "").replace("_", "").isalnum():
        raise SystemExit("run ID may contain only alphanumerics, - and _")


def run(command, path, timeout):
    started = time.monotonic()
    try:
        cp = subprocess.run([str(x) for x in command], text=True, capture_output=True, timeout=timeout)
        record = {"command": [str(x) for x in command], "exit": cp.returncode,
                  "seconds": round(time.monotonic() - started, 3), "stdout": cp.stdout,
                  "stderr": cp.stderr, "timeout": False}
    except subprocess.TimeoutExpired as exc:
        record = {"command": [str(x) for x in command], "timeout": True, "seconds": timeout,
                  "stdout": exc.stdout or "", "stderr": exc.stderr or ""}
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--run-id", required=True)
    a = p.parse_args(); checked_id(a.run_id)
    raw, work = RAW_ROOT / a.run_id, WORK_ROOT / a.run_id
    raw.mkdir(parents=True, exist_ok=False); work.mkdir(parents=True, exist_ok=False)
    try:
        gen = run([sys.executable, "-B", KERNELS / "generate.py"], raw / "00_generate.json", 20)
        if gen.get("timeout") or gen.get("exit"):
            raise RuntimeError("source generation failed")
        source_dir = raw / "sources"; source_dir.mkdir()
        source_hashes = {}
        for name, _ in LEVELS:
            src = KERNELS / f"{name}.metal"; dst = source_dir / src.name
            shutil.copyfile(src, dst); source_hashes[dst.name] = digest(dst)
        (raw / "01_sources.json").write_text(json.dumps({"source_hashes": source_hashes}, indent=2, sort_keys=True) + "\n")
        probe = work / "probe"
        build = run(["clang", "-fobjc-arc", "-framework", "Metal", "-framework", "Foundation",
                     "-o", probe, HARNESS / "probe.m"], raw / "02_build_probe.json", 30)
        if build.get("timeout") or build.get("exit"):
            raise RuntimeError("probe build failed")
        stop = False
        for name, byte_count in LEVELS:
            words = byte_count // 4
            src = source_dir / f"{name}.metal"
            meta = run([sys.executable, "-B", HARNESS / "metadata.py", "--source", src],
                       raw / f"metadata_{name}.json", 100)
            if meta.get("timeout"):
                (raw / "STOP.json").write_text(json.dumps({"reason": "metadata_timeout", "case": name}, indent=2) + "\n")
                break
            for shape, tg in SHAPES:
                if stop: break
                trial = run([probe, "--source", src, "--words", words, "--tg", tg],
                            raw / f"trial_{name}_{shape}.json", 15)
                # A parent timeout is a safety stop.  Normal completed nonzero
                # outcomes remain evidence and allow the other shape to run.
                if trial.get("timeout"):
                    (raw / "STOP.json").write_text(json.dumps({"reason": "execution_timeout", "case": name,
                        "shape": shape, "recovery": "no automatic retry or recovery"}, indent=2) + "\n")
                    stop = True
        (raw / "run_manifest.json").write_text(json.dumps({"run_id": a.run_id, "levels": LEVELS, "shapes": SHAPES,
            "source_hashes": source_hashes, "runner": str(Path(__file__).relative_to(HERE)),
            "all_trials_fresh_processes": True}, indent=2, sort_keys=True) + "\n")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
