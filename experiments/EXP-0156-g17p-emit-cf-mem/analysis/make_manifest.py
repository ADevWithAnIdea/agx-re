#!/usr/bin/env python3
"""EXP-0156: build (or --check) `manifest.json` — every committed artifact with its
size and SHA-256, plus the target/tool/revision metadata CODEX.md §6 requires."""
import hashlib, json, subprocess, sys, time
from pathlib import Path
EXP = Path(__file__).resolve().parent.parent
REPO = EXP.parents[1]

def sha(p):
    h = hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def build():
    files = {}
    for p in sorted(EXP.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(EXP).as_posix()
        if rel.startswith("work/") or rel == "manifest.json":
            continue
        files[rel] = {"bytes": p.stat().st_size, "sha256": sha(p)}
    cc = json.load((EXP / "CAPTURE_CONTRACT.json").open())
    return {
        "experiment": "EXP-0156-g17p-emit-cf-mem",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target": cc["target"],
        "repo_revision_pinned_at_freeze": cc["repo_revision_pinned_at_freeze"],
        "tool_sha256": cc["tool_sha256"],
        "clean_room": cc["clean_room"],
        "raw_is_append_only": True,
        "files": files,
    }

if __name__ == "__main__":
    m = build()
    if "--check" in sys.argv:
        old = json.load((EXP / "manifest.json").open())
        bad = [k for k in old["files"]
               if k not in m["files"] or old["files"][k]["sha256"] != m["files"][k]["sha256"]]
        print("manifest check: %d recorded, %d changed/missing" % (len(old["files"]), len(bad)))
        for k in bad[:20]:
            print("  CHANGED", k)
        sys.exit(1 if bad else 0)
    (EXP / "manifest.json").write_text(json.dumps(m, indent=1, sort_keys=True))
    print("manifest.json: %d files" % len(m["files"]))
