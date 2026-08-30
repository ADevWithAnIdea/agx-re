#!/usr/bin/env python3
"""Generate EXP-0185's manifest.json (artifact hashes + environment). Re-runnable.

    python3 analysis/make_manifest.py
"""
import hashlib
import json
import os
import platform
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(EXP, "..", ".."))

UPSTREAMED = [
    "tools/agxtest/saferunner.py",
    "tools/agxtest/verify_remote.py",
    "tools/agxtest/closure_scan.py",
    "tools/agxtest/fakepersist.py",
    "tools/agxtest/selftest_tools.py",
    "tools/agxtest/testdata/closure_shadow_bad.py",
    "tools/agxtest/testdata/closure_shadow_good.py",
    "tools/agxtest/README.md",
]
EXP_FILES = [
    "README.md", "RESULTS.md", "PROGRESS.md",
    "analysis/make_persistrun_patch.py",
    "analysis/gate_patched_persistrun.py",
    "analysis/make_manifest.py",
    "analysis/persistrun-DEF-0178-1.patch",
    "drafts/SUBAGENT_BRIEF-addition.md",
    "raw/selftest_tools_run01.txt",
    "raw/selftest_tools_run02.txt",
    "raw/gate_patched_persistrun_run01.txt",
    "raw/closure_scan_run01.txt",
    "work/persistrun_orig.py",
    "work/persistrun_patched.py",
]
SOURCES = [
    "experiments/EXP-0178-g17p-sysval-tileread/harness/saferunner.py",
    "experiments/EXP-0178-g17p-sysval-tileread/harness/verify_remote.py",
    "experiments/EXP-0178-g17p-sysval-tileread/harness/closure_scan.py",
    "experiments/EXP-0178-g17p-sysval-tileread/harness/fakerunner.py",
    "experiments/EXP-0179-g17p-call/harness/saferunner.py",
    "experiments/EXP-0179-g17p-call/harness/fakechild.py",
    "tools/agxtest/persistrun.py",
]


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def git(*args):
    try:
        return subprocess.run(["git"] + list(args), cwd=REPO, capture_output=True,
                              text=True).stdout.strip()
    except Exception:                                          # noqa: BLE001
        return "?"


def main():
    m = {
        "experiment": "EXP-0185-tooling-upstream",
        "date_utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                                   capture_output=True, text=True).stdout.strip(),
        "type": "tooling/process — no hardware claim",
        "target": "NONE — pure analysis, no device, no SSH, no GPU, no dispatch",
        "clean_room": {"apple_binary_introspection": "NONE",
                       "inputs": "our own harness code and fixtures in this repository"},
        "environment": {
            "host": "M4 repo host (analysis only; local GPU testing is retired)",
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "git": {"head": git("rev-parse", "HEAD"),
                "dirty_files": len([l for l in git("status", "--porcelain").splitlines()
                                    if l.strip()])},
        "gates": {
            "tools/agxtest/selftest_tools.py": "T0..T7 PASS (raw/selftest_tools_run01.txt)",
            "analysis/gate_patched_persistrun.py":
                "P1..P7 PASS (raw/gate_patched_persistrun_run01.txt)",
            "git apply --check analysis/persistrun-DEF-0178-1.patch": "clean",
        },
        "patch_status": "GENERATED AND GATED, NOT APPLIED — tools/agxtest/persistrun.py is "
                        "untouched (EXP-0184 may be running against it)",
        "upstreamed_sha256": {},
        "experiment_sha256": {},
        "source_copies_sha256": {},
    }
    for rel in UPSTREAMED:
        m["upstreamed_sha256"][rel] = sha(os.path.join(REPO, rel))
    for rel in EXP_FILES:
        p = os.path.join(EXP, rel)
        if os.path.exists(p):
            m["experiment_sha256"][rel] = sha(p)
    for rel in SOURCES:
        m["source_copies_sha256"][rel] = sha(os.path.join(REPO, rel))

    out = os.path.join(EXP, "manifest.json")
    with open(out, "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=False)
        fh.write("\n")
    print("wrote %s (%d hashed artifacts)"
          % (out, len(m["upstreamed_sha256"]) + len(m["experiment_sha256"])
             + len(m["source_copies_sha256"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
