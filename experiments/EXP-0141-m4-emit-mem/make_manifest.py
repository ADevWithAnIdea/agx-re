#!/usr/bin/env python3
"""EXP-0141 manifest: hashes and sizes of every authored input and every raw
artifact, so the clean-room chain
  documented fact -> RESULTS.md -> analysis -> raw capture -> authored probe
can be checked from the repository alone.
"""
import hashlib
import json
import platform
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree(root, pats):
    out = {}
    for pat in pats:
        for p in sorted(root.glob(pat)):
            if p.is_file():
                out[str(p.relative_to(HERE))] = {"sha256": sha(p), "bytes": p.stat().st_size}
    return out


def main():
    m = {"experiment": "EXP-0141-m4-emit-mem",
         "target": {"device": "Apple M4 / G16G", "hw_model": "Mac16,10",
                    "os": "macOS 26.6.2 (25G82)", "machine": platform.machine(),
                    "note": "local host only; A18 Pro hands-off; M5 out of scope"},
         "git_revision_informational_only":
             subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE, text=True,
                            capture_output=True).stdout.strip(),
         "authored": tree(HERE, ["*.py", "*.md", "*.json", "harness/*", "kernels/*",
                                 "analysis/*.py"]),
         "raw": tree(HERE, ["raw/*/*.jsonl", "raw/*/*.json", "raw/*/*.md"]),
         "derived": tree(HERE, ["analysis/*.json"]),
         "readonly_tools": {p: sha(REPO / p) for p in
                            ["tools/agx-isa/isadb.py", "tools/agx-isa/db.json",
                             "tools/agxtest/agxrun_persist.m",
                             "tools/agxtest/persistrun.py",
                             "tools/shdump/shdump.m", "tools/shdump/agxparse.py"]},
         "clean_room": {"provenance": "HW-PROBE + OWN-SHADER",
                        "apple_binary_introspection": "NONE",
                        "inputs": "our own MSL, our own hand-assembled AGX programs "
                                  "(tools/agx-isa isadb.assemble), our own compiled "
                                  "shader bytes"}}
    (HERE / "manifest.json").write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    print("manifest.json: %d authored, %d raw, %d derived artifacts"
          % (len(m["authored"]), len(m["raw"]), len(m["derived"])))


if __name__ == "__main__":
    main()
