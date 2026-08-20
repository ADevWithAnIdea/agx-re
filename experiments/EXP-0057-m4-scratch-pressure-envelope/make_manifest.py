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


def files(root):
    answer = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink(): raise SystemExit(f"symlink forbidden: {path}")
        if path.is_file():
            if not regular(path): raise SystemExit(f"non-regular artifact: {path}")
            answer.append({"path": str(path.relative_to(HERE)), "bytes": path.stat().st_size, "sha256": sha(path)})
    return answer


def main():
    # Raw path/type authorization is deliberately before any raw bytes are read.
    validate_raw_tree()
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
        "raw_artifacts": files(RAW),
        "analysis_artifacts": files(HERE / "analysis"),
        "source_tools": files(HERE / "harness") + files(HERE / "kernels") +
                        [{"path": rel, "bytes": (HERE / rel).stat().st_size, "sha256": sha(HERE / rel)}
                         for rel in ("run.py", "make_manifest.py", "verify.py")],
        "protocol_files": [{"path": "PRE_REGISTRATION.md", "bytes": (HERE / "PRE_REGISTRATION.md").stat().st_size,
                            "sha256": sha(HERE / "PRE_REGISTRATION.md")}],
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__": main()
