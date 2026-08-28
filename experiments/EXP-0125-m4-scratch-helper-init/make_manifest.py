#!/usr/bin/env python3
"""Hash every committed artifact under this experiment directory into
manifest.json. Skips work/ (transient build output) and __pycache__/.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKIP_DIRS = {"work", "__pycache__", ".git"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    artifacts = []
    for p in sorted(HERE.rglob("*")):
        if p.is_dir():
            continue
        if p.name == "manifest.json":
            continue
        if any(part in SKIP_DIRS for part in p.relative_to(HERE).parts):
            continue
        rel = str(p.relative_to(HERE))
        artifacts.append({"path": rel, "bytes": p.stat().st_size, "sha256": sha(p)})
    manifest = {"experiment": "EXP-0125-m4-scratch-helper-init",
               "artifact_count": len(artifacts), "artifacts": artifacts}
    (HERE / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"wrote manifest.json with {len(artifacts)} artifacts")


if __name__ == "__main__":
    main()
