#!/usr/bin/env python3
"""EXP-0206 manifest generator (CODEX.md section 6). Runs on the M4."""
import hashlib, json, os, subprocess, time
EXP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sh(*c):
    try:
        return subprocess.check_output(c, text=True, cwd=EXP, timeout=30).strip()
    except Exception as e:                                      # noqa: BLE001
        return "ERR %s" % e


def main():
    files = {}
    for root, _d, fs in os.walk(EXP):
        if "__pycache__" in root or "/work" in root:
            continue
        for f in fs:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, EXP)
            if rel == "manifest.json":
                continue
            files[rel] = {"sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(),
                          "bytes": os.path.getsize(p)}
    doc = {
        "experiment": "EXP-0206",
        "title": "control flow and scope on G17P: seven fields across six instructions",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "target": {"device": "Apple A18 Pro", "gpu": "G17P / AGXAcceleratorG17P",
                   "arch": "applegpu_g17p", "cores": 5, "os": "macOS 26.6 (25G5043d)",
                   "metal_family": "Apple9", "host": "192.168.170.254"},
        "repo_revision": sh("git", "rev-parse", "HEAD"),
        "repo_dirty": bool(sh("git", "status", "--porcelain")),
        "clean_room": {"provenance": ["HW-PROBE", "OWN-SHADER"],
                       "apple_binary_introspection": "NONE",
                       "inputs_inspected": ["kernels/k_cf206.metal",
                                            "kernels/k_cl206.metal",
                                            "the AGX bytes the public Metal runtime "
                                            "compiled from them"]},
        "gated_runs": ["g17p_20260830_run03 (forward order)",
                       "g17p_20260830_run04 (reversed order)"],
        "calibration_retained_never_cited": [
            "raw/prefreeze/census.json",
            "raw/pilot_20260830_p01 (434 cases)",
            "raw/g17p_20260830_run01 (KILLED at 152 cases for throughput; retained, "
            "never topped up, id never reused)",
            "raw/smoke_20260830_s01 (36 cases)"],
        "pinned_tools": {k: v["sha256"] for k, v in files.items()
                         if k.startswith("pinned/")},
        "files": files,
    }
    open(os.path.join(EXP, "manifest.json"), "w").write(
        json.dumps(doc, indent=1, sort_keys=True))
    print("manifest: %d files" % len(files))


main()
