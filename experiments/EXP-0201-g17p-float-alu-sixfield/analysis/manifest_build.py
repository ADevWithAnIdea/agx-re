#!/usr/bin/env python3
"""EXP-0201 manifest builder. Runs on the M4 (the evidence store).

    python3 analysis/manifest_build.py

Hashes every authored input, every pinned tool snapshot and every raw capture,
so a reviewer can check the chain

    documented fact -> RESULTS.md -> analysis script -> immutable raw capture
                    -> authored probe input + exact reproduction command

without trusting any prose. Raw files are listed with size and sha256; they are
append-only and are never rewritten.
"""
import hashlib
import json
import os
from pathlib import Path

EXP = Path(__file__).resolve().parent.parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tree(rel):
    out = {}
    root = EXP / rel
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            out[str(p.relative_to(EXP))] = {"bytes": p.stat().st_size,
                                            "sha256": sha(p)}
    return out


def main():
    contract = json.loads((EXP / "CAPTURE_CONTRACT.json").read_text())
    m = {
        "experiment": "EXP-0201-g17p-float-alu-sixfield",
        "title": "G17P float ALU: six fields across five instructions",
        "target": contract["target"],
        "clean_room": {
            "provenance": ["HW-PROBE", "OWN-SHADER"],
            "inputs_inspected": "kernels/k_falu201.metal (authored by us) and "
                                "its compiled _agc.main bytes",
            "apple_binary_introspection": "NONE",
        },
        "capture_contract_sha256": sha(EXP / "CAPTURE_CONTRACT.json"),
        "repo_revision_at_freeze": contract["repo"],
        "fields_under_test": contract["fields"],
        "gate": contract["gate"],
        "authored": tree("kernels") | tree("harness") | tree("analysis"),
        "pinned": tree("pinned"),
        "raw": tree("raw"),
        "runs": sorted(d.name for d in (EXP / "raw").iterdir() if d.is_dir())
                if (EXP / "raw").exists() else [],
        "top_level": {f: {"bytes": (EXP / f).stat().st_size,
                          "sha256": sha(EXP / f)}
                      for f in ("run.py", "README.md", "PRE_REGISTRATION.md",
                                "RESULTS.md", "PROGRESS.md")
                      if (EXP / f).exists()},
    }
    (EXP / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")
    print("manifest: %d authored, %d pinned, %d raw files, runs=%s"
          % (len(m["authored"]), len(m["pinned"]), len(m["raw"]),
             ",".join(m["runs"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
