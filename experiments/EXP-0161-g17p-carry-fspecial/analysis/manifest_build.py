#!/usr/bin/env python3
"""EXP-0161 manifest builder: hashes every committed artifact."""
import hashlib, json, subprocess, sys
from pathlib import Path
EXP = Path(__file__).resolve().parent.parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


files = {}
for p in sorted(EXP.rglob("*")):
    if p.is_dir() or "__pycache__" in str(p) or p.name == "manifest.json":
        continue
    rel = str(p.relative_to(EXP))
    if rel.startswith("work/") and not rel.startswith(("work/frozen/", "work/anchors/",
                                                       "work/logs/",
                                                       "work/smoke.json",
                                                       "work/pilot_seed.json")):
        continue
    files[rel] = {"sha256": sha(p), "bytes": p.stat().st_size}

runs = {}
for d in sorted((EXP / "raw").glob("g17p_*")):
    f = d / "sweep.jsonl"
    if f.exists():
        runs[d.name] = {"cases": sum(1 for _ in open(str(f))),
                        "sha256": sha(f)}

man = {
    "experiment": "EXP-0161-g17p-carry-fspecial",
    "target": {"name": "Apple A18 Pro / G17P", "arch": "applegpu_g17p",
               "accelerator": "AGXAcceleratorG17P", "gpu_cores": 5,
               "os": "macOS 26.6", "metal_family": "Apple9", "model": "Mac17,5",
               "host": "192.168.10.243"},
    "analysis_host": {"machine": "Apple M4 (repo host, NO GPU work)",
                      "note": "the M4 is retired for GPU work; it hosts the repo"},
    "tools": {"shdump": "tools/shdump (READ-ONLY)",
              "agxtest": "tools/agxtest (READ-ONLY, persistrun.py with the "
                         "DEF-0153-2 fix)",
              "agx-isa": "pinned copy in work/frozen/ (sha256 in "
                         "CAPTURE_CONTRACT.json)"},
    "repo_revision": subprocess.check_output(
        ["git", "-C", str(EXP), "rev-parse", "HEAD"]).decode().strip(),
    "runs": runs,
    "artifacts": files,
    "clean_room": {"provenance": "OWN-SHADER + HW-PROBE",
                   "apple_binary_introspection": "NONE",
                   "files_not_edited": ["tools/agx-isa/db.json",
                                        "tools/agx-isa/validation.json",
                                        "docs/", "PROVENANCE.md"],
                   "committed": False},
}
(EXP / "manifest.json").write_text(json.dumps(man, indent=1, sort_keys=True))
print("manifest: %d artifacts, %d runs" % (len(files), len(runs)))
