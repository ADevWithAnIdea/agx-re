#!/usr/bin/env python3
"""manifest.py -- EXP-0204 manifest, regenerated from what is actually on disk."""
import glob, hashlib, json, os, subprocess, time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def h(p):
    x = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 16), b""):
            x.update(c)
    return x.hexdigest()


def main():
    files = {}
    for d in ("kernels", "harness", "pinned", "analysis"):
        for fn in sorted(os.listdir(os.path.join(HERE, d))):
            p = os.path.join(HERE, d, fn)
            if os.path.isfile(p) and not fn.endswith(".pyc"):
                files[f"{d}/{fn}"] = h(p)
    for fn in ("README.md", "PRE_REGISTRATION.md", "CAPTURE_CONTRACT.json",
               "RESULTS.md", "PROGRESS.md", "run.py"):
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            files[fn] = h(p)
    raws = {}
    for d in sorted(glob.glob(os.path.join(HERE, "raw", "*"))):
        if not os.path.isdir(d):
            continue
        ent = {}
        for f in sorted(glob.glob(os.path.join(d, "*"))):
            ent[os.path.basename(f)] = {"bytes": os.path.getsize(f),
                                        "sha256": h(f),
                                        "lines": sum(1 for _ in open(f, errors="replace"))
                                        if f.endswith((".jsonl", ".json")) else None}
        raws[os.path.basename(d)] = ent
    rev = subprocess.run(["git", "-C", os.path.join(HERE, "..", ".."),
                          "rev-parse", "HEAD"], capture_output=True,
                         text=True).stdout.strip()
    m = {"experiment": "EXP-0204-g17p-tex-carrier-dimensions",
         "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "target": {"device": "Apple A18 Pro", "arch": "applegpu_g17p",
                    "accelerator": "AGXAcceleratorG17P", "cores": 5,
                    "os": "macOS 26.6", "metal_family": "Apple9",
                    "host": "users-MacBook-Neo.local", "addr": "192.168.170.254"},
         "repo_revision_at_manifest": rev,
         "clean_room": ("OWN-SHADER + HW-PROBE. Every byte spliced, decoded or "
                        "inspected is the compiled form of MSL in kernels/. No Apple "
                        "binary was disassembled, decompiled, symbol-dumped, "
                        "strings-scanned or otherwise introspected."),
         "normative_documents": ["RE_EXPERIMENT_PROCESS_CORRECTIONS.md (wins)",
                                 "CODEX.md", "CLAUDE.md",
                                 "docs/evidence-classification.md",
                                 "experiments/FIELD-SWEEP-PROTOCOL.md"],
         "source_sha256": files,
         "raw": raws}
    p = os.path.join(HERE, "manifest.json")
    json.dump(m, open(p, "w"), indent=1, sort_keys=True)
    print("wrote", p, len(files), "sources,", len(raws), "raw dirs")


if __name__ == "__main__":
    main()
