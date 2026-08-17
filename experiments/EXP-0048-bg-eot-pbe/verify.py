#!/usr/bin/env python3
"""Verify frozen preregistration, raw inventories, analysis, and manifest."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
EXPECTED={"PRE_REGISTRATION.md":"872ea37e256cc196d4e62e41a48d77f14eb9303c4fa7cc9509e63298941ffa78",
          "CONTROL_PRE_REGISTRATION.md":"588ccdf3a234c790e12311d99bf142d7b476a9663506409bf0bda66117bd35d1"}
RUNS=["m4_20260817_run01","m4_20260817_run02","m4_20260817_blend_control01","m4_20260817_blend_control02"]
CASES=[
 "rgba8-clear-store-draw","rgba8-clear-store-empty","rgba8-load-store-empty",
 "rgba8-dontcare-store-draw","rgba8-clear-dontcare-draw","bgra8-clear-store-draw",
 "rgba8srgb-clear-store-draw","r32f-clear-store-draw","r32u-clear-store-draw",
 "rgba8-load-store-blend","rgba8-clear-store-atomic","mixed-r32f-clear-store"]
STATE_FILES={
 "va_18000.bin","va_58000.bin","va_68000.bin","va_10000018200.bin",
 "va_18000.meta","va_58000.meta","va_68000.meta","va_10000018200.meta"}
SHA_LINE=re.compile(r"^([0-9a-f]{64})  ([^/].*)$")

def digest(p:Path)->str:return hashlib.sha256(p.read_bytes()).hexdigest()

def main()->int:
    for name,want in EXPECTED.items():
        got=digest(HERE/name)
        if got!=want:raise AssertionError(f"frozen hash mismatch {name}: {got}")
    for run in RUNS:
        d=HERE/"raw"/run
        if json.loads((d/"failures.json").read_text()):raise AssertionError(f"formal failures {run}")
        inventory={}
        for line in (d/"SHA256SUMS").read_text().splitlines():
            match=SHA_LINE.fullmatch(line)
            if not match:raise AssertionError(f"malformed SHA256SUMS line {run}: {line!r}")
            want,rel=match.groups()
            if rel in inventory or Path(rel).is_absolute() or ".." in Path(rel).parts:
                raise AssertionError(f"unsafe/duplicate inventory path {run}/{rel}")
            inventory[rel]=want
            got=digest(d/rel)
            if got!=want:raise AssertionError(f"raw hash mismatch {run}/{rel}")
        actual={str(p.relative_to(d)) for p in d.rglob("*")
                if p.is_file() and p.name!="SHA256SUMS"}
        if set(inventory)!=actual:
            raise AssertionError(f"incomplete inventory {run}: missing={sorted(actual-set(inventory))} extra={sorted(set(inventory)-actual)}")

    expected_payloads=set()
    for run in RUNS[:2]:
        for case in CASES:
            expected_payloads.update(f"{run}/state_{case}/{name}" for name in STATE_FILES)
    for run in RUNS[2:]:
        expected_payloads.update(
            f"{run}/state_rgba8-load-store-draw-control/{name}" for name in STATE_FILES)
    actual_payloads={str(p.relative_to(HERE/"raw")) for p in (HERE/"raw").rglob("*")
                     if p.is_file() and p.suffix in {".bin",".meta"}}
    if actual_payloads!=expected_payloads:
        raise AssertionError(f"raw payload allowlist violation missing={sorted(expected_payloads-actual_payloads)} extra={sorted(actual_payloads-expected_payloads)}")

    with tempfile.TemporaryDirectory(prefix="exp0048-verify-") as tmp:
        temp=Path(tmp)
        cp=subprocess.run(
            [sys.executable,HERE/"analysis"/"analyze.py",
             "--json",temp/"summary.json","--report",temp/"report.txt"],
            capture_output=True,text=True,timeout=30)
        if cp.returncode:raise AssertionError(f"analysis failed: {cp.stderr}")
        for name in ("summary.json","report.txt"):
            if (temp/name).read_bytes()!=(HERE/"analysis"/name).read_bytes():
                raise AssertionError(f"stale derived analysis/{name}")
    manifest=json.loads((HERE/"manifest.json").read_text())
    listed={a["path"]:a for a in manifest["artifacts"]}
    actual={str(p.relative_to(HERE)):p for p in HERE.rglob("*") if p.is_file() and p.name!="manifest.json" and "work" not in p.parts and "__pycache__" not in p.parts}
    if set(listed)!=set(actual):raise AssertionError(f"manifest coverage mismatch missing={sorted(set(actual)-set(listed))} extra={sorted(set(listed)-set(actual))}")
    for rel,p in actual.items():
        a=listed[rel]
        if a["bytes"]!=p.stat().st_size or a["sha256"]!=digest(p):raise AssertionError(f"manifest mismatch {rel}")
    print(f"PASS frozen=2 raw_runs=4 manifest_artifacts={len(listed)} analysis=PASS")
    return 0

if __name__=="__main__":raise SystemExit(main())
