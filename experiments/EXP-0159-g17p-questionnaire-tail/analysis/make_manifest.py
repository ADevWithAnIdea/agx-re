#!/usr/bin/env python3
"""EXP-0159 manifest: hash every authored input and every raw artifact.
Authored by the clean-room RE team."""
import hashlib, json, os, subprocess, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()
m = {"experiment": "EXP-0159-g17p-questionnaire-tail",
     "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
     "target": "Apple A18 Pro / G17P (applegpu_g17p, AGXAcceleratorG17P, 5 cores, macOS 26.6 25G5043d)",
     "questions": ["P2-06", "TEX-01", "TEX-19", "TEX-21", "TEX-22", "MEM-19"],
     "git_revision_at_freeze": "7dc67d768ada3c016771923bffd5b9647dd14813",
     "authored": {}, "raw": {}}
for d, key in ((".", "authored"), ("kernels", "authored"), ("kernels/fa", "authored"),
               ("harness", "authored"), ("analysis", "authored")):
    p0 = os.path.join(ROOT, d)
    for f in sorted(os.listdir(p0)):
        p = os.path.join(p0, f)
        if os.path.isfile(p):
            rel = os.path.relpath(p, ROOT)
            m[key][rel] = {"sha256": sha(p), "bytes": os.path.getsize(p)}
for dp, _, fs in os.walk(os.path.join(ROOT, "raw")):
    for f in sorted(fs):
        p = os.path.join(dp, f)
        rel = os.path.relpath(p, ROOT)
        m["raw"][rel] = {"sha256": sha(p), "bytes": os.path.getsize(p),
                         "lines": sum(1 for _ in open(p, "rb")) if f.endswith((".jsonl", ".log", ".txt")) else None}
m["counts"] = {"authored_files": len(m["authored"]), "raw_files": len(m["raw"]),
               "raw_bytes": sum(v["bytes"] for v in m["raw"].values())}
json.dump(m, open(os.path.join(ROOT, "manifest.json"), "w"), indent=1, sort_keys=True)
print("manifest: %d authored, %d raw, %.1f MB raw" % (
    m["counts"]["authored_files"], m["counts"]["raw_files"], m["counts"]["raw_bytes"] / 1e6))
