#!/usr/bin/env python3
"""EXP-0140: write/verify manifest.json (SHA-256 of every authored input and
every raw artifact).  `--check` re-hashes and reports drift."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def build():
    m = {
        "experiment": "EXP-0140-m4-emit-mov-cf",
        "target": "local Apple M4 / G16G (macOS 26.6, Metal 4)",
        "clean_room": "HW-PROBE + OWN-SHADER; Apple binary introspection: NONE",
        "git_rev": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO),
                                   capture_output=True, text=True).stdout.strip(),
        "authored_inputs": {},
        "raw": {},
        "analysis": {},
        "readonly_tools": {},
    }
    for d, key in (("kernels", "authored_inputs"), ("harness", "authored_inputs"),
                    ("analysis", "analysis")):
        for p in sorted((EXP / d).rglob("*")):
            if p.is_file() and p.suffix in (".metal", ".py", ".sh", ".json"):
                m[key][str(p.relative_to(EXP))] = sha(p)
    for p in sorted((EXP / "raw").rglob("*")):
        if p.is_file():
            m["raw"][str(p.relative_to(EXP))] = {"sha256": sha(p), "bytes": p.stat().st_size}
    for rel in ("tools/agx-isa/isadb.py", "tools/agx-isa/db.json",
                "tools/agxtest/agxrun_persist.m", "tools/agxtest/persistrun.py",
                "tools/shdump/shdump.m", "tools/shdump/agxparse.py"):
        m["readonly_tools"][rel] = sha(REPO / rel)
    for f in ("PRE_REGISTRATION.md", "README.md", "PROGRESS.md", "RESULTS.md"):
        if (EXP / f).exists():
            m["authored_inputs"][f] = sha(EXP / f)
    return m


def main():
    if "--check" in sys.argv:
        old = json.load(open(EXP / "manifest.json"))
        new = build()
        bad = []
        for sect in ("raw",):
            for k, v in old[sect].items():
                nv = new[sect].get(k)
                if nv != v:
                    bad.append((k, v, nv))
        print("RAW DRIFT:", bad if bad else "none")
        sys.exit(1 if bad else 0)
    (EXP / "manifest.json").write_text(json.dumps(build(), indent=1, sort_keys=True))
    print("wrote manifest.json")


if __name__ == "__main__":
    main()
