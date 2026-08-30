#!/usr/bin/env python3
"""manifest.py -- EXP-0172 (forked from OUR OWN EXP-0163): regenerate manifest.json (artifact hashes + metadata).

    python3 analysis/manifest.py
"""
import hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXP = os.path.dirname(HERE)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def walk(rel):
    out = {}
    root = os.path.join(EXP, rel)
    if not os.path.isdir(root):
        return out
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in ("__pycache__",)]
        for f in sorted(fn):
            p = os.path.join(dp, f)
            r = os.path.relpath(p, EXP)
            out[r] = {"sha256": sha(p), "bytes": os.path.getsize(p)}
    return out


files = {}
for rel in ("kernels", "harness", "analysis", "raw"):
    files.update(walk(rel))
for f in ("run.py", "README.md", "RESULTS.md", "PRE_REGISTRATION.md",
          "CAPTURE_CONTRACT.json", "PROGRESS.md"):
    p = os.path.join(EXP, f)
    if os.path.exists(p):
        files[f] = {"sha256": sha(p), "bytes": os.path.getsize(p)}

runs = {}
for d in sorted(os.listdir(os.path.join(EXP, "raw"))):
    m = os.path.join(EXP, "raw", d, "05_run_manifest.json")
    if os.path.exists(m):
        j = json.load(open(m))
        runs[d] = {k: j[k] for k in ("run_id", "cases", "hangs", "cascade",
                                     "elapsed_s")}

man = {
 "experiment": "EXP-0163-g17p-inert-liveness",
 "question": ("Is any AGX encoding field genuinely a don't-care, or does 'inert' "
              "only mean the EXP-0155 carrier never exercised it?"),
 "target": {"name": "Apple A18 Pro", "gpu": "G17P", "arch": "applegpu_g17p",
            "accelerator": "AGXAcceleratorG17P", "cores": 5, "os": "macOS 26.6",
            "metal_family": "Apple9", "host": "users-MacBook-Neo.local",
            "addr": "192.168.10.243", "device_workdir": "~/agxre/EXP-0163"},
 "clean_room": {"provenance": ["OWN-SHADER", "HW-PROBE"],
                "apple_binary_introspection": "NONE",
                "inputs": "kernels/*.metal (ours) + the machine code the public "
                          "Metal API produced from them"},
 "toolchain_on_device": {
   "build": "clang -fobjc-arc -O2 -Wno-deprecated-declarations "
            "-framework Metal -framework Foundation",
   "xcode": "/Applications/Xcode.app (full Xcode present on the neo)",
   "isa_db": "tools/agx-isa/db.json + isadb.py, copied from the repo into "
             "~/agxre/EXP-0163/tools so the DB is pinned for the whole "
             "experiment (hashes in CAPTURE_CONTRACT.json source_sha256)"},
 "runs": runs,
 "artifacts": files,
 "generated_utc": subprocess.run(["date", "-u", "+%Y-%m-%dT%H:%M:%SZ"],
                                 capture_output=True, text=True).stdout.strip(),
}
json.dump(man, open(os.path.join(EXP, "manifest.json"), "w"), indent=1, sort_keys=True)
print("manifest.json:", len(files), "artifacts,", len(runs), "runs")
