#!/usr/bin/env python3
"""Write the EXP-0057 evidence manifest without modifying captured artifacts."""
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root):
    answer = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink(): raise SystemExit(f"symlink forbidden: {path}")
        if path.is_file(): answer.append({"path": str(path.relative_to(HERE)), "bytes": path.stat().st_size, "sha256": sha(path)})
    return answer


def main():
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, text=True, capture_output=True, check=True).stdout.strip()
    manifest = {
        "experiment": "EXP-0057-m4-scratch-pressure-envelope",
        "manifest_revision": revision,
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
    }
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__": main()
