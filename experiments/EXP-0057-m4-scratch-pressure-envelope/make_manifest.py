#!/usr/bin/env python3
"""Write the EXP-0057 evidence manifest without modifying captured artifacts."""
import hashlib
import json
import stat
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
RUNS = ("m4_20260819_run01", "m4_20260819_run02")
LEVELS = ("baseline", "p576", "p1024", "p2048", "p4096", "p8192", "p16384")
SHAPES = ("tg32", "tg256")
PREREG_COMMIT = "e76f6250"
TOOL_COMMITS = ("5055ed85", "3a0c89e5", "cdaf1709")
TOP_FILES = {".gitignore", "PRE_REGISTRATION.md", "README.md", "RESULTS.md", "run.py", "make_manifest.py", "verify.py", "manifest.json"}
ANALYSIS_FILES = {"analyze.py", "compare.py", "m4_20260819_run01.json", "m4_20260819_run02.json", "m4_20260819_repeat.json"}
HARNESS_FILES = {"metadata.py", "probe.m"}
KERNEL_FILES = {"generate.py"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regular(path):
    mode = path.lstat().st_mode
    return stat.S_ISREG(mode) and not path.is_symlink()


def expected_raw_paths(run):
    names = {"00_generate.json", "01_sources.json", "02_build_probe.json", "run_manifest.json"}
    names |= {f"metadata_{level}.json" for level in LEVELS}
    names |= {f"trial_{level}_{shape}.json" for level in LEVELS for shape in SHAPES}
    names |= {f"sources/{level}.metal" for level in LEVELS}
    # This is an append-only derived JSON accidentally placed under run02 before
    # the tree policy existed. It is named explicitly rather than tolerated by a
    # wildcard, and carries no payload outside already approved JSON records.
    if run == "m4_20260819_run02": names.add("analysis.json")
    return names


def validate_raw_tree():
    if not RAW.is_dir() or RAW.is_symlink(): raise SystemExit("bad raw root")
    entries = {path.name for path in RAW.iterdir()}
    if entries != set(RUNS): raise SystemExit(f"unexpected raw roots: {sorted(entries)}")
    for run in RUNS:
        root = RAW / run
        if not root.is_dir() or root.is_symlink(): raise SystemExit(f"bad run root {run}")
        seen = set()
        for path in root.rglob("*"):
            rel = str(path.relative_to(root))
            if path.is_symlink(): raise SystemExit(f"symlink forbidden: {run}/{rel}")
            if path.is_dir():
                if rel != "sources": raise SystemExit(f"unexpected raw directory: {run}/{rel}")
                continue
            if not regular(path): raise SystemExit(f"non-regular raw artifact: {run}/{rel}")
            if rel not in expected_raw_paths(run): raise SystemExit(f"unexpected raw artifact: {run}/{rel}")
            if not (rel.endswith(".json") or rel.startswith("sources/") and rel.endswith(".metal")):
                raise SystemExit(f"unapproved raw type: {run}/{rel}")
            seen.add(rel)
        if seen != expected_raw_paths(run): raise SystemExit(f"raw matrix mismatch for {run}")


def validate_experiment_tree():
    """Authorize every retained path before any artifact content is opened."""
    if not HERE.is_dir() or HERE.is_symlink(): raise SystemExit("bad experiment root")
    wanted_dirs = {"analysis", "harness", "kernels", "raw"}
    top_dirs = {path.name for path in HERE.iterdir() if path.is_dir() and not path.is_symlink()}
    top_files = {path.name for path in HERE.iterdir() if path.is_file() and not path.is_symlink()}
    if top_dirs != wanted_dirs or top_files != TOP_FILES:
        raise SystemExit(f"experiment root matrix mismatch dirs={sorted(top_dirs)} files={sorted(top_files)}")
    for dirname, expected in (("analysis", ANALYSIS_FILES), ("harness", HARNESS_FILES), ("kernels", KERNEL_FILES)):
        root = HERE / dirname
        names = set()
        for path in root.iterdir():
            if path.is_symlink() or not regular(path): raise SystemExit(f"bad {dirname} artifact: {path.name}")
            names.add(path.name)
        if names != expected: raise SystemExit(f"{dirname} matrix mismatch: {sorted(names)}")
    validate_raw_tree()


def approved_nonmanifest_paths():
    paths = {".gitignore", "PRE_REGISTRATION.md", "README.md", "RESULTS.md", "run.py", "make_manifest.py", "verify.py"}
    paths |= {f"analysis/{name}" for name in ANALYSIS_FILES}
    paths |= {f"harness/{name}" for name in HARNESS_FILES}
    paths |= {f"kernels/{name}" for name in KERNEL_FILES}
    for run in RUNS:
        paths |= {f"raw/{run}/{name}" for name in expected_raw_paths(run)}
    return paths


def records(paths):
    answer = []
    for rel in sorted(paths):
        path = HERE / rel
        if not regular(path): raise SystemExit(f"bad approved artifact: {rel}")
        answer.append({"path": rel, "bytes": path.stat().st_size, "sha256": sha(path)})
    return answer


def main():
    # Raw path/type authorization is deliberately before any raw bytes are read.
    validate_experiment_tree()
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, text=True, capture_output=True, check=True).stdout.strip()
    manifest = {
        "experiment": "EXP-0057-m4-scratch-pressure-envelope",
        "manifest_revision": revision,
        "required_clean_room_commits": {"preregistration": PREREG_COMMIT, "tooling": list(TOOL_COMMITS)},
        "clean_room": {
            "apple_binary_introspection": False,
            "apple_helper_program_bytes_inspected": False,
            "apple_command_state_code_unknown_bo_bytes_inspected": False,
            "compiled_non_authored_code_inspected": False,
        },
        "raw_artifacts": records({f"raw/{run}/{name}" for run in RUNS for name in expected_raw_paths(run)}),
        "analysis_artifacts": records({f"analysis/{name}" for name in ANALYSIS_FILES}),
        "source_tools": records({".gitignore", "run.py", "make_manifest.py", "verify.py"} |
                                {f"harness/{name}" for name in HARNESS_FILES} | {f"kernels/{name}" for name in KERNEL_FILES}),
        "protocol_files": records({"PRE_REGISTRATION.md", "README.md", "RESULTS.md"}),
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__": main()
